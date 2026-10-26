"""AI brain: asks human-like review questions and compares assigned requirements vs actual work.
Uses Claude if ANTHROPIC_API_KEY is set; otherwise a rule-based fallback so the project always runs."""
import os, json, re

MAX_QUESTIONS = 7

def _client():
    key = os.getenv("ANTHROPIC_API_KEY")
    if not key: return None
    try:
        import anthropic
        return anthropic.Anthropic(api_key=key)
    except Exception:
        return None

def _model(): return os.getenv("ANTHROPIC_MODEL", "claude-sonnet-5-5")

def _reqs(task): return [r.strip() for r in re.split(r"[\n;]+", task["requirements"] or "") if r.strip()]

def _ctx(task, transcript):
    t = "\n".join(f"{'BOT' if m['role']=='bot' else 'INTERN'}: {m['text']}" for m in transcript)
    return (f"TASK TITLE: {task['title']}\nTASK DESCRIPTION: {task['description']}\n"
            f"COMPANY REQUIREMENTS:\n" + "\n".join(f"- {r}" for r in _reqs(task)) +
            f"\n\nINTERN SUBMISSION (code/text):\n{(task['submission'] or '(nothing submitted)')[:6000]}\n\nREVIEW CONVERSATION:\n{t}")

# ------------------------------------------------------------------ questions
def next_question(task, name, transcript):
    asked = sum(1 for m in transcript if m["role"] == "bot")
    if asked >= MAX_QUESTIONS: return None
    c = _client()
    if c:
        try:
            sys = ("You are a friendly, human-like senior mentor reviewing an intern over a call. Ask ONE short, natural question at a time "
                   "(max 2 sentences). Cover: task reference, which module they worked on, their approach, each company requirement, "
                   "challenges, and probe vague answers. Reply with only the question. When you have enough info reply exactly DONE.")
            r = c.messages.create(model=_model(), max_tokens=200, system=sys,
                                  messages=[{"role": "user", "content": _ctx(task, transcript) + f"\n\nIntern name: {name}. Questions asked so far: {asked}. Ask the next question."}])
            txt = r.content[0].text.strip()
            return None if txt.upper().startswith("DONE") else txt
        except Exception as e:
            print("[AI] question fallback:", e)
    reqs = _reqs(task)
    flow = [f"Hi {name}! 👋 Welcome to your review for '{task['title']}'. First, in your own words — what was this task and what reference/brief were you given?",
            "Which module or part of the project did you work on, and what approach did you take?"]
    flow += [f"Requirement: \"{r}\" — how did you implement it? Please explain." for r in reqs[:4]]
    flow += ["What challenges did you face, and what would you improve if you had more time?"]
    return flow[asked] if asked < len(flow) else None

# ------------------------------------------------------------------ analysis
def _words(s): return {w for w in re.findall(r"[a-zA-Z]{4,}", (s or "").lower())}

def _fallback_report(task, transcript):
    reqs = _reqs(task)
    evidence = (task["submission"] or "") + " " + " ".join(m["text"] for m in transcript if m["role"] == "intern")
    ev = _words(evidence)
    covered, missing = [], []
    for r in reqs:
        w = _words(r)
        hit = len(w & ev) / max(len(w), 1)
        (covered if hit >= 0.5 else missing).append(r)
    score = int(100 * len(covered) / max(len(reqs), 1))
    short = [m["text"] for m in transcript if m["role"] == "intern" and len(m["text"].split()) < 6]
    mistakes = [f"Requirement not evidenced in submission or explanation: {r}" for r in missing]
    if not (task["submission"] or "").strip(): mistakes.append("No submission/code was provided for review.")
    if short: mistakes.append(f"{len(short)} answer(s) were too short/vague – explanation lacked depth.")
    imp = [f"Implement and be ready to demo: {r}" for r in missing] + ["Explain design decisions with specific examples (files, functions, libraries).",
           "Add README/comments so reviewers can follow your work quickly."]
    verdict = "Task completed" if score >= 80 else "Partially completed" if score >= 40 else "Not completed"
    return dict(score=score, verdict=verdict, covered=covered, missing=missing, mistakes=mistakes, improvements=imp,
                summary=f"{len(covered)} of {len(reqs)} requirements were evidenced. (Rule-based mode – add ANTHROPIC_API_KEY for deep AI analysis.)")

def analyze(task, transcript):
    c = _client()
    if c:
        try:
            sys = ("You are a strict but fair technical reviewer. Compare the COMPANY REQUIREMENTS with what the intern ACTUALLY did "
                   "(submission + explanation in the review). Return ONLY JSON with keys: score (0-100 int), verdict "
                   "('Task completed'|'Partially completed'|'Not completed'), summary (string), covered (list of requirements done), "
                   "missing (list of requirements not done/not shown), mistakes (list of specific mistakes or wrong explanations), "
                   "improvements (list of concrete actionable suggestions). If the task was not done, say so clearly.")
            r = c.messages.create(model=_model(), max_tokens=1500, system=sys,
                                  messages=[{"role": "user", "content": _ctx(task, transcript)}])
            txt = re.sub(r"^```(json)?|```$", "", r.content[0].text.strip(), flags=re.M).strip()
            d = json.loads(txt)
            for k in ("covered", "missing", "mistakes", "improvements"): d.setdefault(k, [])
            d["score"] = int(d.get("score", 0)); d.setdefault("verdict", "Partially completed"); d.setdefault("summary", "")
            return d
        except Exception as e:
            print("[AI] analysis fallback:", e)
    return _fallback_report(task, transcript)
