import os
import sqlite3
from functools import wraps

from flask import (
    Flask,
    flash,
    g,
    redirect,
    render_template,
    request,
    session,
    url_for,
)
from werkzeug.security import check_password_hash, generate_password_hash


app = Flask(__name__)

app.config["SECRET_KEY"] = os.environ.get(
    "SECRET_KEY",
    "development-secret-key-change-this",
)

DATABASE = os.path.join(app.instance_path, "users.db")


def get_db():
    if "db" not in g:
        os.makedirs(app.instance_path, exist_ok=True)

        g.db = sqlite3.connect(DATABASE)
        g.db.row_factory = sqlite3.Row

    return g.db


@app.teardown_appcontext
def close_db(exception=None):
    db = g.pop("db", None)

    if db is not None:
        db.close()


def init_db():
    db = get_db()

    db.execute(
        """
        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            username TEXT UNIQUE NOT NULL,
            password TEXT NOT NULL
        )
        """
    )

    db.execute(
        """
        CREATE TABLE IF NOT EXISTS tasks (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL,
            title TEXT NOT NULL,
            description TEXT,
            completed INTEGER NOT NULL DEFAULT 0,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (user_id) REFERENCES users (id)
        )
        """
    )

    db.commit()


def login_required(view):
    @wraps(view)
    def wrapped_view(**kwargs):
        if "user_id" not in session:
            flash("Please log in first.", "error")
            return redirect(url_for("login"))

        return view(**kwargs)

    return wrapped_view


@app.route("/")
def home():
    if "user_id" in session:
        return redirect(url_for("dashboard"))

    return redirect(url_for("login"))


@app.route("/register", methods=("GET", "POST"))
def register():
    if request.method == "POST":
        username = request.form["username"].strip()
        password = request.form["password"]
        confirm_password = request.form["confirm_password"]

        error = None

        if not username:
            error = "Username is required."
        elif not password:
            error = "Password is required."
        elif len(password) < 6:
            error = "Password must contain at least 6 characters."
        elif password != confirm_password:
            error = "Passwords do not match."

        if error is None:
            db = get_db()

            existing_user = db.execute(
                "SELECT id FROM users WHERE username = ?",
                (username,),
            ).fetchone()

            if existing_user is not None:
                error = "Username already exists."
            else:
                hashed_password = generate_password_hash(password)

                db.execute(
                    """
                    INSERT INTO users (username, password)
                    VALUES (?, ?)
                    """,
                    (username, hashed_password),
                )

                db.commit()

                flash("Registration successful. Please log in.", "success")
                return redirect(url_for("login"))

        flash(error, "error")

    return render_template("register.html")


@app.route("/login", methods=("GET", "POST"))
def login():
    if request.method == "POST":
        username = request.form["username"].strip()
        password = request.form["password"]

        db = get_db()

        user = db.execute(
            """
            SELECT id, username, password
            FROM users
            WHERE username = ?
            """,
            (username,),
        ).fetchone()

        if user is None:
            flash("Invalid username or password.", "error")
        elif not check_password_hash(user["password"], password):
            flash("Invalid username or password.", "error")
        else:
            session.clear()
            session["user_id"] = user["id"]
            session["username"] = user["username"]

            return redirect(url_for("dashboard"))

    return render_template("login.html")


@app.route("/logout")
def logout():
    session.clear()

    flash("You have been logged out.", "success")

    return redirect(url_for("login"))


@app.route("/dashboard")
@login_required
def dashboard():
    db = get_db()

    tasks = db.execute(
        """
        SELECT id, title, description, completed, created_at
        FROM tasks
        WHERE user_id = ?
        ORDER BY created_at DESC
        """,
        (session["user_id"],),
    ).fetchall()

    return render_template("dashboard.html", tasks=tasks)


@app.route("/add-task", methods=("POST",))
@login_required
def add_task():
    title = request.form["title"].strip()
    description = request.form["description"].strip()

    if not title:
        flash("Task title is required.", "error")
        return redirect(url_for("dashboard"))

    db = get_db()

    db.execute(
        """
        INSERT INTO tasks (user_id, title, description)
        VALUES (?, ?, ?)
        """,
        (session["user_id"], title, description),
    )

    db.commit()

    flash("Task added successfully.", "success")

    return redirect(url_for("dashboard"))


@app.route("/task/<int:task_id>/complete", methods=("POST",))
@login_required
def complete_task(task_id):
    db = get_db()

    task = db.execute(
        """
        SELECT id, completed
        FROM tasks
        WHERE id = ? AND user_id = ?
        """,
        (task_id, session["user_id"]),
    ).fetchone()

    if task is None:
        flash("Task not found.", "error")
        return redirect(url_for("dashboard"))

    new_status = 0 if task["completed"] else 1

    db.execute(
        """
        UPDATE tasks
        SET completed = ?
        WHERE id = ? AND user_id = ?
        """,
        (new_status, task_id, session["user_id"]),
    )

    db.commit()

    return redirect(url_for("dashboard"))


@app.route("/task/<int:task_id>/edit", methods=("GET", "POST"))
@login_required
def edit_task(task_id):
    db = get_db()

    task = db.execute(
        """
        SELECT id, title, description, completed
        FROM tasks
        WHERE id = ? AND user_id = ?
        """,
        (task_id, session["user_id"]),
    ).fetchone()

    if task is None:
        flash("Task not found.", "error")
        return redirect(url_for("dashboard"))

    if request.method == "POST":
        title = request.form["title"].strip()
        description = request.form["description"].strip()

        if not title:
            flash("Task title is required.", "error")

            return render_template(
                "edit_task.html",
                task=task,
            )

        db.execute(
            """
            UPDATE tasks
            SET title = ?, description = ?
            WHERE id = ? AND user_id = ?
            """,
            (
                title,
                description,
                task_id,
                session["user_id"],
            ),
        )

        db.commit()

        flash("Task updated successfully.", "success")

        return redirect(url_for("dashboard"))

    return render_template("edit_task.html", task=task)


@app.route("/task/<int:task_id>/delete", methods=("POST",))
@login_required
def delete_task(task_id):
    db = get_db()

    task = db.execute(
        """
        SELECT id
        FROM tasks
        WHERE id = ? AND user_id = ?
        """,
        (task_id, session["user_id"]),
    ).fetchone()

    if task is None:
        flash("Task not found.", "error")
        return redirect(url_for("dashboard"))

    db.execute(
        """
        DELETE FROM tasks
        WHERE id = ? AND user_id = ?
        """,
        (task_id, session["user_id"]),
    )

    db.commit()

    flash("Task deleted successfully.", "success")

    return redirect(url_for("dashboard"))


with app.app_context():
    init_db()


if __name__ == "__main__":
    app.run(
        debug=True,
        host="127.0.0.1",
        port=5000,
    )
