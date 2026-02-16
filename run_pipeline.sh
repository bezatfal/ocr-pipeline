#!/usr/bin/env bash
set -euo pipefail

PDF="${1:?usage: run_pipeline.sh /path/to/file.pdf}"
NAME="$(basename "$PDF" | sed 's/\.[Pp][Dd][Ff]$//')"

RENDER_DIR="/mnt/ai/outputs/renders/$NAME"
OCR_JSON_DIR="/mnt/ai/outputs/json/$NAME"
OCR_TXT_DIR="/mnt/ai/outputs/ocr/$NAME"

mkdir -p "$RENDER_DIR" "$OCR_JSON_DIR" "$OCR_TXT_DIR"

echo "[1/3] Render PDF -> PNG"
python3 render_pdf.py "$PDF" "$RENDER_DIR" 4.0

echo "[2/3] OCR PNGs -> JSON/TXT (docTR)"
python3 ocr_doctr_dir.py "$RENDER_DIR" "$OCR_JSON_DIR/doctr_pages.json" "$OCR_TXT_DIR/doctr_pages.txt"

echo "[3/3] Index OCR text (SQLite FTS5)"
python3 build_index.py "$OCR_TXT_DIR/doctr_pages.txt" "/mnt/ai/outputs/search/ocr_index.sqlite" "$NAME"

echo "Done"
echo "Renders: $RENDER_DIR"
echo "OCR out:  $OCR_TXT_DIR"
echo "Index:    /mnt/ai/outputs/search/ocr_index.sqlite"
echo "PaddleOCR not wired yet." > "$OCR_TXT_DIR/README.txt"

echo "[3/3] Done"
echo "Renders: $RENDER_DIR"
echo "OCR out:  $OCR_TXT_DIR"
