import os,time
from pathlib import Path
import bcrypt
import psycopg

def migrate():
    password=os.environ.get('ADMIN_INITIAL_PASSWORD','')
    if len(password)<8 or password.lower().startswith(('replace','change')):
        raise RuntimeError('Set a non-placeholder ADMIN_INITIAL_PASSWORD of at least 8 characters before first deployment')
    for attempt in range(30):
        try:
            conn=psycopg.connect(os.environ['DATABASE_URL']);break
        except psycopg.OperationalError:
            if attempt==29:raise
            time.sleep(2)
    with conn:
        conn.execute('SELECT pg_advisory_xact_lock(4857001)')
        conn.execute('CREATE TABLE IF NOT EXISTS schema_migrations (version integer PRIMARY KEY, applied_at timestamptz NOT NULL DEFAULT now())')
        if not conn.execute('SELECT 1 FROM schema_migrations WHERE version=1').fetchone():
            source=Path('/app/backend/schema.sql') if Path('/app/backend/schema.sql').exists() else Path('backend/schema.sql')
            sql=source.read_text(encoding='utf-8').replace('BEGIN;','').replace('COMMIT;','')
            conn.execute(sql)
            conn.execute('INSERT INTO schema_migrations(version) VALUES (1)')
        if not conn.execute('SELECT 1 FROM users WHERE role=0').fetchone():
            hashed=bcrypt.hashpw(password.encode(),bcrypt.gensalt(rounds=12)).decode()
            conn.execute("INSERT INTO users(full_name,login,password_hash,role) VALUES ('Администратор','admin',%s,0)",(hashed,))
    print('Database migrations completed')

if __name__=='__main__':migrate()
