"""
gemini_service.py — Gemini AI integration
Voice, image, document and text analysis
"""

import json
import base64
import logging
from datetime import datetime
import google.generativeai as genai
from config import GEMINI_API_KEY, TIMEZONE
import pytz

genai.configure(api_key=GEMINI_API_KEY)
model = genai.GenerativeModel("gemini-2.0-flash")
logger = logging.getLogger(__name__)
tz = pytz.timezone(TIMEZONE)


def _now_str() -> str:
    return datetime.now(tz).strftime("%Y-%m-%d %H:%M")


def _clean_json(text: str) -> str:
    text = text.strip()
    if text.startswith("```"):
        lines = text.split("\n")
        lines = [l for l in lines if not l.startswith("```")]
        text = "\n".join(lines)
    return text.strip()


async def analyze_voice(audio_bytes: bytes) -> dict:
    """Analyze Telegram voice message (.ogg) and detect intent"""
    try:
        audio_b64 = base64.b64encode(audio_bytes).decode()

        prompt = f"""
You are a personal assistant. Listen to this voice message and respond ONLY with JSON:

{{
  "text": "what was said",
  "intent": "calendar or expense or reminder or general",
  "data": {{}}
}}

Intent types and data structure:
- calendar: {{"title": "event name", "date": "YYYY-MM-DD", "time": "HH:MM", "description": ""}}
- expense:  {{"amount": 50.00, "category": "Food", "description": "details"}}
- reminder: {{"text": "reminder text", "date": "YYYY-MM-DD", "time": "HH:MM"}}
- general:  {{}}

Categories: Food | Transport | Business | Housing | Clothing | Health | Education | Other

Current time: {_now_str()}
Return ONLY valid JSON, nothing else.
"""

        response = model.generate_content([
            {"mime_type": "audio/ogg", "data": audio_b64},
            prompt
        ])

        result = json.loads(_clean_json(response.text))
        logger.info(f"Voice analyzed: intent={result.get('intent')} text={result.get('text', '')[:40]}")
        return result

    except Exception as e:
        logger.error(f"Voice analysis error: {e}")
        return {"text": "Could not understand voice message.", "intent": "general", "data": {}}


async def analyze_receipt(image_bytes: bytes) -> dict:
    """Extract expense data from a receipt or invoice photo"""
    try:
        image_b64 = base64.b64encode(image_bytes).decode()

        prompt = """
Analyze this receipt or invoice image and return ONLY this JSON:

{
  "total": 85.50,
  "currency": "USD",
  "items": [
    {"name": "item name", "price": 25.00, "qty": 2}
  ],
  "category": "Food",
  "date": "YYYY-MM-DD or null",
  "store": "store name or null"
}

Categories: Food | Transport | Housing | Clothing | Health | Education | Business | Other
Return ONLY valid JSON, nothing else.
"""

        response = model.generate_content([
            {"mime_type": "image/jpeg", "data": image_b64},
            prompt
        ])

        result = json.loads(_clean_json(response.text))
        logger.info(f"Receipt analyzed: total={result.get('total')} {result.get('currency')}")
        return result

    except Exception as e:
        logger.error(f"Receipt analysis error: {e}")
        return {"total": 0, "currency": "USD", "items": [], "category": "Other",
                "date": None, "store": None}


async def analyze_document(file_bytes: bytes, mime_type: str, filename: str = "") -> str:
    """Analyze a PDF or image document and return a structured summary"""
    try:
        file_b64 = base64.b64encode(file_bytes).decode()

        prompt = f"""
Document: {filename}

Analyze this document and respond in English with the following structure:

📋 **SUMMARY**
(2-3 sentences about the main purpose)

🔑 **KEY POINTS**
• (key point 1)
• (key point 2)
• (key point 3)

📅 **IMPORTANT DATES / NUMBERS**
(if any)

✅ **ACTION REQUIRED**
(if any action needs to be taken)
"""

        response = model.generate_content([
            {"mime_type": mime_type, "data": file_b64},
            prompt
        ])

        return response.text

    except Exception as e:
        logger.error(f"Document analysis error: {e}")
        return "❌ Error analyzing document."


async def parse_text_intent(text: str) -> dict:
    """Detect intent from a text message"""
    try:
        prompt = f"""
You are a personal assistant. Analyze this message and return ONLY JSON:

"{text}"

{{
  "intent": "calendar or expense or reminder or query or general",
  "lang": "en or uz or ru",
  "data": {{}}
}}

Intent types:
- calendar:  {{"title": "", "date": "YYYY-MM-DD", "time": "HH:MM", "description": ""}}
- expense:   {{"amount": 0.00, "category": "Food", "description": ""}}
- reminder:  {{"text": "", "date": "YYYY-MM-DD", "time": "HH:MM"}}
- query:     {{"type": "calendar or expenses or gmail or all"}}
- general:   {{}}

Categories: Food | Transport | Business | Housing | Clothing | Health | Education | Other

Detect the language of the message and set "lang" accordingly:
- Uzbek text → "uz"
- English text → "en"
- Russian text → "ru"

Examples:
"lunch $35" → expense, Food, lang=en
"tushlik 35000" → expense, Food, lang=uz
"meeting tomorrow at 10am" → calendar, lang=en
"ertaga 10da uchrashuv" → calendar, lang=uz
"what are my meetings today?" → query, calendar, lang=en
"bugungi uchrashuvlarim" → query, calendar, lang=uz

Current time: {_now_str()}
Return ONLY valid JSON, nothing else.
"""

        response = model.generate_content(prompt)
        result = json.loads(_clean_json(response.text))
        logger.info(f"Text intent: {result.get('intent')} lang={result.get('lang')}")
        return result

    except Exception as e:
        logger.error(f"Text intent error: {e}")
        return {"intent": "general", "lang": "en", "data": {}}


async def generate_reply(user_text: str, context: str = "", lang: str = "en") -> str:
    """Generate a conversational reply in the same language as the user"""
    try:
        lang_instruction = {
            "uz": "Reply in Uzbek language.",
            "ru": "Reply in Russian language.",
            "en": "Reply in English.",
        }.get(lang, "Reply in the same language as the user's message.")

        prompt = f"""
You are a helpful personal assistant. {lang_instruction}
Give a short, useful reply.
{f'Context: {context}' if context else ''}

User: {user_text}
"""
        response = model.generate_content(prompt)
        return response.text

    except Exception as e:
        logger.error(f"Reply generation error: {e}")
        return "Sorry, I couldn't process that right now."
