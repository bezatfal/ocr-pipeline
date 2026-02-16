#!/usr/bin/env bash
set -euo pipefail

PDF="${1:?usage: run_pipeline_tiles.sh /path/to/file.pdf}"
NAME="$(basename "$PDF" | sed 's/\.[Pp][Dd][Ff]$//')"

RENDER_DIR="/mnt/ai/outputs/renders/$NAME"
TILES_DIR="/mnt/ai/outputs/renders/${NAME}_tiles"
OCR_JSON="/mnt/ai/outputs/json/$NAME/doctr_tiles_merged.json"
OCR_TXT="/mnt/ai/outputs/ocr/$NAME/doctr_tiles_merged.txt"
INDEX_DB="/mnt/ai/outputs/search/ocr_index.sqlite"

echo "[1/5] Render PDF → PNG"
python3 render_pdf.py "$PDF" "$RENDER_DIR"

echo "[2/5] Tile page images"
rm -rf "$TILES_DIR"
mkdir -p "$TILES_DIR"

for IMG in "$RENDER_DIR"/*.png; do
  python3 tile_image.py "$IMG" "$TILES_DIR"
done

echo "[3/5] OCR tiles + merge + dedupe"
python3 ocr_doctr_tiles_merge_v2.py \
  "$TILES_DIR" \
  "$OCR_JSON" \
  "$OCR_TXT" \
  0.6

echo "[4/5] Index OCR text (SQLite FTS upsert)"
python3 build_index.py "$OCR_TXT" "$INDEX_DB" "${NAME}_tiles"

echo "[5/5] Done"
echo "PDF:     $PDF"
echo "OCR TXT: $OCR_TXT"
echo "Index:   $INDEX_DB"
