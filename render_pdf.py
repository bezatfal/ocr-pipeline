import os, sys
import fitz  # PyMuPDF

pdf_path = sys.argv[1]
out_dir = sys.argv[2]
zoom = float(sys.argv[3]) if len(sys.argv) > 3 else 4.0  # 4.0 ~ high DPI

os.makedirs(out_dir, exist_ok=True)
doc = fitz.open(pdf_path)
mat = fitz.Matrix(zoom, zoom)

for i in range(doc.page_count):
    page = doc.load_page(i)
    pix = page.get_pixmap(matrix=mat, alpha=False)
    out_path = os.path.join(out_dir, f"page_{i+1:04d}.png")
    pix.save(out_path)

print(f"Rendered {doc.page_count} pages to {out_dir}")
