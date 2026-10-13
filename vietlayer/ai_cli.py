"""Read selected OCR crops through an authenticated provider CLI."""

from __future__ import annotations

import json
import subprocess
import tempfile
from pathlib import Path


class AiCliError(RuntimeError):
    """A provider CLI could not return usable OCR review data."""


class CodexCliProvider:
    def __init__(self, executable: str = "codex", *, model: str | None = None,
                 effort: str | None = None) -> None:
        self.executable = executable
        self.model = model
        self.effort = effort

    def review(self, regions: list[dict], timeout_seconds: int = 180) -> dict[str, dict]:
        """Return OCR readings keyed by the requested region IDs."""
        if not regions:
            return {}
        ids = [region["id"] for region in regions]
        if len(ids) != len(set(ids)):
            raise ValueError("Region IDs must be unique within one request")
        schema = {
            "type": "object", "additionalProperties": False,
            "properties": {"regions": {
                "type": "array", "items": {
                    "type": "object", "additionalProperties": False,
                    "properties": {"id": {"type": "string", "enum": ids},
                                   "text": {"type": "string"}, "uncertain": {"type": "boolean"}},
                    "required": ["id", "text", "uncertain"],
                },
            }},
            "required": ["regions"],
        }
        with tempfile.TemporaryDirectory(prefix="vietlayer-ai-") as temporary:
            folder = Path(temporary)
            image_paths = []
            for index, region in enumerate(regions, 1):
                path = folder / f"region-{index:02d}.png"
                region["crop"].convert("RGB").save(path)
                image_paths.append(path)
            schema_path = folder / "schema.json"
            output_path = folder / "answer.json"
            schema_path.write_text(json.dumps(schema, ensure_ascii=False), encoding="utf-8")
            prompt = (
                "Read only the attached document crops. Each image corresponds to the numbered "
                "entry below. Transcribe visible Vietnamese text exactly, without expanding "
                "abbreviations or guessing missing characters. Tesseract and VietOCR are hints, "
                "not ground truth. Return one JSON regions entry for each image, retaining its id. "
                "Set uncertain=true if any part is unclear. Do not use tools or inspect other files.\n"
                + json.dumps([
                    {"image": index, "id": region["id"], "tesseract": region["tesseract"],
                     "vietocr": region["vietocr"]}
                    for index, region in enumerate(regions, 1)
                ], ensure_ascii=False)
            )
            command = [self.executable, "exec", "-", "--sandbox", "read-only",
                       "--ephemeral", "--skip-git-repo-check", "-C", str(folder),
                       "--output-schema", str(schema_path), "-o", str(output_path)]
            if self.model:
                command += ["--model", self.model]
            if self.effort:
                command += ["--config", f"model_reasoning_effort={self.effort}"]
            for path in image_paths:
                command += ["-i", str(path)]
            try:
                completed = subprocess.run(command, input=prompt, text=True,
                                           capture_output=True, timeout=timeout_seconds, cwd=folder)
            except (OSError, subprocess.TimeoutExpired) as error:
                raise AiCliError(f"Codex CLI không hoàn thành: {type(error).__name__}") from error
            if completed.returncode != 0 or not output_path.is_file():
                raise AiCliError(f"Codex CLI không trả kết quả (mã {completed.returncode})")
            try:
                payload = json.loads(output_path.read_text(encoding="utf-8"))
                entries = payload["regions"]
                if not isinstance(entries, list):
                    raise ValueError("regions must be a list")
                result = {}
                for entry in entries:
                    identifier = entry["id"]
                    if identifier not in ids or identifier in result:
                        raise ValueError("Unexpected or duplicate region ID")
                    if not isinstance(entry["text"], str) or not isinstance(entry["uncertain"], bool):
                        raise ValueError("Invalid region text or uncertainty")
                    result[identifier] = {"text": entry["text"], "uncertain": entry["uncertain"]}
                return result
            except (ValueError, KeyError, TypeError) as error:
                raise ValueError("Codex CLI trả JSON không hợp lệ cho vùng OCR") from error


class ClaudeCliProvider:
    def __init__(self, executable: str = "claude", *, model: str | None = None,
                 effort: str | None = None) -> None:
        self.executable = executable
        self.model = model
        self.effort = effort

    def review(self, regions: list[dict], timeout_seconds: int = 180) -> dict[str, dict]:
        if not regions:
            return {}
        ids = [region["id"] for region in regions]
        if len(ids) != len(set(ids)):
            raise ValueError("Region IDs must be unique within one request")
        schema = {
            "type": "object", "additionalProperties": False,
            "properties": {"regions": {"type": "array", "items": {
                "type": "object", "additionalProperties": False,
                "properties": {"id": {"type": "string", "enum": ids},
                               "text": {"type": "string"}, "uncertain": {"type": "boolean"}},
                "required": ["id", "text", "uncertain"],
            }}},
            "required": ["regions"],
        }
        with tempfile.TemporaryDirectory(prefix="vietlayer-ai-") as temporary:
            folder = Path(temporary)
            for index, region in enumerate(regions, 1):
                region["crop"].convert("RGB").save(folder / f"region-{index:02d}.png")
            prompt = (
                "Use the Read tool to inspect only the listed image files in this directory. "
                "Transcribe visible Vietnamese text exactly; do not guess missing characters. "
                "Tesseract and VietOCR are hints, not ground truth. Return one JSON regions "
                "entry per image with the same id; set uncertain=true if any part is unclear.\n"
                + json.dumps([
                    {"image_file": str(folder / f"region-{index:02d}.png"), "id": region["id"],
                     "tesseract": region["tesseract"], "vietocr": region["vietocr"]}
                    for index, region in enumerate(regions, 1)
                ], ensure_ascii=False)
            )
            command = [self.executable, "-p", prompt, "--output-format", "json",
                       "--json-schema", json.dumps(schema, ensure_ascii=False),
                       "--safe-mode", "--restricted", "--tools", "Read",
                       "--allowedTools", "Read", "--permission-mode", "dontAsk",
                       "--no-session-persistence"]
            if self.model:
                command += ["--model", self.model]
            if self.effort:
                command += ["--effort", self.effort]
            try:
                completed = subprocess.run(command, capture_output=True, text=True,
                                           timeout=timeout_seconds, cwd=folder)
            except (OSError, subprocess.TimeoutExpired) as error:
                raise AiCliError(f"Claude CLI không hoàn thành: {type(error).__name__}") from error
            if completed.returncode != 0:
                raise AiCliError(f"Claude CLI không trả kết quả (mã {completed.returncode})")
            try:
                payload = json.loads(completed.stdout)["structured_output"]
                entries = payload["regions"]
                if not isinstance(entries, list):
                    raise ValueError("regions must be a list")
                result = {}
                for entry in entries:
                    identifier = entry["id"]
                    if identifier not in ids or identifier in result:
                        raise ValueError("Unexpected or duplicate region ID")
                    if not isinstance(entry["text"], str) or not isinstance(entry["uncertain"], bool):
                        raise ValueError("Invalid region text or uncertainty")
                    result[identifier] = {"text": entry["text"], "uncertain": entry["uncertain"]}
                return result
            except (ValueError, KeyError, TypeError) as error:
                raise AiCliError("Claude CLI trả JSON không hợp lệ cho vùng OCR") from error
