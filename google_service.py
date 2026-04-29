"""
google_service.py — Google Calendar, Sheets va Gmail bilan ishlash
OAuth 2.0 token bir marta olinadi va token.json da saqlanadi
"""

import os
import logging
from datetime import datetime, timedelta
from typing import Optional

from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build
import pytz

from config import SPREADSHEET_ID, TIMEZONE

logger = logging.getLogger(__name__)

# Kerakli Google ruxsatlar
SCOPES = [
    "https://www.googleapis.com/auth/calendar",
    "https://www.googleapis.com/auth/gmail.readonly",
    "https://www.googleapis.com/auth/gmail.send",
    "https://www.googleapis.com/auth/spreadsheets",
    "https://www.googleapis.com/auth/drive.readonly",
]

TOKEN_FILE = "token.json"
CREDENTIALS_FILE = "credentials.json"

tz = pytz.timezone(TIMEZONE)


def get_google_creds() -> Optional[Credentials]:
    """
    token.json mavjud bo'lsa — o'sha token ishlatiladi.
    Muddati tugagan bo'lsa — avtomatik yangilanadi.
    Agar token yo'q bo'lsa — browser ochiladi (birinchi marta).
    """
    creds = None

    if os.path.exists(TOKEN_FILE):
        creds = Credentials.from_authorized_user_file(TOKEN_FILE, SCOPES)

    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            try:
                creds.refresh(Request())
                logger.info("Token yangilandi")
            except Exception as e:
                logger.error(f"Token refresh error: {e}")
                creds = None

        if not creds:
            if not os.path.exists(CREDENTIALS_FILE):
                raise FileNotFoundError(
                    "credentials.json topilmadi!\n"
                    "Google Cloud Console'dan yuklab oling va "
                    "bot papkasiga qo'ying."
                )
            flow = InstalledAppFlow.from_client_secrets_file(CREDENTIALS_FILE, SCOPES)
            creds = flow.run_local_server(port=0)

        with open(TOKEN_FILE, "w") as token:
            token.write(creds.to_json())
        logger.info("Token saqlandi: token.json")

    return creds


# ─────────────────────────────────────────────
#  GOOGLE CALENDAR
# ─────────────────────────────────────────────

def get_today_events() -> list[dict]:
    """Bugungi kalendar voqealarini qaytaradi"""
    try:
        creds = get_google_creds()
        service = build("calendar", "v3", credentials=creds)

        now = datetime.now(tz)
        start = now.replace(hour=0, minute=0, second=0, microsecond=0)
        end = now.replace(hour=23, minute=59, second=59, microsecond=0)

        events_result = service.events().list(
            calendarId="primary",
            timeMin=start.isoformat(),
            timeMax=end.isoformat(),
            singleEvents=True,
            orderBy="startTime",
        ).execute()

        events = events_result.get("items", [])
        result = []

        for e in events:
            start_time = e["start"].get("dateTime", e["start"].get("date", ""))
            if "T" in start_time:
                dt = datetime.fromisoformat(start_time)
                time_str = dt.strftime("%H:%M")
            else:
                time_str = "Kun bo'yi"

            result.append({
                "title": e.get("summary", "Nomsiz"),
                "time": time_str,
                "location": e.get("location", ""),
                "description": e.get("description", ""),
            })

        return result

    except Exception as e:
        logger.error(f"Calendar error: {e}")
        return []


def create_calendar_event(title: str, date: str, time: str = "09:00",
                           description: str = "", duration_minutes: int = 60) -> bool:
    """
    Yangi kalendar voqeasi yaratadi.
    date: "YYYY-MM-DD", time: "HH:MM"
    """
    try:
        creds = get_google_creds()
        service = build("calendar", "v3", credentials=creds)

        start_dt = datetime.strptime(f"{date} {time}", "%Y-%m-%d %H:%M")
        start_dt = tz.localize(start_dt)
        end_dt = start_dt + timedelta(minutes=duration_minutes)

        event = {
            "summary": title,
            "description": description,
            "start": {
                "dateTime": start_dt.isoformat(),
                "timeZone": TIMEZONE,
            },
            "end": {
                "dateTime": end_dt.isoformat(),
                "timeZone": TIMEZONE,
            },
            "reminders": {
                "useDefault": False,
                "overrides": [
                    {"method": "popup", "minutes": 30},
                    {"method": "popup", "minutes": 10},
                ],
            },
        }

        service.events().insert(calendarId="primary", body=event).execute()
        logger.info(f"Event created: {title} on {date} {time}")
        return True

    except Exception as e:
        logger.error(f"Create event error: {e}")
        return False


def get_upcoming_events(days: int = 7) -> list[dict]:
    """Keyingi N kunlik voqealar"""
    try:
        creds = get_google_creds()
        service = build("calendar", "v3", credentials=creds)

        now = datetime.now(tz)
        end = now + timedelta(days=days)

        events_result = service.events().list(
            calendarId="primary",
            timeMin=now.isoformat(),
            timeMax=end.isoformat(),
            singleEvents=True,
            orderBy="startTime",
            maxResults=10,
        ).execute()

        events = events_result.get("items", [])
        result = []

        for e in events:
            start_time = e["start"].get("dateTime", e["start"].get("date", ""))
            if "T" in start_time:
                dt = datetime.fromisoformat(start_time)
                date_str = dt.strftime("%d.%m %H:%M")
            else:
                date_str = datetime.strptime(start_time, "%Y-%m-%d").strftime("%d.%m")

            result.append({
                "title": e.get("summary", "Nomsiz"),
                "datetime": date_str,
            })

        return result

    except Exception as e:
        logger.error(f"Upcoming events error: {e}")
        return []


# ─────────────────────────────────────────────
#  GOOGLE SHEETS (Xarajatlar)
# ─────────────────────────────────────────────

SHEET_NAME = "Xarajatlar"
SHEET_HEADERS = ["Sana", "Kategoriya", "Tavsif", "Summa", "Valyuta"]


def _ensure_sheet():
    """Sheets listini tekshiradi, yo'q bo'lsa yaratadi"""
    try:
        creds = get_google_creds()
        service = build("sheets", "v4", credentials=creds)
        spreadsheet = service.spreadsheets().get(spreadsheetId=SPREADSHEET_ID).execute()

        sheet_names = [s["properties"]["title"] for s in spreadsheet["sheets"]]

        if SHEET_NAME not in sheet_names:
            # Yangi list yaratish
            service.spreadsheets().batchUpdate(
                spreadsheetId=SPREADSHEET_ID,
                body={"requests": [{"addSheet": {"properties": {"title": SHEET_NAME}}}]},
            ).execute()

            # Header qatorini qo'shish
            service.spreadsheets().values().update(
                spreadsheetId=SPREADSHEET_ID,
                range=f"{SHEET_NAME}!A1:E1",
                valueInputOption="RAW",
                body={"values": [SHEET_HEADERS]},
            ).execute()
            logger.info(f"Sheet '{SHEET_NAME}' yaratildi")

    except Exception as e:
        logger.error(f"Ensure sheet error: {e}")


def add_expense(amount: float, category: str, description: str,
                currency: str = "UZS", date: str = None) -> bool:
    """Xarajat qatorini Sheets'ga yozadi"""
    try:
        _ensure_sheet()
        creds = get_google_creds()
        service = build("sheets", "v4", credentials=creds)

        if not date:
            date = datetime.now(tz).strftime("%Y-%m-%d")

        row = [date, category, description, amount, currency]

        service.spreadsheets().values().append(
            spreadsheetId=SPREADSHEET_ID,
            range=f"{SHEET_NAME}!A:E",
            valueInputOption="USER_ENTERED",
            insertDataOption="INSERT_ROWS",
            body={"values": [row]},
        ).execute()

        logger.info(f"Expense added: {amount} {currency} — {category}")
        return True

    except Exception as e:
        logger.error(f"Add expense error: {e}")
        return False


def get_monthly_summary(month: int = None, year: int = None) -> dict:
    """Oylik xarajat hisobotini chiqaradi"""
    try:
        _ensure_sheet()
        creds = get_google_creds()
        service = build("sheets", "v4", credentials=creds)

        now = datetime.now(tz)
        if not month:
            month = now.month
        if not year:
            year = now.year

        result = service.spreadsheets().values().get(
            spreadsheetId=SPREADSHEET_ID,
            range=f"{SHEET_NAME}!A2:E",
        ).execute()

        rows = result.get("values", [])
        monthly_total = 0
        by_category = {}

        for row in rows:
            if len(row) < 4:
                continue
            try:
                row_date = datetime.strptime(row[0], "%Y-%m-%d")
                if row_date.month == month and row_date.year == year:
                    amount = float(str(row[3]).replace(",", "").replace(" ", ""))
                    category = row[1] if len(row) > 1 else "Boshqa"
                    monthly_total += amount
                    by_category[category] = by_category.get(category, 0) + amount
            except (ValueError, IndexError):
                continue

        return {
            "total": monthly_total,
            "by_category": by_category,
            "month": month,
            "year": year,
            "currency": "UZS",
        }

    except Exception as e:
        logger.error(f"Monthly summary error: {e}")
        return {"total": 0, "by_category": {}, "month": month or 1, "year": year or 2024, "currency": "UZS"}


def get_recent_expenses(limit: int = 5) -> list[dict]:
    """Oxirgi N ta xarajatni qaytaradi"""
    try:
        _ensure_sheet()
        creds = get_google_creds()
        service = build("sheets", "v4", credentials=creds)

        result = service.spreadsheets().values().get(
            spreadsheetId=SPREADSHEET_ID,
            range=f"{SHEET_NAME}!A2:E",
        ).execute()

        rows = result.get("values", [])
        rows = rows[-limit:] if len(rows) > limit else rows

        return [
            {
                "date": r[0] if len(r) > 0 else "",
                "category": r[1] if len(r) > 1 else "",
                "description": r[2] if len(r) > 2 else "",
                "amount": r[3] if len(r) > 3 else "0",
                "currency": r[4] if len(r) > 4 else "UZS",
            }
            for r in rows
        ]

    except Exception as e:
        logger.error(f"Recent expenses error: {e}")
        return []


# ─────────────────────────────────────────────
#  GMAIL
# ─────────────────────────────────────────────

def get_unread_emails(max_results: int = 5) -> list[dict]:
    """O'qilmagan xatlarni ro'yxatini qaytaradi"""
    try:
        creds = get_google_creds()
        service = build("gmail", "v1", credentials=creds)

        result = service.users().messages().list(
            userId="me",
            q="is:unread",
            maxResults=max_results,
        ).execute()

        messages = result.get("messages", [])
        emails = []

        for msg in messages:
            msg_data = service.users().messages().get(
                userId="me",
                id=msg["id"],
                format="metadata",
                metadataHeaders=["Subject", "From", "Date"],
            ).execute()

            headers = {h["name"]: h["value"] for h in msg_data.get("payload", {}).get("headers", [])}
            emails.append({
                "subject": headers.get("Subject", "Mavzusiz"),
                "from": headers.get("From", "Noma'lum"),
                "date": headers.get("Date", ""),
            })

        return emails

    except Exception as e:
        logger.error(f"Gmail error: {e}")
        return []


def get_email_stats() -> dict:
    """O'qilmagan xatlar soni"""
    try:
        creds = get_google_creds()
        service = build("gmail", "v1", credentials=creds)

        result = service.users().getProfile(userId="me").execute()
        labels = service.users().labels().get(userId="me", id="INBOX").execute()

        return {
            "email": result.get("emailAddress", ""),
            "unread": labels.get("messagesUnread", 0),
            "total": labels.get("messagesTotal", 0),
        }

    except Exception as e:
        logger.error(f"Email stats error: {e}")
        return {"email": "", "unread": 0, "total": 0}
