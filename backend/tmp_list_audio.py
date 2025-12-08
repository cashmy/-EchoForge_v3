from sqlalchemy import create_engine, text
from backend.app.config import load_settings

settings = load_settings()
engine = create_engine(settings.database_url)
with engine.begin() as conn:
    rows = conn.execute(text("SELECT entry_id, source_path, capture_fingerprint FROM entries WHERE source_type = 'audio'")).mappings().all()
    for row in rows:
        print(row)
