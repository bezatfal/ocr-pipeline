import sys
import sqlite3
from pathlib import Path

def main():
    if len(sys.argv) < 3:
        print("usage: build_index.py <text_file> <db_file> [doc_name]")
        raise SystemExit(2)

    txt_file = Path(sys.argv[1])      # e.g. /mnt/ai/outputs/ocr/39070/doctr_tiles_merged_all.txt
    db_file  = Path(sys.argv[2])      # e.g. /mnt/ai/outputs/search/ocr_index.sqlite
    doc_name = sys.argv[3] if len(sys.argv) > 3 else txt_file.parent.name

    db_file.parent.mkdir(parents=True, exist_ok=True)

    text = txt_file.read_text(encoding="utf-8", errors="ignore")

    con = sqlite3.connect(str(db_file))
    cur = con.cursor()

    # FTS5 table: doc identifier + searchable content
    # doc is UNINDEXED so only 'content' participates in full-text search.
    cur.execute("""
    CREATE VIRTUAL TABLE IF NOT EXISTS docs
    USING fts5(doc UNINDEXED, content);
    """)

    # Upsert: remove any previous entry for this doc_name, then insert the latest content
    cur.execute("DELETE FROM docs WHERE doc = ?;", (doc_name,))
    cur.execute("INSERT INTO docs(doc, content) VALUES (?, ?);", (doc_name, text))

    con.commit()
    con.close()

    print(f"Indexed (upsert) '{doc_name}' into {db_file}")

if __name__ == "__main__":
    main()
