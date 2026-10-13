"""In-memory state for one imported document."""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path

from vietlayer.core import OcrResult


@dataclass
class DocumentSession:
    source_path: Path
    output_path: Path
    page_index: int = 0
    result: OcrResult | None = None
    corrections: dict[str, dict[str, str | dict]] = field(default_factory=dict)
    dirty: bool = False
    unapplied_count: int = 0
    run_number: int = 0

    def next_output_path(self) -> Path:
        self.run_number += 1
        return self.output_path.with_name(f"{self.output_path.stem}_run_{self.run_number}.pdf")

    @property
    def display_path(self) -> Path:
        return self.result.pdf_path if self.result and self.result.pdf_path else self.source_path

    @property
    def review_regions(self) -> list[dict]:
        if self.result is None:
            return []
        return [region for page in self.result.report for region in page.get("review_regions", [])]
