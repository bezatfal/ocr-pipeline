import os, sys, json
import paddle
from paddleocr import PaddleOCR

def main():
    if len(sys.argv) < 4:
        print("usage: ocr_paddle.py <img_dir> <out_json> <out_txt>")
        sys.exit(1)

    img_dir = sys.argv[1]
    out_json = sys.argv[2]
    out_txt  = sys.argv[3]

    os.makedirs(os.path.dirname(out_json), exist_ok=True)
    os.makedirs(os.path.dirname(out_txt), exist_ok=True)

    # Pick GPU if available (PaddleOCR v3 commonly uses paddle device selection)
    if paddle.device.is_compiled_with_cuda() and paddle.device.cuda.device_count() > 0:
        paddle.set_device("gpu:0")
        device_used = "gpu:0"
    else:
        paddle.set_device("cpu")
        device_used = "cpu"

    # Keep args minimal for compatibility across PaddleOCR versions
    ocr = PaddleOCR(lang="en")

    all_items = []
    all_lines = []

    for name in sorted(os.listdir(img_dir)):
        if not name.lower().endswith(".png"):
            continue

        path = os.path.join(img_dir, name)
        result = ocr.ocr(path)

        if not result:
            continue

        dets = result[0] if isinstance(result, list) and len(result) > 0 else result
        if not dets:
            continue

        for item in dets:
            box = None
            text = None
            score = None

            if isinstance(item, (list, tuple)) and len(item) >= 2:
                box = item[0]
                if isinstance(item[1], (list, tuple)) and len(item[1]) >= 2:
                    text = item[1][0]
                    score = float(item[1][1])
            elif isinstance(item, dict):
                box = item.get("points") or item.get("box")
                text = item.get("transcription") or item.get("text")
                sc = item.get("score")
                score = float(sc) if sc is not None else None

            if text:
                all_items.append({"file": name, "text": text, "score": score, "box": box})
                all_lines.append(text)

    with open(out_json, "w", encoding="utf-8") as f:
        json.dump(all_items, f, indent=2, ensure_ascii=False)

    with open(out_txt, "w", encoding="utf-8") as f:
        f.write("\n".join(all_lines) + ("\n" if all_lines else ""))

    print(f"Device   : {device_used}")
    print(f"Wrote JSON: {out_json}")
    print(f"Wrote TXT : {out_txt}")
    print(f"Lines     : {len(all_lines)}")

if __name__ == "__main__":
    main()
