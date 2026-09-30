import os
from psycopg.rows import dict_row
from psycopg_pool import ConnectionPool

pool = ConnectionPool(os.environ['DATABASE_URL'], min_size=1, max_size=int(os.getenv('DB_POOL_SIZE','12')), timeout=15, kwargs={'row_factory':dict_row}, open=False)

def connection():
    if pool.closed:
        pool.open()
    return pool.connection()
