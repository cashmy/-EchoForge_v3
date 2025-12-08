"""Unit tests for EF-03 extraction service helpers."""

from __future__ import annotations

from pathlib import Path

import pytest

from backend.app.domain.ef03_extraction import (
    DocumentExtractionError,
    extract_document,
)

pytestmark = [pytest.mark.ef03]


def test_extract_document_docx(tmp_path: Path) -> None:
    docx = pytest.importorskip("docx")

    document = docx.Document()  # type: ignore[attr-defined]
    document.add_paragraph("Alpha paragraph")
    document.add_paragraph("Beta paragraph")
    path = tmp_path / "sample.docx"
    document.save(path)

    result = extract_document(
        str(path),
        mime_type="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
    )

    assert result.metadata["converter"] == "python-docx"
    assert len(result.segments or []) == 2
    assert result.segments[0]["text"] == "Alpha paragraph"
    assert result.segments[1]["text"] == "Beta paragraph"


def test_extract_document_pdf_uses_pdfminer(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    pdfminer_high_level = pytest.importorskip("pdfminer.high_level")
    path = tmp_path / "sample.pdf"
    path.write_text("First page\fSecond page", encoding="utf-8")

    def fake_extract_text(file_path: str, **kwargs):  # type: ignore[no-untyped-def]
        assert file_path == str(path)
        return path.read_text(encoding="utf-8")

    monkeypatch.setattr(pdfminer_high_level, "extract_text", fake_extract_text)

    result = extract_document(str(path), mime_type="application/pdf")

    assert result.metadata["converter"] == "pdfminer"
    assert [segment["label"] for segment in result.segments or []] == [
        "page_1",
        "page_2",
    ]


def test_extract_document_pdf_without_text_requires_ocr(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    pdfminer_high_level = pytest.importorskip("pdfminer.high_level")
    path = tmp_path / "blank.pdf"
    path.write_bytes(b"%PDF-FAKE")

    def fake_extract_text(*_args, **_kwargs):  # type: ignore[no-untyped-def]
        return " \n\t"

    monkeypatch.setattr(pdfminer_high_level, "extract_text", fake_extract_text)

    with pytest.raises(DocumentExtractionError) as excinfo:
        extract_document(str(path), mime_type="application/pdf", ocr_mode="auto")

    assert excinfo.value.code == "ocr_required"
    assert excinfo.value.retryable is True

    with pytest.raises(DocumentExtractionError) as excinfo_off:
        extract_document(str(path), mime_type="application/pdf", ocr_mode="off")

    assert excinfo_off.value.code == "ocr_required"
    assert excinfo_off.value.retryable is False
