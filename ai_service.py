"""
ai_service.py — Groq AI integration (FREE, fast)
Replaces Gemini and OpenAI
"""

import json
import logging
from datetime import datetime
from openai import AsyncOpenAI  # Groq uses OpenAI-compatible SDK
from config import GROQ_API_KEY, TIMEZONE
import pytz

# Groq uses OpenAI SDK but with different base URL
client = AsyncOpenAI(
    api_key=GROQ_API_KEY,
    base_url="https://api.groq.com/openai/v1"
)

logger = logging.getLogger(__name__)
tz = pytz.timezone(TIMEZONE)
MODEL = "llama-3.3-70b-versatile"  # Best free model on Groq


def _now_str() -> str:
    return datetime.now(tz).strftime("%Y-%m-%d %H:%M")


def _clean_json(text: str) -> str:
    text = text.strip()
    if text.startswith("```"):
        lines = text.split("\n")
        lines = [l for l in lines if not l.startswith("```")]
        text = "\n".join(lines)
    return text.strip()


async def chat(system: str, user: str) -> str:
    """Base Groq chat call"""
    response = await client.chat.completions.create(
        model=MODEL,
        messages=[
            {"role": "system", "content": system},
            {"role": "user", "content": user},
        ],
        max_tokens=1000,
        temperature=0.7,
    )
    return response.choices[0].message.content or ""


async def parse_text_intent(text: str) -> dict:
    """Detect intent from a text message"""
    try:
        system = f"""You are a personal assistant. Analyze the user message and return ONLY valid JSON.

Format:
{{
  "intent": "calendar or expense or reminder or query or general",
  "lang": "en or uz or ru",
  "data": {{}}
}}

Intent data:
- calendar:  {{"title": "", "date": "YYYY-MM-DD", "time": "HH:MM", "description": ""}}
- expense:   {{"amount": 0.00, "category": "Food", "description": ""}}
- reminder:  {{"text": "", "date": "YYYY-MM-DD", "time": "HH:MM"}}
- query:     {{"type": "calendar or expenses or gmail or all"}}
- general:   {{}}

Categories: Food | Transport | Business | Housing | Clothing | Health | Education | Other
Detect language: Uzbek→uz, English→en, Russian→ru
Current time: {_now_str()}
Return ONLY JSON, no explanation."""

        result_text = await chat(system, text)
        result = json.loads(_clean_json(result_text))
        logger.info(f"Intent: {result.get('intent')} lang={result.get('lang')}")
        return result

    except Exception as e:
        logger.error(f"parse_text_intent error: {e}")
        return {"intent": "general", "lang": "en", "data": {}}


async def generate_reply(user_text: str, context: str = "", lang: str = "en") -> str:
    """Conversational reply in the same language as user"""
    try:
        lang_map = {"uz": "Uzbek", "ru": "Russian", "en": "English"}
        lang_name = lang_map.get(lang, "English")

        system = (
            f"You are a helpful, friendly personal assistant. "
            f"Always reply in {lang_name}. Be concise, warm, and natural. "
            f"Current time: {_now_str()}"
        )
        if context:
            system += f"\nContext: {context}"

        return await chat(system, user_text)

    except Exception as e:
        logger.error(f"generate_reply error: {e}")
        return "Sorry, I couldn't process that right now."


async def analyze_voice(audio_bytes: bytes) -> dict:
    """Voice transcription via Groq Whisper then intent detection"""
    try:
        import io
        audio_file = io.BytesIO(audio_bytes)
        audio_file.name = "voice.ogg"

        transcript = await client.audio.transcriptions.create(
            model="whisper-large-v3",
            file=audio_file,
        )
        text = transcript.text
        logger.info(f"Voice transcribed: {text[:60]}")

        result = await parse_text_intent(text)
        result["text"] = text
        return result

    except Exception as e:
        logger.error(f"analyze_voice error: {e}")
        return {"text": "Could not understand voice.", "intent": "general", "data": {}}


async def analyze_receipt(image_bytes: bytes) -> dict:
    """Receipt analysis — Groq vision (llama-4)"""
    try:
        import base64
        image_b64 = base64.b64encode(image_bytes).decode()

        response = await client.chat.completions.create(
            model="meta-llama/llama-4-scout-17b-16e-instruct",
            messages=[{
                "role": "user",
                "content": [
                    {
                        "type": "image_url",
                        "image_url": {"url": f"data:image/jpeg;base64,{image_b64}"}
                    },
                    {
                        "type": "text",
                        "text": 'Analyze this receipt. Return ONLY JSON: {"total": 0, "currency": "USD", "items": [{"name": "", "price": 0, "qty": 1}], "category": "Food", "date": null, "store": null}. Categories: Food|Transport|Housing|Clothing|Health|Education|Business|Other'
                    }
                ]
            }],
            max_tokens=500,
        )

        result = json.loads(_clean_json(response.choices[0].message.content))
        logger.info(f"Receipt: {result.get('total')} {result.get('currency')}")
        return result

    except Exception as e:
        logger.error(f"analyze_receipt error: {e}")
        return {"total": 0, "currency": "USD", "items": [], "category": "Other",
                "date": None, "store": None}


async def analyze_document(file_bytes: bytes, mime_type: str, filename: str = "") -> str:
    """Analyze PDF document"""
    try:
        if mime_type == "application/pdf":
            import io
            try:
                import pypdf
                reader = pypdf.PdfReader(io.BytesIO(file_bytes))
                text = "\n".join(p.extract_text() or "" for p in reader.pages[:10])
                text = text[:4000]
            except Exception:
                return "❌ Could not read PDF."

            system = "You are a document analyst. Summarize in English with sections: 📋 SUMMARY, 🔑 KEY POINTS, 📅 IMPORTANT DATES/NUMBERS, ✅ ACTION REQUIRED."
            return await chat(system, f"Document: {filename}\n\n{text}")

        return "❌ Unsupported file type for document analysis."

    except Exception as e:
        logger.error(f"analyze_document error: {e}")
        return "❌ Error analyzing document."
