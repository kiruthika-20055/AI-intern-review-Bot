import os, io, json, uuid, datetime as dt
from dotenv import load_dotenv
load_dotenv()
from flask import Flask, render_template, request, redirect, url_for, flash, jsonify, send_file, abort
import pandas as pd
from apscheduler.schedulers.background import BackgroundScheduler
import db, excel_io, mailer, meet, ai_engine

app = Flask(__name__)
app.secret_key = os.getenv("SECRET_KEY", "dev")
BASE = lambda: os.getenv("APP_BASE_URL", "http://127.0.0.1:5000")
db.init()

# ----------------------------------------------------------------- helpers
def task_by_token(t):
    r = db.q("SELECT * FROM tasks WHERE token=?", (t,), one=True)
    if not r: abort(404)
    return dict(r)

def intern_by_email(e):
    r = db.q("SELECT * FROM interns WHERE email=?", (e,), one=True)
    return dict(r) if r else {"name": e.split("@")[0], "email": e}

def create_task(email, title, desc, reqs, deadline):
    email = email.strip().lower()
    if not db.q("SELECT 1 FROM interns WHERE email=?", (email,), one=True):
        return False
    tok = uuid.uuid4().hex[:12]
    db.ex("INSERT INTO tasks(token,intern_email,title,description,requirements,deadline) VALUES(?,?,?,?,?,?)",
          (tok, email, title, desc, reqs, deadline))
    t = task_by_token(tok)
    mailer.send_email(email, f"New Task Assigned: {title}", mailer.task_assigned_mail(intern_by_email(email)["name"], t, BASE()))
    return True

def next_slot():
    """Next working-day slot: 30-min slots starting REVIEW_START_HOUR, no clashes."""
    start_h = int(os.getenv("REVIEW_START_HOUR", 10)); mins = int(os.getenv("REVIEW_SLOT_MINUTES", 30))
    per_day = int(os.getenv("SLOTS_PER_DAY", 12))
    day = dt.date.today() + dt.timedelta(days=1)
    while True:
        if day.weekday() < 5:
            taken = {r["review_dt"] for r in db.q("SELECT review_dt FROM tasks WHERE review_dt LIKE ?", (day.isoformat() + "%",))}
            for i in range(per_day):
                s = dt.datetime.combine(day, dt.time(start_h)) + dt.timedelta(minutes=mins * i)
                if s.isoformat(timespec="minutes") not in taken: return s
        day += dt.timedelta(days=1)

def schedule_review(task):
    slot = next_slot(); mins = int(os.getenv("REVIEW_SLOT_MINUTES", 30))
    intern = intern_by_email(task["intern_email"])
    link = meet.create_meet_link(task["title"], slot, mins, task["intern_email"])
    db.ex("UPDATE tasks SET status='review_scheduled', review_dt=?, meet_link=? WHERE id=?",
          (slot.isoformat(timespec="minutes"), link, task["id"]))
    mailer.send_email(task["intern_email"], f"Review Scheduled: {task['title']} – {slot.strftime('%d %b, %I:%M %p')}",
                      mailer.review_mail(intern["name"], task, slot, link, BASE()))
    return slot, link

# ----------------------------------------------------------------- admin
@app.route("/")
def dashboard():
    tasks = db.q("""SELECT t.*, i.name FROM tasks t LEFT JOIN interns i ON i.email=t.intern_email ORDER BY t.id DESC""")
    stats = {"interns": db.q("SELECT COUNT(*) c FROM interns", one=True)["c"], "tasks": len(tasks)}
    for s in ("assigned", "review_scheduled", "reviewed"):
        stats[s] = sum(1 for t in tasks if t["status"] == s)
    return render_template("index.html", tasks=tasks, stats=stats)

@app.route("/template/<kind>")
def template_dl(kind):
    return send_file(excel_io.template(kind), download_name=f"{kind}_template.xlsx", as_attachment=True)

@app.route("/upload/interns", methods=["POST"])
def upload_interns():
    f = request.files.get("file")
    if not f: flash("Choose an Excel file"); return redirect(url_for("dashboard"))
    df = excel_io.read(f); n = 0
    for _, r in df.iterrows():
        e = r.get("email", "").strip().lower()
        if not e: continue
        db.ex("""INSERT INTO interns(email,name,phone,college,department) VALUES(?,?,?,?,?)
                 ON CONFLICT(email) DO UPDATE SET name=excluded.name, phone=excluded.phone, college=excluded.college, department=excluded.department""",
              (e, r.get("name", ""), r.get("phone", ""), r.get("college", ""), r.get("department", ""))); n += 1
    flash(f"{n} interns imported/updated."); return redirect(url_for("dashboard"))

@app.route("/upload/tasks", methods=["POST"])
def upload_tasks():
    f = request.files.get("file")
    if not f: flash("Choose an Excel file"); return redirect(url_for("dashboard"))
    df = excel_io.read(f); ok = bad = 0
    for _, r in df.iterrows():
        if create_task(r.get("email", ""), r.get("title", ""), r.get("description", ""), r.get("requirements", ""), r.get("deadline", "")): ok += 1
        else: bad += 1
    flash(f"{ok} tasks allocated (mail sent). {bad} skipped (email not in interns list)."); return redirect(url_for("dashboard"))

@app.route("/allocate", methods=["POST"])
def allocate():
    f = request.form
    targets = [r["email"] for r in db.q("SELECT email FROM interns")] if f.get("email", "").strip().lower() == "all" else [f.get("email", "")]
    ok = sum(create_task(e, f["title"], f["description"], f["requirements"], f["deadline"]) for e in targets)
    flash(f"Task allocated to {ok} intern(s)."); return redirect(url_for("dashboard"))

@app.route("/export")
def export():
    rows = db.q("""SELECT i.name, t.intern_email email, t.title, t.status, t.deadline, t.review_dt, t.meet_link, r.score,
                   json_extract(r.report,'$.verdict') verdict, json_extract(r.report,'$.summary') summary
                   FROM tasks t LEFT JOIN interns i ON i.email=t.intern_email LEFT JOIN reviews r ON r.task_id=t.id""")
    buf = io.BytesIO(); pd.DataFrame([dict(r) for r in rows]).to_excel(buf, index=False); buf.seek(0)
    return send_file(buf, download_name="review_tracker.xlsx", as_attachment=True)

# ----------------------------------------------------------------- intern submit -> auto schedule
@app.route("/submit/<token>", methods=["GET", "POST"])
def submit(token):
    t = task_by_token(token)
    if request.method == "POST":
        text = request.form.get("submission", "")
        f = request.files.get("file")
        if f and f.filename: text += "\n\n# FILE: " + f.filename + "\n" + f.read().decode("utf-8", "ignore")
        if t["status"] == "assigned":
            db.ex("UPDATE tasks SET submission=?, status='completed' WHERE id=?", (text, t["id"]))
            slot, link = schedule_review(task_by_token(token))
            flash(f"Task submitted! Review scheduled {slot.strftime('%d %b %Y, %I:%M %p')}. Check your email.")
        return redirect(url_for("submit", token=token))
    return render_template("submit.html", t=t, intern=intern_by_email(t["intern_email"]))

# ----------------------------------------------------------------- AI review room
@app.route("/review/<token>")
def review(token):
    t = task_by_token(token)
    return render_template("review.html", t=t, intern=intern_by_email(t["intern_email"]))

def _get_tr(tid):
    r = db.q("SELECT * FROM reviews WHERE task_id=?", (tid,), one=True)
    if not r: db.ex("INSERT INTO reviews(task_id,created) VALUES(?,?)", (tid, dt.datetime.now().isoformat())); r = db.q("SELECT * FROM reviews WHERE task_id=?", (tid,), one=True)
    return json.loads(r["transcript"] or "[]")

@app.route("/api/review/<token>/message", methods=["POST"])
def review_msg(token):
    t = task_by_token(token); name = intern_by_email(t["intern_email"])["name"]
    tr = _get_tr(t["id"]); ans = (request.json or {}).get("text", "").strip()
    if ans: tr.append({"role": "intern", "text": ans})
    q = ai_engine.next_question(t, name, tr)
    if q: tr.append({"role": "bot", "text": q})
    db.ex("UPDATE reviews SET transcript=? WHERE task_id=?", (json.dumps(tr), t["id"]))
    return jsonify(question=q, done=q is None)

@app.route("/api/review/<token>/finish", methods=["POST"])
def review_finish(token):
    t = task_by_token(token); tr = _get_tr(t["id"])
    rep = ai_engine.analyze(t, tr)
    db.ex("UPDATE reviews SET report=?, score=? WHERE task_id=?", (json.dumps(rep), rep["score"], t["id"]))
    db.ex("UPDATE tasks SET status='reviewed' WHERE id=?", (t["id"],))
    intern = intern_by_email(t["intern_email"])
    mailer.send_email(t["intern_email"], f"Review Report: {t['title']}", mailer.report_mail(intern["name"], t, rep, BASE()))
    return jsonify(url=url_for("report", token=token))

@app.route("/report/<token>")
def report(token):
    t = task_by_token(token)
    r = db.q("SELECT * FROM reviews WHERE task_id=?", (t["id"],), one=True)
    if not r or not r["report"]: return "Review not completed yet.", 404
    return render_template("report.html", t=t, intern=intern_by_email(t["intern_email"]), rep=json.loads(r["report"]), tr=json.loads(r["transcript"]))

# ----------------------------------------------------------------- reminders (30 min before review)
def reminder_job():
    now = dt.datetime.now()
    for t in db.q("SELECT * FROM tasks WHERE status='review_scheduled' AND reminded=0 AND review_dt IS NOT NULL"):
        s = dt.datetime.fromisoformat(t["review_dt"])
        if dt.timedelta(0) <= s - now <= dt.timedelta(minutes=30):
            t = dict(t); i = intern_by_email(t["intern_email"])
            mailer.send_email(t["intern_email"], f"Reminder: review at {s.strftime('%I:%M %p')} – {t['title']}", mailer.review_mail(i["name"], t, s, t["meet_link"], BASE()))
            db.ex("UPDATE tasks SET reminded=1 WHERE id=?", (t["id"],))

if __name__ == "__main__":
    sch = BackgroundScheduler(); sch.add_job(reminder_job, "interval", minutes=1); sch.start()
    app.run(debug=True, use_reloader=False, port=5000)
