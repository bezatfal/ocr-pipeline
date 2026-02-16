import os, re, sys, json, math
from pathlib import Path
from doctr.io import DocumentFile
from doctr.models import ocr_predictor

TILE_RE = re.compile(r".*_x(\d+)_y(\d+)_t\d+\.png$", re.IGNORECASE)

def iou(a, b):
    # a,b: (x1,y1,x2,y2) in absolute page coords
    ax1, ay1, ax2, ay2 = a
    bx1, by1, bx2, by2 = b
    ix1, iy1 = max(ax1, bx1), max(ay1, by1)
    ix2, iy2 = min(ax2, bx2), min(ay2, by2)
    iw, ih = max(0, ix2 - ix1), max(0, iy2 - iy1)
    inter = iw * ih
    if inter == 0:
        return 0.0
    a_area = max(0, ax2-ax1) * max(0, ay2-ay1)
    b_area = max(0, bx2-bx1) * max(0, by2-by1)
    return inter / (a_area + b_area - inter + 1e-9)

def norm_box(geo):
    # doctr geom is [(x1,y1),(x2,y2)] normalized to image dims
    (x1, y1), (x2, y2) = geo
    return float(x1), float(y1), float(x2), float(y2)

def main():
    tile_dir = Path(sys.argv[1])
    out_json = Path(sys.argv[2])
    out_txt  = Path(sys.argv[3])
    dedupe_iou = float(sys.argv[4]) if len(sys.argv) > 4 else 0.6

    out_json.parent.mkdir(parents=True, exist_ok=True)
    out_txt.parent.mkdir(parents=True, exist_ok=True)

    predictor = ocr_predictor(det_arch="db_resnet50", reco_arch="crnn_vgg16_bn", pretrained=True)

    items = []

    for img_path in sorted(tile_dir.glob("*.png")):
        m = TILE_RE.match(img_path.name)
        if not m:
            continue
        ox, oy = int(m.group(1)), int(m.group(2))

        doc = DocumentFile.from_images([str(img_path)])
        result = predictor(doc)

        # image size
        from PIL import Image
        w, h = Image.open(img_path).size

        # Iterate words
        page = result.pages[0]
        for block in page.blocks:
            for line in block.lines:
                for word in line.words:
                    text = word.value.strip()
                    if not text:
                        continue
                    x1n, y1n, x2n, y2n = norm_box(word.geometry)
                    # absolute coords on page
                    x1 = ox + x1n * w
                    y1 = oy + y1n * h
                    x2 = ox + x2n * w
                    y2 = oy + y2n * h

                    items.append({
                        "text": text,
                        "conf": float(word.confidence),
                        "box": [x1, y1, x2, y2],
                        "tile": img_path.name,
                        "tile_origin": [ox, oy],
                    })

    # Dedupe: if same text overlaps heavily, keep higher confidence
    kept = []
    for it in sorted(items, key=lambda d: (-d["conf"], d["box"][1], d["box"][0])):
        drop = False
        for j, kt in enumerate(kept):
            if it["text"] == kt["text"] and iou(it["box"], kt["box"]) >= dedupe_iou:
                drop = True
                break
        if not drop:
            kept.append(it)

    # Reading order: top-to-bottom, then left-to-right
    kept.sort(key=lambda d: (d["box"][1], d["box"][0]))

    out_json.write_text(json.dumps(kept, indent=2), encoding="utf-8")

    # Simple line-break heuristic: new line when y jumps enough
    lines = []
    last_y = None
    line = []
    for it in kept:
        y = it["box"][1]
        if last_y is None:
            last_y = y
        if abs(y - last_y) > 18:  # tweak if needed (in pixels)
            if line:
                lines.append(" ".join(line))
            line = [it["text"]]
            last_y = y
        else:
            line.append(it["text"])
    if line:
        lines.append(" ".join(line))

    out_txt.write_text("\n".join(lines) + "\n", encoding="utf-8")

    print(f"Wrote: {out_json}")
    print(f"Wrote: {out_txt}")
    print(f"Words raw: {len(items)} | kept after dedupe: {len(kept)}")

if __name__ == "__main__":
    main()
