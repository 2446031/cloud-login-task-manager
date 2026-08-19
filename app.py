from flask import Flask, render_template, request, redirect, url_for, session
import sqlite3
import os
from werkzeug.security import generate_password_hash, check_password_hash

app = Flask(__name__)

# -------------------------------------------------
# SECRET KEY
# -------------------------------------------------

app.secret_key = os.environ.get(
    "SECRET_KEY",
    "my_cloud_login_secret_key"
)


# -------------------------------------------------
# DATABASE
# -------------------------------------------------

def init_db():

    conn = sqlite3.connect("users.db")
    cursor = conn.cursor()

    # Users table
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            username TEXT UNIQUE NOT NULL,
            password TEXT NOT NULL
        )
    """)

    # Tasks table
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS tasks (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL,
            title TEXT NOT NULL,
            description TEXT,
            status TEXT DEFAULT 'Pending',
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (user_id) REFERENCES users(id)
        )
    """)

    conn.commit()
    conn.close()


# -------------------------------------------------
# HOME
# -------------------------------------------------

@app.route("/")
def home():

    if "username" in session:
        return redirect(url_for("dashboard"))

    return redirect(url_for("login"))


# -------------------------------------------------
# REGISTER
# -------------------------------------------------

@app.route("/register", methods=["GET", "POST"])
def register():

    if request.method == "POST":

        username = request.form["username"]
        password = request.form["password"]

        hashed_password = generate_password_hash(password)

        try:

            conn = sqlite3.connect("users.db")
            cursor = conn.cursor()

            cursor.execute(
                "INSERT INTO users (username, password) VALUES (?, ?)",
                (username, hashed_password)
            )

            conn.commit()
            conn.close()

            return redirect(url_for("login"))

        except sqlite3.IntegrityError:

            return "Username already exists!"

    return render_template("register.html")


# -------------------------------------------------
# LOGIN
# -------------------------------------------------

@app.route("/login", methods=["GET", "POST"])
def login():

    if request.method == "POST":

        username = request.form["username"]
        password = request.form["password"]

        conn = sqlite3.connect("users.db")
        cursor = conn.cursor()

        cursor.execute(
            "SELECT * FROM users WHERE username = ?",
            (username,)
        )

        user = cursor.fetchone()

        conn.close()

        if user and check_password_hash(user[2], password):

            session["user_id"] = user[0]
            session["username"] = user[1]

            return redirect(url_for("dashboard"))

        return "Invalid username or password!"

    return render_template("login.html")


# -------------------------------------------------
# DASHBOARD / TASK LIST
# -------------------------------------------------

@app.route("/dashboard")
def dashboard():

    if "user_id" not in session:

        return redirect(url_for("login"))

    conn = sqlite3.connect("users.db")
    cursor = conn.cursor()

    cursor.execute("""
        SELECT id, title, description, status, created_at
        FROM tasks
        WHERE user_id = ?
        ORDER BY created_at DESC
    """, (session["user_id"],))

    tasks = cursor.fetchall()

    conn.close()

    return render_template(
        "dashboard.html",
        username=session["username"],
        tasks=tasks
    )


# -------------------------------------------------
# ADD TASK
# -------------------------------------------------

@app.route("/add_task", methods=["POST"])
def add_task():

    if "user_id" not in session:

        return redirect(url_for("login"))

    title = request.form["title"]
    description = request.form["description"]

    conn = sqlite3.connect("users.db")
    cursor = conn.cursor()

    cursor.execute("""
        INSERT INTO tasks
        (user_id, title, description)
        VALUES (?, ?, ?)
    """, (
        session["user_id"],
        title,
        description
    ))

    conn.commit()
    conn.close()

    return redirect(url_for("dashboard"))


# -------------------------------------------------
# COMPLETE TASK
# -------------------------------------------------

@app.route("/complete_task/<int:task_id>")
def complete_task(task_id):

    if "user_id" not in session:

        return redirect(url_for("login"))

    conn = sqlite3.connect("users.db")
    cursor = conn.cursor()

    cursor.execute("""
        UPDATE tasks
        SET status = 'Completed'
        WHERE id = ? AND user_id = ?
    """, (
        task_id,
        session["user_id"]
    ))

    conn.commit()
    conn.close()

    return redirect(url_for("dashboard"))


# -------------------------------------------------
# DELETE TASK
# -------------------------------------------------

@app.route("/delete_task/<int:task_id>")
def delete_task(task_id):

    if "user_id" not in session:

        return redirect(url_for("login"))

    conn = sqlite3.connect("users.db")
    cursor = conn.cursor()

    cursor.execute("""
        DELETE FROM tasks
        WHERE id = ? AND user_id = ?
    """, (
        task_id,
        session["user_id"]
    ))

    conn.commit()
    conn.close()

    return redirect(url_for("dashboard"))


# -------------------------------------------------
# EDIT TASK
# -------------------------------------------------

@app.route("/edit_task/<int:task_id>", methods=["GET", "POST"])
def edit_task(task_id):

    if "user_id" not in session:

        return redirect(url_for("login"))

    conn = sqlite3.connect("users.db")
    cursor = conn.cursor()

    if request.method == "POST":

        title = request.form["title"]
        description = request.form["description"]

        cursor.execute("""
            UPDATE tasks
            SET title = ?, description = ?
            WHERE id = ? AND user_id = ?
        """, (
            title,
            description,
            task_id,
            session["user_id"]
        ))

        conn.commit()
        conn.close()

        return redirect(url_for("dashboard"))

    cursor.execute("""
        SELECT id, title, description, status
        FROM tasks
        WHERE id = ? AND user_id = ?
    """, (
        task_id,
        session["user_id"]
    ))

    task = cursor.fetchone()

    conn.close()

    if task is None:

        return "Task not found!"

    return render_template(
        "edit_task.html",
        task=task
    )


# -------------------------------------------------
# LOGOUT
# -------------------------------------------------

@app.route("/logout")
def logout():

    session.clear()

    return redirect(url_for("login"))


# -------------------------------------------------
# INITIALIZE DATABASE
# -------------------------------------------------

# Important for Azure/Gunicorn.
# This runs when the Flask application starts.
init_db()


# -------------------------------------------------
# RUN APPLICATION
# -------------------------------------------------

if __name__ == "__main__":

    # Azure/Cloud deployment port
    port = int(os.environ.get("PORT", 5000))

    app.run(
        host="0.0.0.0",
        port=port,
        debug=False
    )