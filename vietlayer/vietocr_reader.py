"""Load upstream VietOCR checkpoints locally, without a model server."""

from __future__ import annotations

import threading
from pathlib import Path

from PIL import Image


_LOCK = threading.RLock()
_READERS: dict[tuple[str, Path], "VietOcrReader"] = {}
_CONFIG_NAMES = {"transformer": "vgg-transformer", "seq2seq": "vgg-seq2seq"}


class VietOcrReader:
    def __init__(self, model: str, model_dir: Path):
        if model not in _CONFIG_NAMES:
            raise ValueError("Invalid VietOCR model.")
        import torch
        import yaml
        from vietocr.tool.translate import build_model, process_input

        self._torch = torch
        self._process_input = process_input
        model_dir = Path(model_dir).expanduser().resolve()
        config_name = _CONFIG_NAMES[model]
        config = yaml.safe_load((model_dir / "base.yml").read_text(encoding="utf-8"))
        config.update(yaml.safe_load((model_dir / f"{config_name}.yml").read_text(encoding="utf-8")))
        config["device"] = "cpu"
        config["cnn"]["pretrained"] = False
        self._config = config
        torch.set_num_threads(4)
        self._model, self._vocab = build_model(config)
        weight_path = model_dir / f"{config_name.replace('-', '_')}.pth"
        self._model.load_state_dict(torch.load(weight_path, map_location="cpu", weights_only=True))
        self._model.eval()

    def read(self, image: Image.Image, max_tokens: int = 256) -> dict:
        from torch.nn.functional import log_softmax

        dataset = self._config["dataset"]
        model_input = self._process_input(
            image.convert("RGB"),
            dataset["image_height"],
            dataset["image_min_width"],
            dataset["image_max_width"],
        )
        with self._torch.inference_mode():
            memory = self._model.transformer.forward_encoder(self._model.cnn(model_input))
            token_ids = [1]
            token_log_probabilities = []
            while len(token_ids) <= max_tokens:
                output, memory = self._model.transformer.forward_decoder(
                    self._torch.LongTensor([[token_id] for token_id in token_ids]), memory
                )
                probabilities = log_softmax(output[0, -1].float(), dim=-1)
                token_id = int(self._torch.argmax(probabilities))
                token_ids.append(token_id)
                if token_id == 2:
                    break
                token_log_probabilities.append(float(probabilities[token_id]))
        return {
            "text": self._vocab.decode(token_ids).strip(),
            "min_log_probability": min(token_log_probabilities, default=None),
            "reached_token_limit": token_ids[-1] != 2,
        }


def read_image(image: Image.Image, model: str, model_dir: Path) -> dict:
    """Cache the model within each OCRmyPDF worker process."""
    if model not in _CONFIG_NAMES:
        raise ValueError("Invalid VietOCR model.")
    key = (model, Path(model_dir).expanduser().resolve())
    with _LOCK:
        if key not in _READERS:
            _READERS[key] = VietOcrReader(*key)
        return _READERS[key].read(image)
