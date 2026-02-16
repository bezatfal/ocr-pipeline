import os, sys, json
from pathlib import Path
from doctr.io import DocumentFile
from doctr.models import ocr_predictor

def iter_images(img_dir: Path):
    for p in sorted(img_dir.iterdir()):
        if p.suffix.lower() in {".png", ".jpg", ".jpeg", ".tif", ".tiff"}:
            yield p

def main():
    img_dir = Path(sys.argv[1])
    out_json = Path(sys.argv[2])
    out_txt  = Path(sys.argv[3])

    out_json.parent.mkdir(parents=True, exist_ok=True)
    out_txt.parent.mkdir(parents=True, exist_ok=True)

    # Accuracy-first defaults for docTR:
    # - db_resnet50 (detector) + crnn_vgg16_bn (recognizer) are what you just downloaded.
    predictor = ocr_predictor(
        det_arch="db_resnet50",
        reco_arch="crnn_vgg16_bn",
        pretrained=True
    )

    all_pages = []
    all_lines = []

    for img_path in iter_images(img_dir):
        doc = DocumentFile.from_images(str(img_path))
        result = predictor(doc)
        export = result.export()

        # export structure: {"pages":[{"blocks":[{"lines":[{"words":[...]}]}]}]}
        page_obj = {"file": img_path.name, "pages": export.get("pages", [])}
        all_pages.append(page_obj)

        # Flatten to plain text (line by line) for indexing/search
        for page in export.get("pages", []):
            for block in page.get("blocks", []):
                for line in block.get("lines", []):
                    words = [w["value"] for w in line.get("words", []) if w.get("value")]
                    if words:
                        all_lines.append(" ".join(words))

    out_json.write_text(json.dumps(all_pages, indent=2), encoding="utf-8")
    out_txt.write_text("\n".join(all_lines) + "\n", encoding="utf-8")

    print(f"Wrote: {out_json}")
    print(f"Wrote: {out_txt}")

if __name__ == "__main__":
    main()
