"""Ortak pytest ayarları.

Linux'ta (ekransız Qt) QApplication yorumlayıcı kapanırken çöp toplayıcıya kalırsa PySide6
`none_dealloc` hatasıyla çöküyor; testler geçse bile süreç 134 koduyla bitiyor. Bu yüzden
oturum sonunda, yorumlayıcı henüz çalışırken pencereler kapatılıp QApplication açıkça
kapatılıyor.
"""

import gc
import sys


def pytest_sessionfinish(session, exitstatus):
    if "PySide6.QtWidgets" not in sys.modules:
        return
    from PySide6.QtWidgets import QApplication

    app = QApplication.instance()
    if app is None:
        return
    for w in QApplication.topLevelWidgets():
        w.close()
    app.processEvents()
    gc.collect()
    app.shutdown()
