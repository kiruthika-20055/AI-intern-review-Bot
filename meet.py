import os, datetime as dt

def create_meet_link(title, start, minutes, attendee_email):
    """Real unique Meet link via Google Calendar API if enabled, else the default room."""
    default = os.getenv("DEFAULT_MEET_LINK", "https://meet.google.com/your-room-code")
    if os.getenv("USE_GOOGLE_CALENDAR", "false").lower() != "true":
        return default
    try:
        from google.oauth2.credentials import Credentials
        from google_auth_oauthlib.flow import InstalledAppFlow
        from google.auth.transport.requests import Request
        from googleapiclient.discovery import build
        scopes = ["https://www.googleapis.com/auth/calendar.events"]
        creds = None
        if os.path.exists("token.json"):
            creds = Credentials.from_authorized_user_file("token.json", scopes)
        if not creds or not creds.valid:
            if creds and creds.expired and creds.refresh_token:
                creds.refresh(Request())
            else:
                creds = InstalledAppFlow.from_client_secrets_file("credentials.json", scopes).run_local_server(port=0)
            open("token.json", "w").write(creds.to_json())
        svc = build("calendar", "v3", credentials=creds)
        ev = {"summary": f"Intern Review: {title}",
              "start": {"dateTime": start.isoformat(), "timeZone": "Asia/Kolkata"},
              "end": {"dateTime": (start + dt.timedelta(minutes=minutes)).isoformat(), "timeZone": "Asia/Kolkata"},
              "attendees": [{"email": attendee_email}],
              "conferenceData": {"createRequest": {"requestId": f"rev{int(start.timestamp())}{abs(hash(attendee_email))%9999}",
                                                   "conferenceSolutionKey": {"type": "hangoutsMeet"}}}}
        r = svc.events().insert(calendarId="primary", body=ev, conferenceDataVersion=1).execute()
        return r.get("hangoutLink", default)
    except Exception as e:
        print("[MEET] Calendar API failed, using default link:", e)
        return default
