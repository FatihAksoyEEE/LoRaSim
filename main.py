"""Uygulama giriş noktası.

Argümansız çalıştırıldığında grafiksel arayüzü açar; argüman verilirse komut satırı
arayüzünü çalıştırır (bkz. `python main.py --help`).
"""

import sys

if __name__ == "__main__":
    if len(sys.argv) > 1:
        from lorasim.cli import main
    else:
        from lorasim.gui.main_window import main
    sys.exit(main())
