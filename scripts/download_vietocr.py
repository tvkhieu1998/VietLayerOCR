"""Tải checkpoint VietOCR chính thức, kiểm SHA-256 trước khi sử dụng."""

from __future__ import annotations

import argparse
import hashlib
import tempfile
import urllib.request
from pathlib import Path


DEFAULT_MODEL_DIR = Path(__file__).resolve().parents[1] / "models" / "vietocr"
MODELS = {
    "transformer": (
        "vgg_transformer.pth",
        "380512193a8b6cbf6fad80deacdc9b6939d10d473d199892fc6408d13775ea59",
    ),
    "seq2seq": (
        "vgg_seq2seq.pth",
        "0921503a41375a0584268e23ef3d414ea478a8fe8777865c7745d38f2d0bc5db",
    ),
}


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def download_model(model: str, directory: Path = DEFAULT_MODEL_DIR) -> Path:
    """Tải một checkpoint; không dùng file nếu mã kiểm tra khác bản đã thử."""
    filename, expected_hash = MODELS[model]
    directory = Path(directory).expanduser().resolve()
    directory.mkdir(parents=True, exist_ok=True)
    destination = directory / filename
    if destination.is_file() and sha256_file(destination) == expected_hash:
        return destination

    url = f"https://vocr.vn/data/vietocr/{filename}"
    with tempfile.NamedTemporaryFile(dir=directory, prefix=f".{filename}.", delete=False) as temporary:
        temporary_path = Path(temporary.name)
    try:
        with urllib.request.urlopen(url, timeout=120) as response, temporary_path.open("wb") as stream:
            for chunk in iter(lambda: response.read(1024 * 1024), b""):
                stream.write(chunk)
        if sha256_file(temporary_path) != expected_hash:
            raise ValueError(f"Checkpoint {filename} không khớp SHA-256 đã kiểm chứng.")
        temporary_path.replace(destination)
    finally:
        temporary_path.unlink(missing_ok=True)
    return destination


def main() -> None:
    parser = argparse.ArgumentParser(description="Tải checkpoint VietOCR về máy")
    parser.add_argument("--model", choices=tuple(MODELS), default="transformer")
    parser.add_argument("--directory", type=Path, default=DEFAULT_MODEL_DIR)
    arguments = parser.parse_args()
    print(download_model(arguments.model, arguments.directory))


if __name__ == "__main__":
    main()
