import psycopg
from psycopg.rows import dict_row
from contextlib import contextmanager
from config import settings

@contextmanager
def get_db_connection():
    conn = None
    try:
        conn = psycopg.connect(settings.DATABASE_URL, row_factory=dict_row)
        yield conn
        conn.commit()
    except Exception:
        if conn:
            conn.rollback()
        raise
    finally:
        if conn:
            conn.close()

def get_db():
    return get_db_connection()
