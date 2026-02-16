#!/usr/bin/env bash
set -euo pipefail

PDF="${1:-}"
IOU="${2:-0.6}"

if [[ -z "$PDF" ]]; then
  echo "usage: ./run_pipeline_tiles.sh /path/to/file.pdf [dedupe_iou]"
  exit 2
fi

ROOT="/mnt/ai"
WORK="/mnt/ai/work/ocr-pipeline"
REND="$ROOT/outputs/renders"
JSON="$ROOT/outputs/json"
OCR="$ROOT/outputs/ocr"
INDEX_DB="$ROOT/outputs/search/ocr_index.sqlite"

NAME="$(basename "$PDF")"
NAME="${NAME%.*}"

RENDER_DIR="$REND/$NAME"
JSON_DIR="$JSON/$NAME"
OCR_DIR="$OCR/$NAME"
TILES_BASE="$REND/${NAME}_tiles"

mkdir -p "$RENDER_DIR" "$JSON_DIR" "$OCR_DIR" "$TILES_BASE" "$(dirname "$INDEX_DB")"

echo "[1/4] Render PDF -> PNG"
python3 "$WORK/render_pdf.py" "$PDF" "$RENDER_DIR"

echo "[2/4] Tile + OCR merge each page (docTR)"
COMBINED_TXT="$OCR_DIR/doctr_tiles_merged_all.txt"
: > "$COMBINED_TXT"

shopt -s nullglob
pages=("$RENDER_DIR"/page_*.png)
if [[ ${#pages[@]} -eq 0 ]]; then
  echo "No rendered pages found in $RENDER_DIR"
  exit 1
fi

for page in "${pages[@]}"; do
  base="$(basename "$page" .png)"
  tile_dir="$TILES_BASE/$base"
  out_json="$JSON_DIR/${base}_tiles_merged.json"
  out_txt="$OCR_DIR/${base}_tiles_merged.txt"

  rm -rf "$tile_dir"
  mkdir -p "$tile_dir"

  python3 "$WORK/tile_image.py" "$page" "$tile_dir"
  python3 "$WORK/ocr_doctr_tiles_merge_v2.py" "$tile_dir" "$out_json" "$out_txt" "$IOU"

  echo "" >> "$COMBINED_TXT"
  echo "===== $base =====" >> "$COMBINED_TXT"
  cat "$out_txt" >> "$COMBINED_TXT"
done

echo "[3/4] Index combined OCR text (SQLite FTS5)"
python3 "$WORK/build_index.py" "$COMBINED_TXT" "$INDEX_DB" "${NAME}_tiles"

echo "[4/4] Done"
echo "Renders:   $RENDER_DIR"
echo "Tiles:    $TILES_BASE"
echo "OCR out:   $OCR_DIR"
echo "Index DB:  $INDEX_DB"
