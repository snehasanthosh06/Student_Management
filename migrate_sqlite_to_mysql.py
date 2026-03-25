import sqlite3
from pathlib import Path
import pymysql


SQLITE_DB = Path(__file__).resolve().parent / "students.db"

MYSQL_CONFIG = {
    "host": "127.0.0.1",
    "port": 3306,
    "user": "root",
    "password": "",
    "database": "student_management",
}


def migrate_students():
    if not SQLITE_DB.exists():
        print("No SQLite database found. Nothing to migrate.")
        return

    sqlite_conn = sqlite3.connect(SQLITE_DB)
    sqlite_conn.row_factory = sqlite3.Row
    sqlite_rows = sqlite_conn.execute(
        """
        SELECT roll_number, name, email, age,
               COALESCE(student_class, course, 'N/A') AS student_class,
               marks, attendance
        FROM students
        """
    ).fetchall()

    mysql_conn = pymysql.connect(**MYSQL_CONFIG, autocommit=False)
    try:
        with mysql_conn.cursor() as cursor:
            for row in sqlite_rows:
                cursor.execute(
                    """
                    INSERT INTO students
                    (roll_number, name, email, age, student_class, marks, attendance)
                    VALUES (%s, %s, %s, %s, %s, %s, %s)
                    ON DUPLICATE KEY UPDATE
                        name = VALUES(name),
                        age = VALUES(age),
                        student_class = VALUES(student_class),
                        marks = VALUES(marks),
                        attendance = VALUES(attendance)
                    """,
                    (
                        row["roll_number"],
                        row["name"],
                        row["email"],
                        row["age"],
                        row["student_class"],
                        row["marks"],
                        row["attendance"],
                    ),
                )
        mysql_conn.commit()
        print(f"Migrated {len(sqlite_rows)} student rows to MySQL.")
    finally:
        sqlite_conn.close()
        mysql_conn.close()


if __name__ == "__main__":
    migrate_students()
