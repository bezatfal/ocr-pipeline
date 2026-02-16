import sys, sqlite3

db_file = sys.argv[1]
query   = " ".join(sys.argv[2:]).strip()
if not query:
    print("usage: search_index.py /path/to/index.sqlite words to search")
    raise SystemExit(2)

con = sqlite3.connect(db_file)
cur = con.cursor()

# Simple FTS query
rows = cur.execute("""
SELECT doc, snippet(docs, 1, '[', ']', '…', 10) AS snippet
FROM docs
WHERE docs MATCH ?
LIMIT 10;
""", (query,)).fetchall()

if not rows:
    print("No matches.")
else:
    for doc, snip in rows:
        print(f"\n--- {doc} ---\n{snip}")

con.close()
