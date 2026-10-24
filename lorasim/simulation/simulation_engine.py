"""Simülasyon motoru: çoklu verici/alıcı, sürekli trafik, ACK, tekrar gönderim ve çakışmalar.

Her vericinin bir hedef alıcısı vardır. Verici durum makinesi:

    üret → kuyruk → [duty-cycle bekle] → gönder → (hedef alıcı: al → ACK gönder)
         → ACK alındı: onaylandı | timeout: [rastgele backoff] tekrar gönder veya vazgeç

Havadaki tüm gönderimler (veri ve ACK) `_air` listesinde tutulur. Bir alım
değerlendirilirken onunla zamanda örtüşen diğer gönderimler girişim kaynağıdır
(capture effect, bkz. channel/interference.py). Alıcı o sırada kendisi gönderim
yapıyorsa (half-duplex) alım başarısız olur.
"""

from __future__ import annotations

import itertools
import secrets
import threading
import time
from dataclasses import dataclass, replace
from typing import Callable, Optional

import numpy as np

from lorasim.channel.channel_model import Link, LinkSample, ResolvedChannel
from lorasim.channel.interference import ExternalInterference, Interferer, survives_capture
from lorasim.channel.noise import dbm_sum
from lorasim.config import SimConfig
from lorasim.devices.device import Device, build_devices
from lorasim.devices.receiver import ReceiverState
from lorasim.devices.transmitter import TransmitterState
from lorasim.lora.lora_parameters import LoRaPhy
from lorasim.lora.sensitivity import sensitivity_dbm
from lorasim.metrics.collector import AckStatus, MetricsCollector, Outcome, PacketOutcome, PacketRecord
from lorasim.metrics.energy import device_energy
from lorasim.simulation.ack_manager import ack_airtime_s, auto_ack_timeout_s, build_ack, parse_ack
from lorasim.simulation.duty_cycle import DutyCycleTracker
from lorasim.simulation.link_level_model import LinkLevelModel, RxResult, RxStatus
from lorasim.simulation.packet_manager import Packet, PacketFactory
from lorasim.simulation.scheduler import EventScheduler

RecordCallback = Callable[[PacketRecord], None]
_INTERFERENCE_PAYLOAD_BYTES = 20  # harici LoRa girişim paketlerinin uzunluğu


@dataclass(frozen=True)
class AirTransmission:
    sender: str
    start_s: float
    end_s: float
    sf: int
    kind: str  # "data" | "ack"


@dataclass
class _PendingAttempt:
    """ACK beklenen gönderim denemesi."""

    tx: TransmitterState
    rx: ReceiverState
    packet: Packet
    attempt: int
    rx_time_s: float
    sample: LinkSample
    result: RxResult
    duplicate: bool
    violation: bool
    freq_offset_hz: float
    interferers: int
    ack_status: AckStatus = AckStatus.NOT_SENT
    ack_in_flight: bool = False


def make_phy_model(model: str, phy: LoRaPhy, sensitivity: float, rng: np.random.Generator, lora_cfg):
    if model == "css_phy":
        from lorasim.simulation.css_phy_model import CssPhyModel
        return CssPhyModel(phy, sensitivity, rng, sync_word=lora_cfg.sync_word, iq_inverted=lora_cfg.iq_inverted)
    return LinkLevelModel(phy, sensitivity, rng)


class SimulationEngine:
    """Thread-safe kontrol: stop/pause/resume başka bir iş parçacığından çağrılabilir."""

    def __init__(self, config: SimConfig, on_record: Optional[RecordCallback] = None):
        config.validate()
        self.config = config
        self.seed = config.run.seed if config.run.seed is not None else secrets.randbits(32)
        self.rng = np.random.default_rng(self.seed)
        self.on_record = on_record

        lora, radio, traffic, ack = config.lora, config.radio, config.traffic, config.ack
        self.phy = LoRaPhy.from_config(lora)
        self.sensitivity_dbm = sensitivity_dbm(lora.spreading_factor, self.phy.bandwidth_hz,
                                               radio.noise_figure_db, radio.sensitivity_override_dbm)
        self.channel = ResolvedChannel.from_config(config.channel)
        self.model = make_phy_model(config.run.model, self.phy, self.sensitivity_dbm, self.rng, lora)
        self.airtime_s = self.phy.time_on_air_s(lora.payload_bytes)
        self.ack_airtime_s = ack_airtime_s(self.phy)
        self.ack_timeout_s = (ack.timeout_s if ack.timeout_s is not None
                              else auto_ack_timeout_s(self.phy, ack.turnaround_s))
        self.enforce_duty_cycle = traffic.duty_cycle_policy == "enforce"

        self.devices: dict[str, Device] = {d.id: d for d in build_devices(config, self.rng)}
        self.transmitters = {
            d.id: TransmitterState(d, PacketFactory(d.id, d.target, lora.payload_bytes, lora.crc_enabled, self.rng),
                                   DutyCycleTracker(traffic.duty_cycle_limit))
            for d in self.devices.values() if d.role == "tx"
        }
        self.receivers = {d.id: ReceiverState(d, DutyCycleTracker(traffic.duty_cycle_limit))
                          for d in self.devices.values() if d.role == "rx"}
        self._links: dict[frozenset, Link] = {}
        self.external = None
        ch = self.channel
        if ch.interference_enabled and ch.interference_rate_hz > 0:
            if ch.interference_type == "lora":
                ext_phy = replace(self.phy, sf=ch.interference_sf)
                duration, sf = ext_phy.time_on_air_s(_INTERFERENCE_PAYLOAD_BYTES), ch.interference_sf
            else:
                duration, sf = ch.interference_duration_s, None
            self.external = ExternalInterference(ch.interference_rate_hz, duration, ch.interference_power_dbm, sf,
                                                 np.random.default_rng(self.rng.integers(2**63)))
        self._air: list[AirTransmission] = []
        self._air_horizon = 2 * max(self.airtime_s, self.ack_airtime_s) + self.ack_timeout_s + 1.0

        self.metrics = MetricsCollector(config.run.max_records)
        self.scheduler = EventScheduler()
        for tx in self.transmitters.values():
            t0 = float(self.rng.uniform(0, traffic.interval_s)) if traffic.random_start else 0.0
            self.scheduler.schedule(t0, lambda t, tx=tx: self._on_generate(t, tx))

        self._stop = threading.Event()
        self._running = threading.Event()
        self._running.set()

    # --- kontrol -------------------------------------------------------------
    def stop(self) -> None:
        self._stop.set()
        self._running.set()

    def pause(self) -> None:
        self._running.clear()

    def resume(self) -> None:
        self._running.set()

    @property
    def stopped(self) -> bool:
        return self._stop.is_set()

    @property
    def paused(self) -> bool:
        return not self._running.is_set()

    @property
    def now(self) -> float:
        return self.scheduler.now

    def device_positions(self, t: Optional[float] = None) -> dict[str, tuple[str, float, float]]:
        """Cihaz kimliği → (rol, x, y). Konumlar zamanın saf fonksiyonu olduğundan her thread'den çağrılabilir."""
        t = self.scheduler.now if t is None else t
        return {d.id: (d.role, *map(float, d.position(t)[:2])) for d in self.devices.values()}

    # --- kanal ---------------------------------------------------------------
    def link(self, a: Device, b: Device) -> Link:
        key = frozenset((a.id, b.id))
        if key not in self._links:
            self._links[key] = Link(a, b, self.config.lora, self.config.radio, self.channel, self.rng)
        return self._links[key]

    def _freq_offset_hz(self, sender: Device, receiver: Device, sample: LinkSample) -> float:
        f = self.config.lora.frequency_mhz * 1e6
        return (sender.frequency_offset_ppm - receiver.frequency_offset_ppm) * 1e-6 * f + sample.doppler_hz

    def _transmit(self, sender: str, start: float, duration: float, kind: str) -> None:
        self._air.append(AirTransmission(sender, start, start + duration, self.phy.sf, kind))
        horizon = start - self._air_horizon
        if self._air[0].end_s < horizon:
            self._air = [a for a in self._air if a.end_s >= horizon]

    def _receive(self, sender: Device, receiver: Device, frame: bytes, start: float, end: float,
                 sample: LinkSample) -> tuple[RxResult, float, int]:
        """Bir gönderimin alıcıdaki sonucu: (alım sonucu, frekans farkı, örtüşen girişim sayısı)."""
        cfo = self._freq_offset_hz(sender, receiver, sample)
        if any(a.sender == receiver.id and a.start_s < end and a.end_s > start for a in self._air):
            return RxResult(RxStatus.HALF_DUPLEX, None, 0, 0, 0, 0), cfo, 0
        interferers: list[Interferer] = []
        if self.channel.collisions_enabled:
            for a in self._air:
                if a.sender in (sender.id, receiver.id) or not (a.start_s < end and a.end_s > start):
                    continue
                p = self.link(self.devices[a.sender], receiver).sample(max(a.start_s, start)).rssi_dbm
                interferers.append(Interferer(p, a.sf, a.start_s, a.end_s))
        if self.external is not None:
            interferers += self.external.overlapping(start, end)
        wideband = [i.power_dbm for i in interferers if i.sf is None]
        noise = dbm_sum([sample.noise_dbm] + wideband) if wideband else sample.noise_dbm
        snr = sample.rssi_dbm - noise
        result = self.model.receive(frame, sample.rssi_dbm, snr, cfo)
        lora_interferers = [i for i in interferers if i.sf is not None]
        if (lora_interferers and result.status not in (RxStatus.NOT_DETECTED, RxStatus.FREQ_OFFSET)
                and not survives_capture(sample.rssi_dbm, self.phy.sf, lora_interferers,
                                         self.channel.capture_threshold_db)):
            result = RxResult(RxStatus.COLLISION, None, 0, 0, result.symbol_errors, result.symbols_compared)
        return result, cfo, len(interferers)

    # --- trafik üretimi ------------------------------------------------------
    def _on_generate(self, now: float, tx: TransmitterState) -> None:
        packet = tx.factory.create(now)
        tx.generated += 1
        traffic = self.config.traffic
        if len(tx.queue) >= traffic.tx_queue_size:
            self.metrics.add_outcome(PacketOutcome(tx.id, packet.seq, now, now, Outcome.QUEUE_DROP.value, 0,
                                                   None, None))
        else:
            tx.queue.append(packet)
        next_t = now + traffic.interval_s
        more = ((traffic.max_packets is None or tx.generated < traffic.max_packets)
                and (traffic.duration_s is None or next_t < traffic.duration_s))
        if more:
            self.scheduler.schedule(next_t, lambda t: self._on_generate(t, tx))
        self._try_send(now, tx)

    def _try_send(self, now: float, tx: TransmitterState) -> None:
        if not tx.busy and tx.queue:
            tx.busy = True
            self._start_attempt(now, tx, tx.next_packet(), 0)

    # --- veri gönderimi ------------------------------------------------------
    def _start_attempt(self, now: float, tx: TransmitterState, packet: Packet, attempt: int) -> None:
        violation = tx.duty.would_violate(now)
        if violation and self.enforce_duty_cycle:
            self.scheduler.schedule(tx.duty.next_allowed(now), lambda t: self._start_attempt(t, tx, packet, attempt))
            return
        tx.duty.register(now, self.airtime_s, violation)
        tx.tx_time_s += self.airtime_s
        self._transmit(tx.id, now, self.airtime_s, "data")
        self.scheduler.schedule(now + self.airtime_s,
                                lambda t: self._on_data_received(t, tx, packet, attempt, violation))

    def _on_data_received(self, now: float, tx: TransmitterState, packet: Packet, attempt: int,
                          violation: bool) -> None:
        rx = self.receivers[packet.rx_id]
        sample = self.link(tx.device, rx.device).sample(now)
        result, cfo, n_int = self._receive(tx.device, rx.device, packet.frame, now - self.airtime_s, now, sample)
        duplicate = False
        if result.status == RxStatus.OK:
            key = (tx.id, packet.seq)
            duplicate = key in rx.delivered
            rx.delivered.setdefault(key, now)

        if not self.config.ack.enabled:
            self._emit(now, tx, packet, attempt, sample, result, duplicate, violation, AckStatus.DISABLED, cfo, n_int)
            self._resolve(now, tx, rx, packet, attempt + 1, confirmed_at=None)
            return

        pending = _PendingAttempt(tx, rx, packet, attempt, now, sample, result, duplicate, violation, cfo, n_int)
        tx.pending = pending
        if result.delivered:
            pending.ack_in_flight = True  # dönüş gecikmesi de "yolda" sayılır
            self.scheduler.schedule(now + self.config.ack.turnaround_s, lambda t: self._send_ack(t, pending))
        self.scheduler.schedule(now + self.ack_timeout_s, lambda t: self._on_ack_timeout(t, pending))

    # --- ACK -----------------------------------------------------------------
    def _send_ack(self, now: float, pending: _PendingAttempt) -> None:
        rx = pending.rx
        violation = rx.duty.would_violate(now)
        if violation:
            self.metrics.ack_duty_cycle_violations += 1
            if self.enforce_duty_cycle:
                pending.ack_status = AckStatus.BLOCKED
                pending.ack_in_flight = False
                return
        rx.duty.register(now, self.ack_airtime_s, violation)
        rx.tx_time_s += self.ack_airtime_s
        self._transmit(rx.id, now, self.ack_airtime_s, "ack")
        self.scheduler.schedule(now + self.ack_airtime_s, lambda t: self._on_ack_received(t, pending))

    def _on_ack_received(self, now: float, pending: _PendingAttempt) -> None:
        pending.ack_in_flight = False
        tx = pending.tx
        # Zamana bağlı kanal kapalıyken ACK verinin kanal örneğini kullanır: sabit cihazlarda kanal
        # ~10 ms'de değişmez ve karşılıklıdır (yalnızca gürültü bağımsızdır). Açıkken kanal bu anda örneklenir.
        link = self.link(pending.rx.device, tx.device)
        sample = link.sample(now) if self.channel.time_varying else pending.sample
        frame = build_ack(pending.packet.seq, self.phy.crc_enabled)
        result, _, _ = self._receive(pending.rx.device, tx.device, frame, now - self.ack_airtime_s, now, sample)
        if tx.pending is not pending:
            return  # timeout dolmuş; geç gelen ACK yok sayılır
        if result.status != RxStatus.OK or parse_ack(result.received_frame) != pending.packet.seq & 0xFFFF:
            pending.ack_status = AckStatus.LOST
            return
        tx.pending = None
        tx.listen_time_s += now - pending.rx_time_s
        self._emit_pending(pending, AckStatus.ACKED)
        self._resolve(now, tx, pending.rx, pending.packet, pending.attempt + 1, confirmed_at=now)

    def _on_ack_timeout(self, now: float, pending: _PendingAttempt) -> None:
        tx = pending.tx
        if tx.pending is not pending:
            return  # ACK zamanında alındı
        tx.pending = None
        tx.listen_time_s += now - pending.rx_time_s
        self._emit_pending(pending, AckStatus.LATE if pending.ack_in_flight else pending.ack_status)
        ack = self.config.ack
        packet = pending.packet
        expired = ack.packet_timeout_s is not None and now - packet.created_at_s >= ack.packet_timeout_s
        if pending.attempt < ack.max_retries and not expired:
            backoff = float(self.rng.uniform(0, ack.retry_backoff_max_s)) if ack.retry_backoff_max_s > 0 else 0.0
            self.scheduler.schedule(now + backoff,
                                    lambda t: self._start_attempt(t, tx, packet, pending.attempt + 1))
        else:
            self._resolve(now, tx, pending.rx, packet, pending.attempt + 1, confirmed_at=None)

    # --- kayıt ---------------------------------------------------------------
    def _emit_pending(self, p: _PendingAttempt, ack_status: AckStatus) -> None:
        self._emit(p.rx_time_s, p.tx, p.packet, p.attempt, p.sample, p.result, p.duplicate, p.violation, ack_status,
                   p.freq_offset_hz, p.interferers)

    def _emit(self, rx_time: float, tx: TransmitterState, packet: Packet, attempt: int, sample: LinkSample,
              rx: RxResult, duplicate: bool, violation: bool, ack_status: AckStatus, cfo: float,
              interferers: int) -> None:
        record = PacketRecord(
            time_s=rx_time, seq=packet.seq, tx_id=packet.tx_id, rx_id=packet.rx_id,
            payload_bytes=len(packet.payload), airtime_s=self.airtime_s,
            distance_m=sample.distance_m, environment=self.channel.environment,
            path_loss_db=sample.path_loss_db, shadowing_db=sample.shadowing_db,
            fading_db=sample.fading_db, rssi_dbm=sample.rssi_dbm, noise_dbm=sample.noise_dbm,
            snr_db=sample.snr_db, status=rx.status.value, delivered=rx.delivered,
            success=rx.status == RxStatus.OK, bit_errors=rx.bit_errors,
            bits_compared=rx.bits_compared, symbol_errors=rx.symbol_errors,
            symbols_compared=rx.symbols_compared, latency_s=rx_time - packet.created_at_s,
            retransmissions=attempt, ack_status=ack_status.value, duplicate=duplicate,
            duty_cycle_violation=violation, freq_offset_hz=cfo, doppler_hz=sample.doppler_hz,
            interferers=interferers,
        )
        self.metrics.add(record)
        if self.on_record:
            self.on_record(record)

    def _resolve(self, now: float, tx: TransmitterState, rx: ReceiverState, packet: Packet, attempts: int,
                 confirmed_at: Optional[float]) -> None:
        delivered_at = rx.delivered.pop((tx.id, packet.seq), None)
        if confirmed_at is not None:
            outcome = Outcome.CONFIRMED
        elif delivered_at is not None:
            outcome = Outcome.DELIVERED
        else:
            outcome = Outcome.FAILED
        self.metrics.add_outcome(PacketOutcome(
            tx.id, packet.seq, packet.created_at_s, now, outcome.value, attempts,
            None if delivered_at is None else delivered_at - packet.created_at_s,
            None if confirmed_at is None else confirmed_at - packet.created_at_s,
        ))
        tx.busy = False
        self._try_send(now, tx)

    # --- çalıştırma ----------------------------------------------------------
    def run(self) -> dict:
        realtime = self.config.run.mode == "realtime"
        speed = self.config.run.speed
        wall_start = time.monotonic()
        while not self._stop.is_set():
            if not self._running.is_set():
                paused_at = time.monotonic()
                self._running.wait()
                wall_start += time.monotonic() - paused_at
                continue
            next_t = self.scheduler.peek_time()
            if next_t is None:
                break
            if realtime:
                delay = wall_start + next_t / speed - time.monotonic()
                if delay > 0 and self._stop.wait(min(delay, 0.1)):
                    break
                if delay > 0.1 or not self._running.is_set():
                    continue
            self.scheduler.run_next()
        return self.summary()

    def energy(self) -> dict:
        total = self.metrics.elapsed_s
        lora = self.config.lora
        out = {}
        for tx in self.transmitters.values():
            out[tx.id] = device_energy(tx.tx_time_s, tx.listen_time_s, total, lora.tx_power_dbm, self.phy.bandwidth_hz)
        for rx in self.receivers.values():
            # Alıcı sürekli dinlemededir (yalnızca ACK gönderirken değil).
            out[rx.id] = device_energy(rx.tx_time_s, max(total - rx.tx_time_s, 0.0), total, lora.tx_power_dbm,
                                       self.phy.bandwidth_hz)
        return out

    def live_summary(self) -> dict:
        """Çalışma sürerken başka bir thread'den okunabilen özet.

        Yalnızca sayaçları okur; link oluşturmaz ve rastgele sayı üretecine dokunmaz, bu
        yüzden simülasyonun sonucunu etkilemez. Sayaçlar o anda güncelleniyorsa
        RuntimeError oluşabilir; çağıran bir sonraki denemede tekrar okur.
        """
        s = self.metrics.summary()
        s.update({
            "seed": self.seed, "model": self.config.run.model, "num_transmitters": len(self.transmitters),
            "num_receivers": len(self.receivers), "airtime_s": self.airtime_s, "sensitivity_dbm": self.sensitivity_dbm,
            "ack_timeout_s": self.ack_timeout_s if self.config.ack.enabled else None,
            "tx_energy_j": None, "energy_per_delivered_packet_mj": None,
        })
        return s

    def summary(self) -> dict:
        s = self.metrics.summary()
        energy = self.energy()
        tx_energy = sum(energy[t]["energy_j"] for t in self.transmitters)
        delivered = s["packets_successful"]
        s.update({
            "seed": self.seed,
            "model": self.config.run.model,
            "num_transmitters": len(self.transmitters),
            "num_receivers": len(self.receivers),
            "airtime_s": self.airtime_s,
            "ack_airtime_s": self.ack_airtime_s,
            "ack_timeout_s": self.ack_timeout_s if self.config.ack.enabled else None,
            "sensitivity_dbm": self.sensitivity_dbm,
            "ldro": self.phy.ldro,
            "bitrate_bps": self.phy.bitrate_bps,
            "path_loss_db": self._mean_target_path_loss(),
            "energy": energy,
            "tx_energy_j": tx_energy,
            "energy_per_delivered_packet_mj": tx_energy * 1e3 / delivered if delivered else None,
            "resolved_channel": self.channel.to_dict(),
        })
        return s

    def _mean_target_path_loss(self) -> float:
        """Vericilerin hedef alıcılarına başlangıçtaki ortalama yol kaybı."""
        losses = [self.link(tx.device, self.devices[tx.device.target]).path_loss_db(
                  self.link(tx.device, self.devices[tx.device.target]).distance_m(0.0))
                  for tx in self.transmitters.values()]
        return float(np.mean(losses))
