import psycopg

DB_URL = "postgresql://postgres:LuckySebeka@localhost:5432/echo_forge"
INDEXES = (
    "IDX_entries_type_id",
    "IDX_entries_domain_id",
    "IDX_entries_domain_type",
)

conn = psycopg.connect(DB_URL)
cur = conn.cursor()
cur.execute(
    """
    select indexrelname, idx_scan
    from pg_stat_user_indexes
    where indexrelname = any(%s)
    order by indexrelname
    """,
    (list(INDEXES),),
)
rows = cur.fetchall()
conn.close()
for name, idx_scan in rows:
    print(f"{name}: {idx_scan}")
