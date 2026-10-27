import csv
import io
import os
import re
import threading
import time
import webbrowser
from datetime import datetime
from functools import wraps

import cv2
import numpy as np
from dotenv import load_dotenv
from flask import (Flask, render_template, jsonify, Response,
                   request, redirect, url_for, session)
from werkzeug.security import generate_password_hash, check_password_hash

from modules.pipeline import Pipeline
from modules.recognition import FaceRecognizer
from modules import db, genai_utils

load_dotenv()

app = Flask(__name__)
app.secret_key = os.getenv("SECRET_KEY", "change-this-secret")
app.config["MAX_CONTENT_LENGTH"] = 40 * 1024 * 1024
db.init_db()
pipeline = Pipeline()
suggestion_cache = {}

GRADE_RE = re.compile(r"[A-Za-z0-9][A-Za-z0-9 \-]{0,19}")
SECTION_RE = re.compile(r"[A-Za-z0-9]{1,5}")
ROLL_RE = re.compile(r"[A-Za-z0-9\-/]{1,12}")


def pretty_date(value):
    try:
        return datetime.strptime(value, "%Y-%m-%d").strftime("%d %b %Y")
    except (TypeError, ValueError):
        return value


def login_required(view):
    @wraps(view)
    def wrapped(*args, **kwargs):
        if "teacher_id" not in session:
            if request.path.startswith("/api/") or request.path == "/video_feed":
                return jsonify({"error": "login required"}), 401
            return redirect(url_for("login"))
        return view(*args, **kwargs)
    return wrapped


def save_finished_session(info, started_at, ended_at, timeline, students):
    return db.save_session(info["teacher_id"], info, started_at, ended_at,
                           timeline, students)


# ---------- accounts ----------

@app.route("/health")
def health():
    return jsonify({"status": "ok"})


@app.route("/register", methods=["GET", "POST"])
def register():
    error = None
    if request.method == "POST":
        name = request.form.get("name", "").strip()
        email = request.form.get("email", "").strip().lower()
        password = request.form.get("password", "")
        if not name or not email or len(password) < 6:
            error = "Fill every field. Password needs at least 6 characters."
        elif not db.create_teacher(name, email, generate_password_hash(password)):
            error = "That email is already registered."
        else:
            return redirect(url_for("login"))
    return render_template("register.html", error=error)


@app.route("/login", methods=["GET", "POST"])
def login():
    error = None
    if request.method == "POST":
        email = request.form.get("email", "").strip().lower()
        password = request.form.get("password", "")
        teacher = db.get_teacher_by_email(email)
        if teacher and check_password_hash(teacher["password_hash"], password):
            session.clear()
            session["teacher_id"] = teacher["id"]
            session["teacher_name"] = teacher["name"]
            return redirect(url_for("index"))
        error = "Wrong email or password."
    return render_template("login.html", error=error)


@app.route("/logout")
def logout():
    pipeline.stop()
    session.clear()
    return redirect(url_for("login"))


# ---------- dashboard ----------

@app.route("/")
@login_required
def index():
    today = datetime.now().strftime("%A, %d %B %Y")
    return render_template("index.html", teacher_name=session["teacher_name"], today=today)


@app.route("/api/classes", methods=["GET"])
@login_required
def api_classes():
    classes = db.list_classes(session["teacher_id"])
    for c in classes:
        t = db.todays_session(c["id"])
        c["today"] = None if not t else {
            "time": t["started_at"][11:16],
            "present": t["present_count"],
            "absent": t["absent_count"],
        }
    return jsonify(classes)


@app.route("/api/classes", methods=["POST"])
@login_required
def api_add_class():
    data = request.get_json(silent=True) or {}
    grade = str(data.get("grade", "")).strip()
    section = str(data.get("section", "")).strip()
    mode = data.get("mode")

    if not GRADE_RE.fullmatch(grade):
        return jsonify({"error": "Class: use letters, numbers, spaces and hyphens only (for example 10 or CSE)."}), 400
    if section and not SECTION_RE.fullmatch(section):
        return jsonify({"error": "Section: 1 to 5 letters or numbers (for example A)."}), 400
    if mode not in ("daily", "lecture"):
        return jsonify({"error": "Choose the attendance type."}), 400

    class_id = db.create_class(session["teacher_id"], grade, section, mode)
    if class_id is None:
        return jsonify({"error": "You already have that class and section."}), 409
    return jsonify({"id": class_id})


@app.route("/api/classes/<int:class_id>/mode", methods=["POST"])
@login_required
def api_class_mode(class_id):
    data = request.get_json(silent=True) or {}
    mode = data.get("mode")
    if mode not in ("daily", "lecture"):
        return jsonify({"error": "Invalid attendance type."}), 400
    if not db.update_class_mode(session["teacher_id"], class_id, mode):
        return jsonify({"error": "Class not found."}), 404
    return jsonify({"ok": True})


@app.route("/api/start", methods=["POST"])
@login_required
def api_start():
    pipeline.clear_saved()
    data = request.get_json(silent=True) or {}
    try:
        class_id = int(data.get("class_id", 0))
    except (TypeError, ValueError):
        class_id = 0

    cls = db.get_class(session["teacher_id"], class_id)
    if not cls:
        return jsonify({"error": "Choose a class first, or add one with + Add class."}), 400

    if cls["strength"] < 1:
        return jsonify({"error": "Class %s has no students yet. Click Manage students and add them first." % cls["name"]}), 400

    subject = str(data.get("subject", "")).strip()
    if cls["mode"] == "lecture" and not subject:
        return jsonify({"error": "Enter the subject for this lecture."}), 400

    if cls["mode"] == "daily":
        subject = ""
        existing = db.todays_session(cls["id"])
        if existing:
            message = (
                "Attendance for %s was already taken on %s at %s (%d present, %d absent). "
                "Open Records to review it, or delete it there to retake."
                % (cls["name"], pretty_date(existing["session_date"]),
                   existing["started_at"][11:16], existing["present_count"],
                   existing["absent_count"])
            )
            return jsonify({"error": message}), 409

    roster = []
    for s in db.get_roster(cls["id"]):
        roster.append({
            "id": s["id"],
            "roll_no": s["roll_no"],
            "name": s["name"],
            "embedding": np.frombuffer(s["embedding"], dtype=np.float32),
        })

    info = {
        "teacher_id": session["teacher_id"],
        "class_id": cls["id"],
        "class_name": cls["name"],
        "subject": subject,
    }
    started = pipeline.start(info, roster, save_finished_session)
    return jsonify({"started": started})


@app.route("/api/stop", methods=["POST"])
@login_required
def api_stop():
    pipeline.stop()
    return jsonify({"stopped": True})


@app.route("/api/stats")
@login_required
def api_stats():
    return jsonify(pipeline.get_stats())


def mjpeg_stream():
    while pipeline.get_stats()["running"]:
        frame = pipeline.get_frame()
        if frame is None:
            time.sleep(0.05)
            continue
        yield (b"--frame\r\nContent-Type: image/jpeg\r\n\r\n" + frame + b"\r\n")
        time.sleep(0.04)


@app.route("/video_feed")
@login_required
def video_feed():
    return Response(mjpeg_stream(),
                    mimetype="multipart/x-mixed-replace; boundary=frame")


@app.route("/api/history")
@login_required
def api_history():
    return jsonify(db.list_sessions(session["teacher_id"])[:5])


# ---------- students (roster) ----------

@app.route("/classes/<int:class_id>")
@login_required
def class_roster(class_id):
    cls = db.get_class(session["teacher_id"], class_id)
    if not cls:
        return redirect(url_for("index"))
    return render_template("roster.html", teacher_name=session["teacher_name"], c=cls)


@app.route("/api/classes/<int:class_id>/students", methods=["GET"])
@login_required
def api_students(class_id):
    if not db.get_class(session["teacher_id"], class_id):
        return jsonify({"error": "Class not found."}), 404
    return jsonify(db.list_students(class_id))


@app.route("/api/classes/<int:class_id>/students", methods=["POST"])
@login_required
def api_add_student(class_id):
    if not db.get_class(session["teacher_id"], class_id):
        return jsonify({"error": "Class not found."}), 404

    roll_no = request.form.get("roll_no", "").strip()
    name = request.form.get("name", "").strip()
    if not ROLL_RE.fullmatch(roll_no):
        return jsonify({"error": "Roll number: 1 to 12 letters, numbers, - or /."}), 400
    if not (1 <= len(name) <= 60):
        return jsonify({"error": "Enter the student's name (up to 60 characters)."}), 400

    files = request.files.getlist("photos")
    if not (1 <= len(files) <= 12):
        return jsonify({"error": "Add 1 to 12 photos of the student's face."}), 400

    images = []
    for f in files:
        data = np.frombuffer(f.read(), dtype=np.uint8)
        images.append(cv2.imdecode(data, cv2.IMREAD_COLOR) if data.size else None)

    try:
        template, used, skipped = FaceRecognizer().template_from_images(images)
    except FileNotFoundError as e:
        return jsonify({"error": "%s. Download the two face models into the models folder (see the README)." % e}), 500

    if template is None:
        return jsonify({"error": "No clear single face was found in the photos. Use well-lit photos of just this student, facing the camera."}), 400

    student_id = db.add_student(class_id, roll_no, name, template.tobytes())
    if student_id is None:
        return jsonify({"error": "Roll number %s already exists in this class." % roll_no}), 409

    warning = ""
    if used < 3:
        warning = "Only %d photo(s) had a clear face. Recognition works better with 3 or more." % used
    return jsonify({"id": student_id, "used": used, "skipped": skipped, "warning": warning})


@app.route("/api/students/<int:student_id>/delete", methods=["POST"])
@login_required
def api_delete_student(student_id):
    if not db.delete_student(session["teacher_id"], student_id):
        return jsonify({"error": "Student not found."}), 404
    return jsonify({"ok": True})


# ---------- teaching suggestions ----------

@app.route("/api/suggestions/<int:session_id>")
@login_required
def api_suggestions(session_id):
    row = db.get_session(session["teacher_id"], session_id)
    if not row:
        return jsonify({"error": "Session not found."}), 404

    if session_id in suggestion_cache:
        return jsonify(suggestion_cache[session_id])

    intervals = db.get_session_intervals(session_id)
    summary = genai_utils.build_summary(row, intervals)
    result = genai_utils.get_suggestions(summary)
    if result["source"] == "gemini":
        suggestion_cache[session_id] = result
    return jsonify(result)


# ---------- records ----------

def clean_date(value):
    try:
        return datetime.strptime(value, "%Y-%m-%d").strftime("%Y-%m-%d")
    except (TypeError, ValueError):
        return None


def read_filters():
    date_from = clean_date(request.args.get("from"))
    date_to = clean_date(request.args.get("to"))
    try:
        class_id = int(request.args.get("class_id", ""))
    except ValueError:
        class_id = None
    return date_from, date_to, class_id


@app.route("/records")
@login_required
def records():
    date_from, date_to, class_id = read_filters()
    sessions = db.list_sessions(session["teacher_id"], date_from, date_to, class_id)

    args = {}
    if date_from:
        args["from"] = date_from
    if date_to:
        args["to"] = date_to
    if class_id:
        args["class_id"] = class_id

    return render_template(
        "records.html",
        teacher_name=session["teacher_name"],
        sessions=sessions,
        classes=db.list_classes(session["teacher_id"]),
        date_from=date_from or "",
        date_to=date_to or "",
        class_id=class_id,
        csv_url=url_for("records_csv", **args),
    )


@app.route("/records.csv")
@login_required
def records_csv():
    date_from, date_to, class_id = read_filters()
    rows = db.list_sessions(session["teacher_id"], date_from, date_to, class_id)

    out = io.StringIO()
    writer = csv.writer(out)
    writer.writerow(["Date", "Class", "Subject", "Start", "End",
                     "Total students", "Present", "Absent", "Avg engagement"])
    for s in rows:
        writer.writerow([
            s["session_date"], s["class_name"], s["subject"] or "",
            s["started_at"][11:19], s["ended_at"][11:19] if s["ended_at"] else "",
            s["total_students"], s["present_count"], s["absent_count"],
            s["avg_engagement"] if s["avg_engagement"] is not None else "",
        ])

    return Response(
        out.getvalue(),
        mimetype="text/csv",
        headers={"Content-Disposition": "attachment; filename=attendance_records.csv"},
    )


@app.route("/records/<int:session_id>")
@login_required
def record_detail(session_id):
    row = db.get_session(session["teacher_id"], session_id)
    if not row:
        return redirect(url_for("records"))
    return render_template(
        "session.html",
        teacher_name=session["teacher_name"],
        s=row,
        intervals=db.get_session_intervals(session_id),
        students=db.get_session_students(session_id),
    )


@app.route("/records/<int:session_id>.csv")
@login_required
def record_students_csv(session_id):
    row = db.get_session(session["teacher_id"], session_id)
    if not row:
        return redirect(url_for("records"))

    out = io.StringIO()
    writer = csv.writer(out)
    writer.writerow(["Date", "Class", "Subject", "Roll no", "Name", "Status", "First seen"])
    for st in db.get_session_students(session_id):
        writer.writerow([row["session_date"], row["class_name"], row["subject"] or "",
                         st["roll_no"], st["name"], st["status"], st["first_seen"] or ""])

    return Response(
        out.getvalue(),
        mimetype="text/csv",
        headers={"Content-Disposition": "attachment; filename=attendance_%s_%s.csv"
                 % (row["class_name"], row["session_date"])},
    )


@app.route("/records/<int:session_id>/delete", methods=["POST"])
@login_required
def delete_record(session_id):
    db.delete_session(session["teacher_id"], session_id)
    suggestion_cache.pop(session_id, None)
    return redirect(url_for("records"))


if __name__ == "__main__":
    threading.Timer(1.5, lambda: webbrowser.open("http://127.0.0.1:5000")).start()
    app.run(debug=True, threaded=True, use_reloader=False)