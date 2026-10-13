"""Send the existing OCR review batches through an AI HTTP API."""

from __future__ import annotations

import base64
import io
import json
import re
from dataclasses import dataclass, field

import requests


DEFAULT_MODELS = {
    "openai-api": "gpt-5-mini",
    "anthropic-api": "claude-sonnet-5",
    "gemini-api": "gemini-3.8-flash",
}


class AiApiError(RuntimeError):
    """An API call did not return usable OCR review data."""


def _png_base64(image) -> str:
    buffer = io.BytesIO()
    image.convert("RGB").save(buffer, format="PNG")
    return base64.b64encode(buffer.getvalue()).decode("ascii")


def _instructions(regions: list[dict]) -> str:
    hints = [{"id": region["id"], "tesseract": region["tesseract"],
              "vietocr": region["vietocr"]} for region in regions]
    return (
        "Read only the attached document crops. Each following image has an id. "
        "Transcribe visible Vietnamese text exactly, without expanding abbreviations "
        "or guessing missing characters. Tesseract and VietOCR are hints, not ground truth. "
        "Return one JSON object with a regions array containing one entry per image: "
        '{"regions":[{"id":"...","text":"...","uncertain":false}]}. '
        "Keep every id unchanged; set uncertain=true if any part is unclear.\n"
        + json.dumps(hints, ensure_ascii=False)
    )


def _json_from_text(text: str) -> dict:
    if not isinstance(text, str):
        raise AiApiError("API AI không trả nội dung chữ.")
    cleaned = re.sub(r"^```(?:json)?\s*", "", text.strip(), flags=re.IGNORECASE)
    cleaned = re.sub(r"\s*```$", "", cleaned).strip()
    try:
        result = json.loads(cleaned)
    except ValueError:
        match = re.search(r"\{[\s\S]*\}", cleaned)
        result = json.loads(match.group(0)) if match else None
    if not isinstance(result, dict):
        raise AiApiError("API AI không trả JSON dạng đối tượng.")
    return result


def _validate_results(payload: dict, expected_ids: list[str]) -> dict[str, dict]:
    entries = payload.get("regions")
    if not isinstance(entries, list):
        raise AiApiError("API AI không trả danh sách vùng OCR.")
    result = {}
    for entry in entries:
        if not isinstance(entry, dict):
            raise AiApiError("API AI trả vùng OCR không hợp lệ.")
        identifier = entry.get("id")
        if identifier not in expected_ids or identifier in result:
            raise AiApiError("API AI trả mã vùng lạ hoặc trùng.")
        if not isinstance(entry.get("text"), str) or not isinstance(entry.get("uncertain"), bool):
            raise AiApiError("API AI trả chữ hoặc trạng thái không hợp lệ.")
        result[identifier] = {"text": entry["text"], "uncertain": entry["uncertain"]}
    return result


@dataclass(frozen=True)
class ApiAiProvider:
    provider: str
    api_key: str = field(repr=False)
    model: str | None = None

    def review(self, regions: list[dict], timeout_seconds: int = 180) -> dict[str, dict]:
        if not regions:
            return {}
        if self.provider not in DEFAULT_MODELS or not self.api_key.strip():
            raise AiApiError("Chưa cấu hình provider hoặc API key.")
        ids = [region["id"] for region in regions]
        if len(ids) != len(set(ids)):
            raise ValueError("Region IDs must be unique within one request")
        images = [(region["id"], _png_base64(region["crop"])) for region in regions]
        model = self.model or DEFAULT_MODELS[self.provider]
        instructions = _instructions(regions)
        try:
            if self.provider == "openai-api":
                text = self._review_openai(model, instructions, images, timeout_seconds)
            elif self.provider == "anthropic-api":
                text = self._review_anthropic(model, instructions, images, timeout_seconds)
            else:
                text = self._review_gemini(model, instructions, images, timeout_seconds)
            return _validate_results(_json_from_text(text), ids)
        except requests.HTTPError as error:
            status = error.response.status_code if error.response is not None else "?"
            raise AiApiError(f"{self.provider} từ chối yêu cầu (HTTP {status}).") from error
        except (requests.RequestException, ValueError, KeyError, IndexError, TypeError) as error:
            raise AiApiError(f"API AI không trả kết quả hợp lệ ({type(error).__name__}).") from error

    def _review_openai(self, model: str, instructions: str,
                       images: list[tuple[str, str]], timeout: int) -> str:
        content = [{"type": "text", "text": instructions}]
        for identifier, image in images:
            content += [{"type": "text", "text": f"Vùng {identifier}:"},
                        {"type": "image_url", "image_url": {
                            "url": f"data:image/png;base64,{image}", "detail": "high"}}]
        payload = {"model": model, "max_completion_tokens": max(6000, 400 * len(images)),
                   "messages": [{"role": "user", "content": content}]}
        url = "https://api.openai.com/v1/chat/completions"
        headers = {"authorization": f"Bearer {self.api_key}", "content-type": "application/json"}
        response = requests.post(url, headers=headers, json=payload, timeout=timeout)
        if response.status_code == 400 and "max_completion_tokens" in response.text:
            payload["max_tokens"] = payload.pop("max_completion_tokens")
            response = requests.post(url, headers=headers, json=payload, timeout=timeout)
        response.raise_for_status()
        content = response.json()["choices"][0]["message"]["content"]
        if isinstance(content, list):
            return "".join(part.get("text", "") for part in content if isinstance(part, dict))
        return content

    def _review_anthropic(self, model: str, instructions: str,
                          images: list[tuple[str, str]], timeout: int) -> str:
        content = [{"type": "text", "text": instructions}]
        for identifier, image in images:
            content += [{"type": "text", "text": f"Vùng {identifier}:"},
                        {"type": "image", "source": {
                            "type": "base64", "media_type": "image/png", "data": image}}]
        response = requests.post(
            "https://api.anthropic.com/v1/messages",
            headers={"x-api-key": self.api_key, "anthropic-version": "2023-06-01",
                     "content-type": "application/json"},
            json={"model": model, "max_tokens": max(6000, 400 * len(images)),
                  "messages": [{"role": "user", "content": content}]},
            timeout=timeout,
        )
        response.raise_for_status()
        return "".join(part.get("text", "") for part in response.json()["content"]
                       if part.get("type") == "text")

    def _review_gemini(self, model: str, instructions: str,
                       images: list[tuple[str, str]], timeout: int) -> str:
        parts = [{"text": instructions}]
        for identifier, image in images:
            parts += [{"text": f"Vùng {identifier}:"},
                      {"inline_data": {"mime_type": "image/png", "data": image}}]
        response = requests.post(
            f"https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent",
            headers={"x-goog-api-key": self.api_key, "content-type": "application/json"},
            json={"contents": [{"role": "user", "parts": parts}],
                  "generationConfig": {"maxOutputTokens": max(6000, 400 * len(images))}},
            timeout=timeout,
        )
        response.raise_for_status()
        return "".join(part.get("text", "") for part in response.json()["candidates"][0]["content"]["parts"]
                       if "text" in part)
