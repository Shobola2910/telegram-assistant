"""
start.py — Render.com startup script
Reads CREDENTIALS_JSON and TOKEN_JSON from environment variables
and writes them to files before starting the bot.

Start command on Render: python start.py
"""

import os
import base64
import subprocess
import sys


def write_file_from_env(env_key: str, filename: str):
    value = os.environ.get(env_key)
    if not value:
        print(f"⚠️  {env_key} not set in environment — skipping {filename}")
        return
    try:
        decoded = base64.b64decode(value)
        with open(filename, "wb") as f:
            f.write(decoded)
        print(f"✅ {filename} written from {env_key}")
    except Exception as e:
        print(f"❌ Failed to write {filename}: {e}")


if __name__ == "__main__":
    print("🚀 Setting up environment...")

    write_file_from_env("CREDENTIALS_JSON", "credentials.json")
    write_file_from_env("TOKEN_JSON", "token.json")

    print("▶️  Starting bot...")
    result = subprocess.run([sys.executable, "main.py"])
    sys.exit(result.returncode)
