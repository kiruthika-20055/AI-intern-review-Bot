import pandas as pd, io

INTERN_COLS = ["name", "email", "phone", "college", "department"]
TASK_COLS = ["email", "title", "description", "requirements", "deadline"]

def template(kind):
    cols = INTERN_COLS if kind == "interns" else TASK_COLS
    sample = ({"name": "Asha K", "email": "asha@example.com", "phone": "9876543210", "college": "ABC College", "department": "CSE"}
              if kind == "interns" else
              {"email": "asha@example.com", "title": "Login Module", "description": "Build a login page with Flask",
               "requirements": "Email+password form; Password hashing; Session handling; Error messages", "deadline": "2026-11-05"})
    buf = io.BytesIO(); pd.DataFrame([sample], columns=cols).to_excel(buf, index=False); buf.seek(0); return buf

def read(file):
    df = pd.read_excel(file, dtype=str).fillna("")
    df.columns = [c.strip().lower() for c in df.columns]
    return df
