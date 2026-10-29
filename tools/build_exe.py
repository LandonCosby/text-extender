"""Package the app as a single TextExtender.exe (plan step 11).

    python -m pip install -r requirements-dev.txt
    python tools/build_exe.py

The result is dist/TextExtender.exe, which runs without Python installed. It uses the
same settings file (%APPDATA%\\TextExtender\\config.json) as `python main.py`.
"""

import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from extender.tray import make_icon_image  # noqa: E402

# pynput and pystray pick their Windows code when they're imported, so PyInstaller
# can't see it and has to be told.
HIDDEN_IMPORTS = ["pynput.keyboard._win32", "pynput.mouse._win32", "pystray._win32"]


def main():
    build = ROOT / "build"
    build.mkdir(exist_ok=True)
    icon = build / "TextExtender.ico"
    make_icon_image(size=256).save(icon, sizes=[(16, 16), (24, 24), (32, 32), (48, 48), (64, 64), (256, 256)])
    command = [
        sys.executable, "-m", "PyInstaller", str(ROOT / "main.py"),
        "--name", "TextExtender",
        "--onefile",
        "--windowed",  # no terminal window, like pythonw
        "--icon", str(icon),
        "--distpath", str(ROOT / "dist"),
        "--workpath", str(build),
        "--specpath", str(build),
        "--noconfirm",
    ]
    for module in HIDDEN_IMPORTS:
        command += ["--hidden-import", module]
    subprocess.run(command, check=True)
    print(f"\nBuilt {ROOT / 'dist' / 'TextExtender.exe'}")


if __name__ == "__main__":
    main()
