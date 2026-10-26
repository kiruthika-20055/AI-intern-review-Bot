# 🤖 AI Intern Review Bot

100 interns → Excel upload → task allocation (email-based) → intern submits → auto review slot + email (Meet link, date, time, title, task)
→ AI review room (voice/text, human-like questions) → AI compares requirements vs actual work → report (missing, mistakes, improvements) + email.

## Run in VS Code (Windows)
```
cd ai-review-bot
python -m venv venv
venv\Scripts\activate
pip install -r requirements.txt
python app.py
```
## Mac / Linux
```
python3 -m venv venv && source venv/bin/activate
pip install -r requirements.txt
python app.py
```
Open http://127.0.0.1:5000

## Demo flow
1. Dashboard → Import `sample_data/interns_100.xlsx`
2. Import `sample_data/tasks_100.xlsx` (allocates tasks; mails saved in `outbox/` in dev mode)
3. Click **submit** on a task → paste work → review slot + email created
4. Click **review** → answer bot's questions (🎤 voice works in Chrome/Edge) → **Finish & get report**
5. `/export` downloads tracker Excel

## Settings (.env)
- `ANTHROPIC_API_KEY` → real AI questions + deep analysis (blank = rule-based fallback)
- `SMTP_USER` / `SMTP_PASSWORD` → real Gmail mails (App Password). Blank = saved to `outbox/`
- `USE_GOOGLE_CALENDAR=true` + `credentials.json` (Google Cloud → Calendar API → OAuth Desktop) → unique Meet link per intern. Otherwise `DEFAULT_MEET_LINK` is used.
