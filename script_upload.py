from telethon import TelegramClient
import os
from dotenv import load_dotenv
from pathlib import Path
from FastTelethonhelper import fast_upload

# Load the environment variables from the .env file
load_dotenv()

# Fetch variables securely from the environment
api_id = int(os.getenv("TELEGRAM_API_ID"))
api_hash = os.getenv("TELEGRAM_API_HASH")
target_channel = int(os.getenv("TELEGRAM_CHANNEL"))

# Fail early if environment variables are missing
if not api_id or not api_hash:
    raise ValueError("Missing TELEGRAM_API_ID or TELEGRAM_API_HASH in environment variables!")

client = TelegramClient("session_name", api_id, api_hash)

# --- THE FIX: The Dummy Message Class ---
class ConsoleProgressBar:
    def __init__(self):
        self.id = 1 # Dummy ID just in case the library checks for it
        
    async def edit(self, text):
        # The library sends text formatted for Telegram (with newlines and markdown).
        # We clean it up and print it cleanly on a single line in your terminal.
        clean_text = text.replace('\n', ' | ').replace('`', '').replace('*', '')
        
        # \r forces it to overwrite the same line. The extra spaces ensure clean overwrites.
        print(f"\r{clean_text}                                        ", end="", flush=True)

# Instantiate our fake message object
dummy_msg = ConsoleProgressBar()


async def main():
    mp4_files = sorted([f for f in Path("./telegram").iterdir() if f.is_file() and f.suffix == ".mp4"])
    
    if not mp4_files:
        print("❌ No .mp4 files found in the current directory.")
        return

    count = 1
    season_text = "Season 1 Episode"

    for item in mp4_files:
        message_to_send = (
            "==============================================================\n"
            f"{season_text} {count}\n"
            "⬇⬇⬇⬇⬇⬇⬇⬇⬇⬇⬇⬇⬇⬇⬇⬇⬇⬇⬇⬇⬇⬇⬇⬇⬇⬇⬇⬇⬇⬇\n"
            "=============================================================="
        )
        
        print(f"\n--- Starting process for: {item.name} ---")
        
        await client.send_message(target_channel, message_to_send)
        print("✅ Text message sent.")
        
        print("🚀 Uploading video using fast parallel chunks...")
        
        # 3. Upload chunks using our trick!
        uploaded_file = await fast_upload(
            client, 
            str(item), 
            reply=dummy_msg,   # <-- Trick the library to use our terminal class!
            name=item.name
            # Note: We completely removed 'progress_bar_function' so it uses the 
            # library's built-in ETA and speed calculations.
        )
        
        # Ensure we jump to a new line after the progress bar finishes
        print("\n")
        
        # 4. Post the completed chunks as a playable video
        await client.send_file(
            target_channel,
            uploaded_file, 
            supports_streaming=True
        )
        
        print(f"✅ Successfully uploaded video: {item.name}")
        
        count += 1

with client:
    client.loop.run_until_complete(main())
