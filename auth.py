"""
auth.py — Google OAuth 2.0 birinchi marta sozlash

Faqat BIR MARTA ishga tushirasiz:
    python auth.py

Browser ochiladi → Google hisobingizga kirasiz → ruxsat berasiz
token.json avtomatik saqlanadi.
Keyingi safar main.py to'g'ridan-to'g'ri ishlaydi.
"""

from google_service import get_google_creds

if __name__ == "__main__":
    print("=" * 50)
    print("Google OAuth 2.0 sozlash")
    print("=" * 50)
    print()
    print("Browser ochiladi. Google hisobingizga kiring va ruxsat bering.")
    print()

    try:
        creds = get_google_creds()
        print("✅ Muvaffaqiyatli! token.json saqlandi.")
        print()
        print("Endi botni ishga tushiring:")
        print("    python main.py")
    except FileNotFoundError as e:
        print(f"❌ Xato: {e}")
        print()
        print("credentials.json faylini quyidagicha oling:")
        print("1. console.cloud.google.com ga kiring")
        print("2. Loyihangizni tanlang")
        print("3. APIs & Services → Credentials")
        print("4. OAuth 2.0 Client IDs → Download JSON")
        print("5. Faylni 'credentials.json' deb nomlang va bu papkaga qo'ying")
    except Exception as e:
        print(f"❌ Kutilmagan xato: {e}")
