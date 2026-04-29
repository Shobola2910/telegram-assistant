# ============================================================
#  config.py — works both locally and on Render.com
# ============================================================
import os

# --- Telegram ---
BOT_TOKEN = os.environ.get("BOT_TOKEN", "8628617703:AAFiHIMw7o4h4wMc_Xp9x-UXDxYLjojqB04")
YOUR_TELEGRAM_ID = int(os.environ.get("YOUR_TELEGRAM_ID", "5639519356"))

# --- Groq AI (FREE) ---
GROQ_API_KEY = os.environ.get("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", "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")

# --- Google Sheets ---
SPREADSHEET_ID = os.environ.get("SPREADSHEET_ID", "1o1CHM4vUpTjqSchopLGTkBQo_bpvrWsBw9R22986H5w")

# --- Timezone ---
TIMEZONE = os.environ.get("TIMEZONE", "Asia/Tashkent")

# --- Daily briefing time ---
BRIEFING_HOUR = 8
BRIEFING_MINUTE = 0

# --- Expense categories ---
CATEGORIES = {
    "Food": "Food",
    "Transport": "Transport",
    "Business": "Business",
    "Housing": "Housing",
    "Clothing": "Clothing",
    "Health": "Health",
    "Education": "Education",
    "Other": "Other",
}
