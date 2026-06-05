from telethon import TelegramClient
import os
from dotenv import load_dotenv
from pathlib import Path

# Load the environment variables from the .env file
load_dotenv()

# Fetch variables securely from the environment
api_id = int(os.getenv("TELEGRAM_API_ID"))
api_hash = os.getenv("TELEGRAM_API_HASH")
target_channel = int(os.getenv("TELEGRAM_CHANNEL"))
#Define your target channel here
# Use the string username for public channels:
# TELEGRAM_CHANNEL = @my_awesome_channel 
# OR use the integer ID for private channels (uncomment line below if private):
# Take the number in the middle (1827364519), put -100 in front of it, and convert it to an integer.
# Your Channel ID: -1001827364519
# TELEGRAM_CHANNEL = -1001827364519

# Fail early if environment variables are missing
if not api_id or not api_hash:
    raise ValueError("Missing TELEGRAM_API_ID or TELEGRAM_API_HASH in environment variables!")

client = TelegramClient("session_name", api_id, api_hash)

def upload_progress(current, total):
    print(f"Uploading... {current * 100 / total:.2f}%", end='\r')

async def main():
    # Gather and sort all .mkv files in the current folder 
    # Sorting ensures episodes upload in the correct numerical order!
    mkv_files = sorted([f for f in Path("./telegram").iterdir() if f.is_file() and f.suffix == ".mp4"])
    
    if not mkv_files:
        print("❌ No .mp4 files found in the current directory.")
        return

    count = 1
    season_text = "Season 1 Episode"

    # The Single Combined Loop
    for item in mkv_files:
        # 1. Prepare the text message format
        # Using \n creates a new line in the Telegram message
        message_to_send = (
            "==============================================================\n"
            f"{season_text} {count}\n"
            "⬇⬇⬇⬇⬇⬇⬇⬇⬇⬇⬇⬇⬇⬇⬇⬇⬇⬇⬇⬇⬇⬇⬇⬇⬇⬇⬇⬇⬇⬇\n"
            "=============================================================="
        )
        
        print(f"\n--- Starting process for: {item.name} ---")
        
        # 2. Send the text message first
        await client.send_message(target_channel, message_to_send)
        print("✅ Text message sent.")
        
        # 3. Upload the actual video file as a streamable video
        # Convert the Path object 'item' to a string for Telethon
        await client.send_file(
            target_channel,
            str(item), 
            supports_streaming=True,          # Tells Telegram you can stream it
            video_note=False,                 # Ensures it's a standard video, not a circle video
            progress_callback=upload_progress
        )
        
        print(f"\n✅ Successfully uploaded video: {item.name}")
        
        # Increment the episode counter for the next loop
        count += 1

with client:
    client.loop.run_until_complete(main())
