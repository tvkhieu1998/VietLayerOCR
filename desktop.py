"""Launch the VietLayerOCR desktop application with its project environment."""

import os
import sys
import multiprocessing
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parent
BUNDLE_ROOT = Path(getattr(sys, "_MEIPASS", PROJECT_ROOT))
ENVIRONMENT_BIN = PROJECT_ROOT / ".venv" / ("Scripts" if os.name == "nt" else "bin")
PROJECT_PYTHON = ENVIRONMENT_BIN / ("python.exe" if os.name == "nt" else "python")
GHOSTSCRIPT_BIN = PROJECT_ROOT / ".venv" / "ghostscript" / "bin"
GHOSTSCRIPT_SHARE = PROJECT_ROOT / ".venv" / "ghostscript" / "share" / "ghostscript"


def _prepare_environment() -> None:
    if not getattr(sys, "frozen", False) and PROJECT_PYTHON.is_file() and Path(sys.executable).resolve() != PROJECT_PYTHON.resolve():
        os.execv(str(PROJECT_PYTHON), [str(PROJECT_PYTHON), str(Path(__file__).resolve()), *sys.argv[1:]])
    if not getattr(sys, "frozen", False) and ENVIRONMENT_BIN.is_dir():
        os.environ["PATH"] = str(ENVIRONMENT_BIN) + os.pathsep + os.environ.get("PATH", "")
    if not getattr(sys, "frozen", False) and GHOSTSCRIPT_BIN.is_dir():
        os.environ["PATH"] = str(GHOSTSCRIPT_BIN) + os.pathsep + os.environ["PATH"]
        ghostscript_libraries = sorted(GHOSTSCRIPT_SHARE.glob("*/lib"))
        if ghostscript_libraries:
            os.environ["GS_LIB"] = str(ghostscript_libraries[-1])
    if getattr(sys, "frozen", False):
        search_paths = []
        bundled_ghostscript = BUNDLE_ROOT / "ghostscript"
        if (bundled_ghostscript / "bin" / "gs").is_file():
            search_paths.append(str(bundled_ghostscript / "bin"))
            libraries = sorted((bundled_ghostscript / "share" / "ghostscript").glob("*/lib"))
            if libraries:
                os.environ["GS_LIB"] = str(libraries[-1])
        if sys.platform == "darwin":
            search_paths.extend(("/opt/homebrew/bin", "/usr/local/bin", "/opt/local/bin"))
        os.environ["PATH"] = os.pathsep.join((*search_paths, os.environ.get("PATH", "")))
    try:
        import PySide6  # noqa: F401
    except ModuleNotFoundError as error:
        if error.name != "PySide6":
            raise
        raise SystemExit(
            "Thiếu PySide6. Tạo .venv Python 3.12 và cài requirements.txt theo README.md."
        ) from error


def main() -> int:
    _prepare_environment()
    if sys.argv[1:2] == ["--ocr-worker"]:
        from ocrmypdf.__main__ import run

        return int(run(sys.argv[2:]))
    if "--check" in sys.argv[1:]:
        import PySide6

        print(f"Python: {sys.executable}")
        print(f"PySide6: {PySide6.__version__}")
        return 0
    from PySide6.QtGui import QIcon
    from PySide6.QtWidgets import QApplication

    from desktop.main_window import MainWindow

    application = QApplication(sys.argv)
    application.setWindowIcon(QIcon(str(BUNDLE_ROOT / "assets" / "app_icon.png")))
    window = MainWindow()
    window.show()
    return application.exec()


if __name__ == "__main__":
    multiprocessing.freeze_support()
    raise SystemExit(main())
