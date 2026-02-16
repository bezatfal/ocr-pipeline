# OCR Pipeline (docTR)

PDF -> PNG render -> (optional tiling) -> docTR OCR -> JSON/TXT -> SQLite FTS5 index

Scripts:
- render_pdf.py
- tile_image.py
- ocr_doctr.py / ocr_doctr_dir.py
- ocr_doctr_tiles_merge.py
- build_index.py / search_index.py
- run_pipeline.sh
