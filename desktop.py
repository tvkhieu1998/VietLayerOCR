"""Launch the VietLayerOCR desktop application with its project environment."""

import os
import sys
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parent
ENVIRONMENT_BIN = PROJECT_ROOT / ".venv" / ("Scripts" if os.name == "nt" else "bin")
PROJECT_PYTHON = ENVIRONMENT_BIN / ("python.exe" if os.name == "nt" else "python")
GHOSTSCRIPT_BIN = PROJECT_ROOT / ".venv" / "ghostscript" / "bin"
GHOSTSCRIPT_SHARE = PROJECT_ROOT / ".venv" / "ghostscript" / "share" / "ghostscript"


def _prepare_environment() -> None:
    if PROJECT_PYTHON.is_file() and Path(sys.executable).resolve() != PROJECT_PYTHON.resolve():
        os.execv(str(PROJECT_PYTHON), [str(PROJECT_PYTHON), str(Path(__file__).resolve()), *sys.argv[1:]])
    if ENVIRONMENT_BIN.is_dir():
        os.environ["PATH"] = str(ENVIRONMENT_BIN) + os.pathsep + os.environ.get("PATH", "")
    if GHOSTSCRIPT_BIN.is_dir():
        os.environ["PATH"] = str(GHOSTSCRIPT_BIN) + os.pathsep + os.environ["PATH"]
        ghostscript_libraries = sorted(GHOSTSCRIPT_SHARE.glob("*/lib"))
        if ghostscript_libraries:
            os.environ["GS_LIB"] = str(ghostscript_libraries[-1])
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
    if "--check" in sys.argv[1:]:
        import PySide6

        print(f"Python: {sys.executable}")
        print(f"PySide6: {PySide6.__version__}")
        return 0
    from PySide6.QtWidgets import QApplication

    from desktop.main_window import MainWindow

    application = QApplication(sys.argv)
    window = MainWindow()
    window.show()
    return application.exec()


if __name__ == "__main__":
    raise SystemExit(main())
