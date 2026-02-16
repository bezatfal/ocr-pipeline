import sys, sqlite3
from pathlib import Path

def main():
    txt_file = Path(sys.argv[1])      # e.g. /mnt/ai/outputs/ocr/39070/doctr_tiles_merged.txt
    db_file  = Path(sys.argv[2])      # e.g. /mnt/ai/outputs/search/ocr_index.sqlite
    doc_name = sys.argv[3] if len(sys.argv) > 3 else txt_file.parent.name

    db_file.parent.mkdir(parents=True, exist_ok=True)
    text = txt_file.read_text(encoding="utf-8", errors="ignore")

    con = sqlite3.connect(str(db_file))
    cur = con.cursor()

    # FTS5 table: doc + content
    cur.execute("""
    CREATE VIRTUAL TABLE IF NOT EXISTS docs
    USING fts5(doc, content);
    """)

    # Upsert behaviour: remove any previous rows for this doc name
    cur.execute("DELETE FROM docs WHERE doc = ?;", (doc_name,))
    cur.execute("INSERT INTO docs(doc, content) VALUES (?, ?);", (doc_name, text))

    con.commit()
    con.close()
    print(f"Indexed (replaced) '{doc_name}' into {db_file}")

if __name__ == "__main__":
    main()
