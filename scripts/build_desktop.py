"""Build the native VietLayerOCR desktop bundle on the current operating system."""

from __future__ import annotations

import importlib.util
import os
import shutil
import subprocess
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
NAME = "VietLayerOCR"


def build() -> Path:
    if sys.version_info[:2] != (3, 12):
        raise SystemExit("Build bằng Python 3.12 theo requirements.txt.")
    if importlib.util.find_spec("PyInstaller") is None:
        raise SystemExit("Thiếu PyInstaller. Cài requirements-build.txt vào .venv trước khi build.")

    model_dir = ROOT / "models" / "vietocr"
    required_models = ("base.yml", "vgg-transformer.yml", "vgg_transformer.pth")
    missing = [name for name in required_models if not (model_dir / name).is_file()]
    if missing:
        raise SystemExit("Thiếu VietOCR model: " + ", ".join(missing) + ". Chạy scripts/download_vietocr.py trước.")

    icon = ROOT / "assets" / ("app_icon.icns" if sys.platform == "darwin" else "app_icon.png")
    if not icon.is_file():
        raise SystemExit(f"Thiếu icon: {icon}")

    command = [
        sys.executable, "-m", "PyInstaller", "--noconfirm", "--clean",
        "--onedir", "--windowed", "--name", NAME,
        "--specpath", str(ROOT / "build"),
        "--icon", str(icon),
        "--add-data", f"{ROOT / 'assets' / 'app_icon.png'}{os.pathsep}assets",
        "--add-data", f"{ROOT / 'ocr_plugin.py'}{os.pathsep}.",
        "--add-data", f"{model_dir}{os.pathsep}models/vietocr",
        "--hidden-import", "ocr_plugin",
        "--hidden-import", "ocrmypdf.__main__",
        "--collect-all", "ocrmypdf",
        "--collect-all", "vietocr",
        "--collect-all", "rapidocr",
        "--collect-submodules", "vietlayer",
        str(ROOT / "desktop.py"),
    ]
    if sys.platform == "darwin":
        command[7:7] = ["--osx-bundle-identifier", "org.vietlayerocr.desktop"]
        local_ghostscript = ROOT / ".venv" / "ghostscript"
        if (local_ghostscript / "bin" / "gs").is_file():
            command[-1:-1] = ["--add-data", f"{local_ghostscript}{os.pathsep}ghostscript"]
    subprocess.run(command, cwd=ROOT, check=True)

    output = ROOT / "dist" / (f"{NAME}.app" if sys.platform == "darwin" else NAME)
    if not output.exists():
        raise SystemExit(f"PyInstaller không tạo được {output}")
    if sys.platform == "win32":
        archive = Path(shutil.make_archive(str(ROOT / "dist" / f"{NAME}-windows"), "zip", ROOT / "dist", NAME))
        print(f"Windows ZIP: {archive}")
    print(f"Desktop app: {output}")
    return output


if __name__ == "__main__":
    build()
