from telethon import TelegramClient, utils
import os
import subprocess
from dotenv import load_dotenv
from pathlib import Path
from FastTelethonhelper import fast_upload

# Load the environment variables from the .env file
load_dotenv()

api_id = int(os.getenv("TELEGRAM_API_ID"))
api_hash = os.getenv("TELEGRAM_API_HASH")
target_channel = int(os.getenv("TELEGRAM_CHANNEL"))

if not api_id or not api_hash:
    raise ValueError("Missing TELEGRAM_API_ID or TELEGRAM_API_HASH in environment variables!")

client = TelegramClient("session_name", api_id, api_hash)

# This class tricks FastTelethonhelper into rendering the progress bar in the terminal
class ConsoleProgressBar:
    def __init__(self):
        self.id = 1 
        
    async def edit(self, text):
        clean_text = text.replace('\n', ' | ').replace('`', '').replace('*', '')
        print(f"\r{clean_text}                                        ", end="", flush=True)

dummy_msg = ConsoleProgressBar()

async def main():
    # Looks for the finished .mp4 files inside the 'telegram' folder
    mp4_files = sorted([f for f in Path("./telegram").iterdir() if f.is_file() and f.suffix == ".mp4"])
    
    if not mp4_files:
        print("❌ No .mp4 files found in the ./telegram directory.")
        return

    count = 1
    season_text = "Season 2 Episode"

    for item in mp4_files:
        message_to_send = (
            "==============================================================\n"
            f"{season_text} {count}\n"
            "⬇⬇⬇⬇⬇⬇⬇⬇⬇⬇⬇⬇⬇⬇⬇⬇⬇⬇⬇⬇⬇⬇⬇⬇⬇⬇⬇⬇⬇⬇\n"
            "=============================================================="
        )
        
        print(f"\n--- Starting process for: {item.name} ---")
        
        # 1. Send the intro text message
        await client.send_message(target_channel, message_to_send)
        print("✅ Text message sent.")
        
        # 2. Generate a thumbnail screenshot using FFmpeg
        print("📸 Generating thumbnail for Telegram Web compatibility...")
        thumb_path = f"thumb_{item.stem}.jpg"
        
        # Takes a screenshot exactly 5 minutes (00:05:00) into the episode
        subprocess.run([
            "ffmpeg", "-y", "-i", str(item), 
            "-ss", "00:05:00", "-vframes", "1", 
            thumb_path
        ], capture_output=True)

        print("🚀 Uploading video using fast parallel chunks...")
        
        # 3. Fast Upload
        uploaded_file = await fast_upload(
            client, 
            str(item), 
            reply=dummy_msg,   
            name=item.name
        )
        
        print("\n⚙️ Fetching video metadata...")
        video_attributes, _ = utils.get_attributes(
            str(item), 
            supports_streaming=True
        )
        
        # 4. Finalize the upload with thumbnail and strict video MIME type
        await client.send_file(
            target_channel,
            uploaded_file, 
            attributes=video_attributes,
            mime_type="video/mp4",
            thumb=thumb_path if os.path.exists(thumb_path) else None 
        )
        
        print(f"✅ Successfully uploaded streaming video: {item.name}")
        
        # 5. Clean up the temporary thumbnail image
        if os.path.exists(thumb_path):
            os.remove(thumb_path)
            
        count += 1

with client:
    client.loop.run_until_complete(main())
