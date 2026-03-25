import os
import time
import subprocess

import pymysql
from pymysql.cursors import DictCursor


def wait_for_mysql():
    host = os.getenv("DB_HOST", "127.0.0.1")
    port = int(os.getenv("DB_PORT", "3306"))
    user = os.getenv("DB_USER", "root")
    password = os.getenv("DB_PASSWORD", "")

    # Prefer connecting to the app DB (created by MySQL init). Falling back to "mysql"
    # can fail if the DB user has no privileges on system schemas.
    server_db = os.getenv("DB_SERVER_DB") or os.getenv("DB_NAME") or "student_management"

    retries = int(os.getenv("DB_CONNECT_RETRIES", "60"))
    delay_s = float(os.getenv("DB_CONNECT_DELAY_SECONDS", "2"))

    last_err = None
    for attempt in range(retries):
        try:
            conn = pymysql.connect(
                host=host,
                port=port,
                user=user,
                password=password,
                database=server_db,
                cursorclass=DictCursor,
                autocommit=True,
            )
            conn.close()
            return
        except pymysql.err.OperationalError as exc:
            last_err = exc
            time.sleep(delay_s)

    # Final fallback: connect without selecting a database (privilege-safe).
    try:
        conn = pymysql.connect(
            host=host,
            port=port,
            user=user,
            password=password,
            cursorclass=DictCursor,
            autocommit=True,
        )
        conn.close()
        return
    except pymysql.err.OperationalError as exc:
        last_err = exc

    raise last_err


if __name__ == "__main__":
    wait_for_mysql()
    subprocess.run(["python", "app.py"], check=True)

