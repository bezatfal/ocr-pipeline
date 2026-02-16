import sys, json
from doctr.io import DocumentFile
from doctr.models import ocr_predictor

img_path = sys.argv[1]
out_json = sys.argv[2]
out_txt  = sys.argv[3]

# Accuracy-first model (slower but best)
model = ocr_predictor(det_arch="db_resnet50", reco_arch="crnn_vgg16_bn", pretrained=True)

doc = DocumentFile.from_images(img_path)
result = model(doc)

# Save full structured output
data = result.export()

with open(out_json, "w", encoding="utf-8") as f:
    json.dump(data, f, indent=2, ensure_ascii=False)

# Extract plain text (reading order)
lines = []
for page in data.get("pages", []):
    for block in page.get("blocks", []):
        for line in block.get("lines", []):
            words = [w["value"] for w in line.get("words", []) if w.get("value")]
            if words:
                lines.append(" ".join(words))

with open(out_txt, "w", encoding="utf-8") as f:
    f.write("\n".join(lines) + "\n")

print("Wrote:", out_json)
print("Wrote:", out_txt)
