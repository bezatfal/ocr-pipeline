import os, re, sys, json
from pathlib import Path
from doctr.io import DocumentFile
from doctr.models import ocr_predictor

TILE_RE = re.compile(r".*_x(\d+)_y(\d+)_t\d+\.png$", re.IGNORECASE)

def iou(a, b):
    ax1, ay1, ax2, ay2 = a
    bx1, by1, bx2, by2 = b
    ix1, iy1 = max(ax1, bx1), max(ay1, by1)
    ix2, iy2 = min(ax2, bx2), min(ay2, by2)
    iw, ih = max(0, ix2 - ix1), max(0, iy2 - iy1)
    inter = iw * ih
    if inter <= 0:
        return 0.0
    a_area = max(0, ax2-ax1) * max(0, ay2-ay1)
    b_area = max(0, bx2-bx1) * max(0, by2-by1)
    return inter / (a_area + b_area - inter + 1e-9)

def reading_order(words, y_bucket_px=18):
    # bucket by y center to form "rows", then sort row by x
    def yc(w): return (w["bbox"][1] + w["bbox"][3]) / 2.0
    def xc(w): return (w["bbox"][0] + w["bbox"][2]) / 2.0

    words_sorted = sorted(words, key=lambda w: (yc(w), xc(w)))

    rows = []
    for w in words_sorted:
        y = yc(w)
        placed = False
        for row in rows:
            if abs(row["y"] - y) <= y_bucket_px:
                row["items"].append(w)
                # keep running average
                row["y"] = (row["y"] * (len(row["items"]) - 1) + y) / len(row["items"])
                placed = True
                break
        if not placed:
            rows.append({"y": y, "items": [w]})

    ordered = []
    for row in sorted(rows, key=lambda r: r["y"]):
        ordered.extend(sorted(row["items"], key=lambda w: xc(w)))
    return ordered

def main():
    tile_dir = Path(sys.argv[1])
    out_json = Path(sys.argv[2])
    out_txt  = Path(sys.argv[3])
    page_w   = int(sys.argv[4]) if len(sys.argv) > 4 else None
    page_h   = int(sys.argv[5]) if len(sys.argv) > 5 else None
    dedupe_iou = float(sys.argv[6]) if len(sys.argv) > 6 else 0.6

    out_json.parent.mkdir(parents=True, exist_ok=True)
    out_txt.parent.mkdir(parents=True, exist_ok=True)

    predictor = ocr_predictor(det_arch="db_resnet50", reco_arch="crnn_vgg16_bn", pretrained=True)

    all_words = []

    for img_path in sorted(tile_dir.glob("*.png")):
        m = TILE_RE.match(img_path.name)
        if not m:
            continue
        x0, y0 = int(m.group(1)), int(m.group(2))

        doc = DocumentFile.from_images(str(img_path))
        result = predictor(doc)
        exported = result.export()

        # doctr export structure: pages -> blocks -> lines -> words
        page = exported["pages"][0]
        for block in page.get("blocks", []):
            for line in block.get("lines", []):
                for w in line.get("words", []):
                    text = (w.get("value") or "").strip()
                    if not text:
                        continue
                    ((nx1, ny1), (nx2, ny2)) = w["geometry"]  # normalized to tile dims
                    # convert to absolute page coords: tile origin + normalized*tile_size
                    # we don't know tile dims here; use the word's own tile size from result dimensions
                    # exported includes "dimensions": (h, w) in pixels
                    th, tw = page["dimensions"]
                    ax1 = x0 + nx1 * tw
                    ay1 = y0 + ny1 * th
                    ax2 = x0 + nx2 * tw
                    ay2 = y0 + ny2 * th
                    all_words.append({
                        "text": text,
                        "bbox": [float(ax1), float(ay1), float(ax2), float(ay2)],
                        "tile": img_path.name
                    })

    # dedupe by IoU + same text (keep first)
    kept = []
    for w in all_words:
        dup = False
        for k in kept:
            if w["text"] == k["text"] and iou(w["bbox"], k["bbox"]) >= dedupe_iou:
                dup = True
                break
        if not dup:
            kept.append(w)

    ordered = reading_order(kept)

    payload = {
        "source": str(tile_dir),
        "word_count_raw": len(all_words),
        "word_count_kept": len(kept),
        "words": ordered,
        "page_size": {"w": page_w, "h": page_h} if page_w and page_h else None,
    }

    out_json.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    out_txt.write_text("\n".join([w["text"] for w in ordered]) + "\n", encoding="utf-8")

    print(f"Wrote: {out_json}")
    print(f"Wrote: {out_txt}")
    print(f"Words raw: {len(all_words)} | kept after dedupe: {len(kept)} | ordered: {len(ordered)}")

if __name__ == "__main__":
    main()
