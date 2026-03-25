from flask import Flask, flash, redirect, render_template, request, session, url_for
from functools import wraps
import os
import time
import pymysql
from pymysql.cursors import DictCursor

app = Flask(__name__)
app.secret_key = os.getenv("SECRET_KEY", "student-management-secret-key")
app.config["DB_HOST"] = os.getenv("DB_HOST", "127.0.0.1")
app.config["DB_PORT"] = int(os.getenv("DB_PORT", "3306"))
app.config["DB_USER"] = os.getenv("DB_USER", "root")
app.config["DB_PASSWORD"] = os.getenv("DB_PASSWORD", "")
app.config["DB_NAME"] = os.getenv("DB_NAME", "student_management")


def login_required(view):
    @wraps(view)
    def wrapped_view(*args, **kwargs):
        if not session.get("is_admin_logged_in"):
            flash("Please login as admin to continue.", "error")
            return redirect(url_for("login"))
        return view(*args, **kwargs)

    return wrapped_view


def get_connection():
    retries = int(os.getenv("DB_CONNECT_RETRIES", "20"))
    delay_s = float(os.getenv("DB_CONNECT_DELAY_SECONDS", "1.5"))
    last_err = None

    for _ in range(retries):
        try:
            return pymysql.connect(
                host=app.config["DB_HOST"],
                port=app.config["DB_PORT"],
                user=app.config["DB_USER"],
                password=app.config["DB_PASSWORD"],
                database=app.config["DB_NAME"],
                cursorclass=DictCursor,
                autocommit=False,
            )
        except pymysql.err.OperationalError as exc:
            last_err = exc
            time.sleep(delay_s)

    raise last_err


def get_server_connection():
    """
    Connect to the MySQL server without assuming the target database exists yet.
    Used by init_db() to create database/schema safely during container startup.
    """
    retries = int(os.getenv("DB_CONNECT_RETRIES", "20"))
    delay_s = float(os.getenv("DB_CONNECT_DELAY_SECONDS", "1.5"))
    last_err = None

    for _ in range(retries):
        try:
            return pymysql.connect(
                host=app.config["DB_HOST"],
                port=app.config["DB_PORT"],
                user=app.config["DB_USER"],
                password=app.config["DB_PASSWORD"],
                database="mysql",
                cursorclass=DictCursor,
                autocommit=True,
            )
        except pymysql.err.OperationalError as exc:
            last_err = exc
            time.sleep(delay_s)

    raise last_err


def init_db():
    server_conn = get_server_connection()
    with server_conn.cursor() as cursor:
        # In Docker Compose setups the database is often created by MySQL init scripts.
        # If the DB user doesn't have CREATE DATABASE privileges, we just continue.
        try:
            cursor.execute(
                f"""
                CREATE DATABASE IF NOT EXISTS {app.config["DB_NAME"]}
                CHARACTER SET utf8mb4
                COLLATE utf8mb4_unicode_ci
                """
            )
        except Exception:
            pass
    server_conn.close()

    conn = get_connection()
    with conn.cursor() as cursor:
        cursor.execute(
            """
            CREATE TABLE IF NOT EXISTS students (
                id INT PRIMARY KEY AUTO_INCREMENT,
                roll_number VARCHAR(100) NOT NULL UNIQUE,
                name VARCHAR(255) NOT NULL,
                email VARCHAR(255) NOT NULL UNIQUE,
                age INT NOT NULL,
                student_class VARCHAR(100) NOT NULL,
                marks DECIMAL(5,2) NOT NULL,
                attendance DECIMAL(5,2) NOT NULL
            )
            """
        )
        cursor.execute(
            """
            CREATE TABLE IF NOT EXISTS users (
                id INT PRIMARY KEY AUTO_INCREMENT,
                username VARCHAR(100) NOT NULL UNIQUE,
                password VARCHAR(255) NOT NULL,
                role VARCHAR(50) NOT NULL
            )
            """
        )
        cursor.execute(
            """
            INSERT IGNORE INTO users (username, password, role)
            VALUES (%s, %s, %s)
            """,
            ("admin", "admin123", "admin"),
        )
        cursor.execute("DELETE FROM users WHERE role <> 'admin'")
    conn.commit()
    conn.close()


@app.route("/")
def index():
    # Public landing page (admin login is still required for CRUD).
    return render_template("index.html")


@app.route("/dashboard")
@login_required
def dashboard():
    search_name = request.args.get("name", "").strip()
    search_roll = request.args.get("roll_number", "").strip()
    search_class = request.args.get("student_class", "").strip()
    sort_by = request.args.get("sort_by", "id")
    sort_order = request.args.get("sort_order", "desc")

    valid_sort_fields = {
        "id": "id",
        "name": "name",
        "roll_number": "roll_number",
        "student_class": "student_class",
        "marks": "marks",
        "attendance": "attendance",
    }
    safe_sort_field = valid_sort_fields.get(sort_by, "id")
    safe_sort_order = "ASC" if sort_order.lower() == "asc" else "DESC"

    query = "SELECT * FROM students WHERE 1=1"
    params = []

    if search_name:
        query += " AND name LIKE %s"
        params.append(f"%{search_name}%")
    if search_roll:
        query += " AND roll_number LIKE %s"
        params.append(f"%{search_roll}%")
    if search_class:
        query += " AND student_class LIKE %s"
        params.append(f"%{search_class}%")

    query += f" ORDER BY {safe_sort_field} {safe_sort_order}"

    conn = get_connection()
    with conn.cursor() as cursor:
        cursor.execute(query, params)
        students = cursor.fetchall()
    conn.close()
    return render_template(
        "dashboard.html",
        students=students,
        filters={
            "name": search_name,
            "roll_number": search_roll,
            "student_class": search_class,
            "sort_by": sort_by,
            "sort_order": sort_order,
        },
    )


@app.route("/add", methods=["POST"])
@login_required
def add_student():
    roll_number = request.form.get("roll_number", "").strip()
    name = request.form.get("name", "").strip()
    email = request.form.get("email", "").strip()
    age = request.form.get("age", "").strip()
    student_class = request.form.get("student_class", "").strip()
    marks = request.form.get("marks", "").strip()
    attendance = request.form.get("attendance", "").strip()

    if not all([roll_number, name, email, age, student_class, marks, attendance]):
        flash("All fields are required.", "error")
        return redirect(url_for("dashboard"))

    try:
        age_int = int(age)
        marks_float = float(marks)
        attendance_float = float(attendance)
    except ValueError:
        flash("Age must be integer, marks/attendance must be numbers.", "error")
        return redirect(url_for("dashboard"))

    if not (0 <= marks_float <= 100 and 0 <= attendance_float <= 100):
        flash("Marks and attendance must be between 0 and 100.", "error")
        return redirect(url_for("dashboard"))

    conn = get_connection()
    try:
        with conn.cursor() as cursor:
            cursor.execute(
                """
                INSERT INTO students (roll_number, name, email, age, student_class, marks, attendance)
                VALUES (%s, %s, %s, %s, %s, %s, %s)
                """,
                (roll_number, name, email, age_int, student_class, marks_float, attendance_float),
            )
        conn.commit()
        flash("Student added successfully.", "success")
    except pymysql.IntegrityError as exc:
        error_text = str(exc).lower()
        if "duplicate entry" in error_text:
            flash("Email or roll number already exists. Use unique values.", "error")
        else:
            flash("Could not save student due to database constraints.", "error")
    finally:
        conn.close()

    return redirect(url_for("dashboard"))


@app.route("/edit/<int:student_id>", methods=["GET", "POST"])
@login_required
def edit_student(student_id):
    conn = get_connection()
    with conn.cursor() as cursor:
        cursor.execute("SELECT * FROM students WHERE id = %s", (student_id,))
        student = cursor.fetchone()

    if student is None:
        conn.close()
        flash("Student not found.", "error")
        return redirect(url_for("dashboard"))

    if request.method == "POST":
        roll_number = request.form.get("roll_number", "").strip()
        name = request.form.get("name", "").strip()
        email = request.form.get("email", "").strip()
        age = request.form.get("age", "").strip()
        student_class = request.form.get("student_class", "").strip()
        marks = request.form.get("marks", "").strip()
        attendance = request.form.get("attendance", "").strip()

        if not all([roll_number, name, email, age, student_class, marks, attendance]):
            flash("All fields are required.", "error")
            conn.close()
            return redirect(url_for("edit_student", student_id=student_id))

        try:
            age_int = int(age)
            marks_float = float(marks)
            attendance_float = float(attendance)
        except ValueError:
            flash("Age must be integer, marks/attendance must be numbers.", "error")
            conn.close()
            return redirect(url_for("edit_student", student_id=student_id))

        if not (0 <= marks_float <= 100 and 0 <= attendance_float <= 100):
            flash("Marks and attendance must be between 0 and 100.", "error")
            conn.close()
            return redirect(url_for("edit_student", student_id=student_id))

        try:
            with conn.cursor() as cursor:
                cursor.execute(
                    """
                    UPDATE students
                    SET roll_number = %s, name = %s, email = %s, age = %s, student_class = %s, marks = %s, attendance = %s
                    WHERE id = %s
                    """,
                    (
                        roll_number,
                        name,
                        email,
                        age_int,
                        student_class,
                        marks_float,
                        attendance_float,
                        student_id,
                    ),
                )
            conn.commit()
            flash("Student updated successfully.", "success")
        except pymysql.IntegrityError as exc:
            error_text = str(exc).lower()
            if "duplicate entry" in error_text:
                flash("Email or roll number already exists. Use unique values.", "error")
            else:
                flash("Could not update student due to database constraints.", "error")
            conn.close()
            return redirect(url_for("edit_student", student_id=student_id))

        conn.close()
        return redirect(url_for("dashboard"))

    conn.close()
    return render_template("edit.html", student=student)


@app.route("/delete/<int:student_id>", methods=["POST"])
@login_required
def delete_student(student_id):
    conn = get_connection()
    with conn.cursor() as cursor:
        cursor.execute("DELETE FROM students WHERE id = %s", (student_id,))
    conn.commit()
    conn.close()
    flash("Student deleted successfully.", "success")
    return redirect(url_for("dashboard"))


@app.route("/login", methods=["GET", "POST"])
def login():
    if session.get("is_admin_logged_in"):
        return redirect(url_for("dashboard"))

    if request.method == "POST":
        username = request.form.get("username", "").strip()
        password = request.form.get("password", "")
        conn = get_connection()
        with conn.cursor() as cursor:
            cursor.execute(
                "SELECT username FROM users WHERE username = %s AND password = %s AND role = 'admin'",
                (username, password),
            )
            user = cursor.fetchone()
        conn.close()

        if user:
            session["is_admin_logged_in"] = True
            session["username"] = user["username"]
            flash("Login successful.", "success")
            return redirect(url_for("dashboard"))

        flash("Invalid username or password.", "error")

    return render_template("login.html")


@app.route("/logout", methods=["POST"])
@login_required
def logout():
    session.clear()
    flash("Logged out successfully.", "success")
    return redirect(url_for("login"))


if __name__ == "__main__":
    init_db()
    app.run(
        host="0.0.0.0",
        port=int(os.getenv("APP_PORT", "5000")),
        debug=os.getenv("DEBUG", "false").lower() == "true",
    )
