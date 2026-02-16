from PIL import Image
from pathlib import Path
import sys

img_path = Path(sys.argv[1])
out_dir  = Path(sys.argv[2])
tile = int(sys.argv[3]) if len(sys.argv) > 3 else 1536
overlap = int(tile * 0.2)
step = tile - overlap

out_dir.mkdir(parents=True, exist_ok=True)

img = Image.open(img_path).convert("RGB")
w, h = img.size

i = 0
for y in range(0, h, step):
    for x in range(0, w, step):
        crop = img.crop((x, y, min(x+tile, w), min(y+tile, h)))
        crop.save(out_dir / f"{img_path.stem}_x{x:05d}_y{y:05d}_t{i:04d}.png")
        i += 1

print(f"Generated {i} tiles in {out_dir} (tile={tile}, overlap={overlap}, step={step})")
