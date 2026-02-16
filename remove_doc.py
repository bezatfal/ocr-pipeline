import sqlite3, sys

if len(sys.argv) < 3:
    print("usage: remove_doc.py /path/to/index.sqlite doc_name")
    raise SystemExit(2)

db = sys.argv[1]
doc = sys.argv[2]

con = sqlite3.connect(db)
cur = con.cursor()
cur.execute("DELETE FROM docs WHERE doc = ?;", (doc,))
con.commit()

print(f"Removed '{doc}' from {db}")
con.close()
