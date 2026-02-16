import os, sys
from PIL import Image, ImageOps, ImageFilter

in_dir = sys.argv[1]
out_dir = sys.argv[2]
os.makedirs(out_dir, exist_ok=True)

def preprocess(img: Image.Image) -> Image.Image:
    # Convert to grayscale
    img = img.convert("L")

    # Auto-contrast helps faded scans
    img = ImageOps.autocontrast(img, cutoff=1)

    # Mild sharpening helps thin text/lines
    img = img.filter(ImageFilter.UnsharpMask(radius=2, percent=150, threshold=3))

    return img

for name in sorted(os.listdir(in_dir)):
    if not name.lower().endswith(".png"):
        continue
    src = os.path.join(in_dir, name)
    dst = os.path.join(out_dir, name.replace(".png", "_prep.png"))
    im = Image.open(src)
    im2 = preprocess(im)
    im2.save(dst)

print(f"Preprocessed PNGs written to {out_dir}")
