import os, smtplib, time, re
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart

def send_email(to, subject, html):
    user, pwd = os.getenv("SMTP_USER"), os.getenv("SMTP_PASSWORD")
    if not (user and pwd):   # DEV MODE: save to outbox
        os.makedirs("outbox", exist_ok=True)
        name = re.sub(r"[^a-zA-Z0-9@._-]", "_", f"{int(time.time()*1000)}_{to}.html")
        with open(os.path.join("outbox", name), "w", encoding="utf-8") as f:
            f.write(f"<h4>To: {to}<br>Subject: {subject}</h4><hr>{html}")
        print(f"[DEV MAIL] saved outbox/{name}")
        return True
    msg = MIMEMultipart("alternative")
    msg["Subject"] = subject
    msg["From"] = f"{os.getenv('FROM_NAME','Review Team')} <{user}>"
    msg["To"] = to
    msg.attach(MIMEText(html, "html"))
    with smtplib.SMTP(os.getenv("SMTP_HOST", "smtp.gmail.com"), int(os.getenv("SMTP_PORT", 587))) as s:
        s.starttls(); s.login(user, pwd); s.sendmail(user, [to], msg.as_string())
    return True

def task_assigned_mail(name, task, base):
    reqs = "".join(f"<li>{r}</li>" for r in task["requirements"].splitlines() if r.strip())
    return f"""<p>Hi {name},</p><p>A new task is assigned to you.</p>
    <h3>{task['title']}</h3><p>{task['description']}</p>
    <b>Requirements:</b><ul>{reqs}</ul><p><b>Deadline:</b> {task['deadline']}</p>
    <p>When you finish, submit here: <a href="{base}/submit/{task['token']}">Submit task</a></p>"""

def review_mail(name, task, dt, meet, base):
    return f"""<p>Hi {name},</p><p>Your task is marked complete. Your review is scheduled:</p>
    <table cellpadding=6 border=1 style="border-collapse:collapse">
    <tr><td><b>Title</b></td><td>{task['title']}</td></tr>
    <tr><td><b>Task to be done / reviewed</b></td><td>{task['description']}</td></tr>
    <tr><td><b>Date</b></td><td>{dt.strftime('%A, %d %b %Y')}</td></tr>
    <tr><td><b>Time</b></td><td>{dt.strftime('%I:%M %p')}</td></tr>
    <tr><td><b>Google Meet</b></td><td><a href="{meet}">{meet}</a></td></tr>
    <tr><td><b>AI Review Room</b></td><td><a href="{base}/review/{task['token']}">{base}/review/{task['token']}</a></td></tr></table>
    <p>Be ready to explain your task reference, module and what you built. Please join on time.</p>"""

def report_mail(name, task, rep, base):
    li = lambda xs: "".join(f"<li>{x}</li>" for x in xs) or "<li>None</li>"
    return f"""<p>Hi {name}, here is your AI review report for <b>{task['title']}</b>.</p>
    <h3>Score: {rep['score']}/100 &mdash; {rep['verdict']}</h3><p>{rep['summary']}</p>
    <b>Completed:</b><ul>{li(rep['covered'])}</ul><b>Missing / not done:</b><ul>{li(rep['missing'])}</ul>
    <b>Mistakes:</b><ul>{li(rep['mistakes'])}</ul><b>How to improve:</b><ul>{li(rep['improvements'])}</ul>
    <p><a href="{base}/report/{task['token']}">View full report</a></p>"""
