import sqlite3
import sys

db = sys.argv[1] if len(sys.argv) > 1 else "/mnt/ai/outputs/search/ocr_index.sqlite"
con = sqlite3.connect(db)
cur = con.cursor()

try:
    rows = cur.execute("SELECT rowid, doc, length(content) AS chars FROM docs ORDER BY doc;").fetchall()
except Exception as e:
    print(f"Error reading docs table. Is the index created? ({e})")
    raise SystemExit(2)

if not rows:
    print("No docs indexed.")
else:
    for rowid, doc, chars in rows:
        print(f"{rowid}\t{doc}\t{chars} chars")

con.close()
