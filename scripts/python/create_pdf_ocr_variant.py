#!/usr/bin/env python3
"""Create a searchable OCR PDF variant without modifying the source PDF.

The script uses the project-local PyMuPDF runtime in ``work/pdf_tools`` and
Tesseract language data. It preserves every original PDF page and adds an
invisible Unicode text layer generated from full-page OCR.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import sys
from pathlib import Path


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--input", required=True, type=Path)
    parser.add_argument("--output", required=True, type=Path)
    parser.add_argument("--pdf-tools", required=True, type=Path)
    parser.add_argument("--tessdata", required=True, type=Path)
    parser.add_argument("--font", required=True, type=Path)
    parser.add_argument("--languages", default="kor+eng")
    parser.add_argument("--dpi", type=int, default=240)
    parser.add_argument("--progress-every", type=int, default=5)
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    source = args.input.resolve()
    output = args.output.resolve()
    pdf_tools = args.pdf_tools.resolve()
    tessdata = args.tessdata.resolve()
    font_path = args.font.resolve()

    if not source.is_file():
        raise FileNotFoundError(source)
    if output.exists():
        raise FileExistsError(f"refusing to overwrite existing output: {output}")
    if source.parent != output.parent:
        raise ValueError("OCR variant must be written beside its source PDF")
    if not pdf_tools.is_dir() or not tessdata.is_dir() or not font_path.is_file():
        raise FileNotFoundError("pdf-tools, tessdata, or Unicode font is missing")

    sys.path.insert(0, str(pdf_tools))
    import pymupdf  # type: ignore

    source_sha_before = sha256(source)
    document = pymupdf.open(source)
    page_count = document.page_count
    unicode_font = pymupdf.Font(fontfile=str(font_path))
    total_words = 0

    for page_index in range(page_count):
        page = document[page_index]
        textpage = page.get_textpage_ocr(
            language=args.languages,
            dpi=args.dpi,
            full=True,
            tessdata=str(tessdata),
        )
        words = textpage.extractWORDS()
        writer = pymupdf.TextWriter(page.rect)
        for x0, y0, _x1, y1, text, *_rest in words:
            if not text or not text.strip():
                continue
            height = max(1.0, y1 - y0)
            font_size = max(3.0, min(36.0, height * 0.78))
            baseline = pymupdf.Point(x0, y1 - max(0.5, height * 0.12))
            writer.append(
                baseline,
                text.strip() + " ",
                font=unicode_font,
                fontsize=font_size,
            )
            total_words += 1
        writer.write_text(page, render_mode=3, overlay=True)

        current = page_index + 1
        if current == 1 or current == page_count or current % args.progress_every == 0:
            print(
                json.dumps(
                    {
                        "status": "ocr_progress",
                        "page": current,
                        "page_count": page_count,
                        "words_total": total_words,
                    },
                    ensure_ascii=False,
                ),
                flush=True,
            )

    output.parent.mkdir(parents=True, exist_ok=True)
    document.save(output, garbage=4, deflate=True, clean=True)
    document.close()

    source_sha_after = sha256(source)
    if source_sha_before != source_sha_after:
        raise RuntimeError("source PDF SHA-256 changed during OCR processing")

    # PyMuPDF can fail to decode a valid Identity-H ToUnicode map for some
    # Korean fonts even though other PDF readers extract it correctly. Use an
    # independent parser for the searchable-text acceptance check.
    from pypdf import PdfReader  # type: ignore

    check = PdfReader(str(output))
    observed_pages = len(check.pages)
    extracted_characters = sum(
        len(page.extract_text() or "") for page in check.pages
    )
    if observed_pages != page_count:
        raise RuntimeError(
            f"OCR page count mismatch: expected {page_count}, got {observed_pages}"
        )
    if extracted_characters < 100:
        raise RuntimeError(
            f"OCR output has insufficient extractable text: {extracted_characters} chars"
        )

    print(
        json.dumps(
            {
                "status": "completed",
                "input": str(source),
                "output": str(output),
                "page_count": page_count,
                "ocr_words": total_words,
                "extractable_characters": extracted_characters,
                "source_sha256_before": source_sha_before,
                "source_sha256_after": source_sha_after,
                "output_file_size": output.stat().st_size,
                "output_sha256": sha256(output),
                "languages": args.languages,
                "dpi": args.dpi,
            },
            ensure_ascii=False,
        ),
        flush=True,
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
