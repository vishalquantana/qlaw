#!/usr/bin/env python3
"""Re-parse order_no_date for all rulings in-place (no DB rebuild — preserves
chunks/embeddings while Vision OCR runs). Uses build_db.split_order_field."""
import sqlite3
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from build_db import split_order_field

DB = Path(__file__).parent / "data" / "aar.db"

con = sqlite3.connect(DB)
rows = con.execute("SELECT id, order_no_date FROM rulings").fetchall()
fixed, cleared = 0, 0
for rid, s in rows:
    no, date = split_order_field(s or "")
    cur = con.execute("SELECT order_no, order_date FROM rulings WHERE id=?", (rid,)).fetchone()
    if (cur[0], cur[1]) != (no, date):
        con.execute("UPDATE rulings SET order_no=?, order_date=? WHERE id=?", (no, date, rid))
        fixed += 1
    if not date:
        cleared += 1
con.commit()
bad_dates = con.execute(
    "SELECT COUNT(*) FROM rulings WHERE order_date != '' AND (CAST(substr(order_date,6,2) AS INT) > 12"
    " OR CAST(substr(order_date,9,2) AS INT) > 31)"
).fetchone()[0]
print(f"updated {fixed}/{len(rows)} rows; {cleared} without a parseable date; remaining invalid dates: {bad_dates}")
