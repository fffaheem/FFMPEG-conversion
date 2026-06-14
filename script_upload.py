import os
from queue import Empty
import subprocess
import time
from pathlib import Path

from dotenv import load_dotenv
from FastTelethonhelper import fast_upload
from telethon import TelegramClient, utils

# Load the environment variables from the .env file
load_dotenv()

FOLDER_NAME = "./telegram-TBBT-S06"
MKV_FOLDER_NAME = "./TBBT-S06"
season_text = "S06E"
count_start = 1
count_end = -1 #-1 means complete to the end

api_id = int(os.getenv("TELEGRAM_API_ID"))
api_hash = os.getenv("TELEGRAM_API_HASH")
target_channel = int(os.getenv("TELEGRAM_CHANNEL"))

if not api_id or not api_hash:
    raise ValueError(
        "Missing TELEGRAM_API_ID or TELEGRAM_API_HASH in environment variables!"
    )

client = TelegramClient("session_name", api_id, api_hash)


# This class tricks FastTelethonhelper into rendering the progress bar in the terminal
class ConsoleProgressBar:
    def __init__(self):
        self.id = 1

    async def edit(self, text):
        clean_text = text.replace("\n", " | ").replace("`", "").replace("*", "")
        print(
            f"\r{clean_text}                                        ",
            end="",
            flush=True,
        )


dummy_msg = ConsoleProgressBar()


# Helper function to cleanly format seconds into a readable string
def format_duration(seconds):
    mins, secs = divmod(int(seconds), 60)
    if mins > 0:
        return f"{mins}m {secs}s"
    return f"{secs}s"


async def main():
    # Start the master clock for the entire script execution
    script_start_time = time.time()

    # Looks for the finished .mp4 files inside the 'telegram' folder
    mp4_files = sorted(
        [
            f
            for f in Path(FOLDER_NAME).iterdir()
            if f.is_file() and f.suffix == ".mp4"
        ]
    )

    if not mp4_files:
        print("❌ No .mp4 files found in the ./telegram directory.")
        return

    count = 1

    for item in mp4_files:
        if count < count_start:
            count += 1
            continue
            
        if count_end != -1 and count > count_end:
            count += 1
            break
        
        # Start clock for this specific loop iteration (one single pass)
        pass_start_time = time.time()
        
        # d = item.stem.split("-")
        title = " ".join(item.stem.split(".")[5::]).split("1080p")[0]

        message_to_send = (
            "==============================================================\n"
            f"{season_text}{count:02d} - {title}\n"
            "⬇⬇⬇⬇⬇⬇⬇⬇⬇⬇⬇⬇⬇⬇⬇⬇⬇⬇⬇⬇⬇⬇⬇⬇⬇⬇⬇⬇⬇⬇\n"
            "=============================================================="
        )

        print(f"\n==================================================")
        print(f"🎬 Starting process for: {item.name}")
        print(f"==================================================")

        # 1. Send the intro text message
        await client.send_message(target_channel, message_to_send)
        print("✅ Text message sent.")

        # ==========================================
        # MKV UPLOAD LOGIC (With Fast Upload & Timing)
        # ==========================================
        mkv_file = Path(f"./{MKV_FOLDER_NAME}/{item.stem}.mkv")
        mkv_duration_str = "N/A"
        
        if mkv_file.exists():
            print(f"📦 Fast uploading MKV file: {mkv_file.name}...")
            mkv_start_time = time.time()
            
            # Utilizing fast parallel upload with the console progress bar for the MKV
            uploaded_mkv = await fast_upload(
                client, str(mkv_file), reply=dummy_msg, name=mkv_file.name
            )
            
            # Send as a document since we don't care about streaming/thumbnails
            await client.send_file(
                target_channel,
                uploaded_mkv,
                force_document=True 
            )
            
            mkv_end_time = time.time()
            mkv_duration_str = format_duration(mkv_end_time - mkv_start_time)
            print(f"\n✅ Successfully uploaded MKV document in: {mkv_duration_str}")
        else:
            print(f"⚠️ No matching MKV found at {mkv_file}. Skipping MKV upload.")

        # 2. Generate a thumbnail screenshot using FFmpeg for the MP4
        print("📸 Generating thumbnail for Telegram Web compatibility...")
        thumb_path = f"thumb_{item.stem}.jpg"

        subprocess.run(
            [
                "ffmpeg",
                "-y",
                "-i",
                str(item),
                "-ss",
                "00:05:00",
                "-vframes",
                "1",
                thumb_path,
            ],
            capture_output=True,
        )

        # ==========================================
        # MP4 UPLOAD LOGIC (With Timing)
        # ==========================================
        print("🚀 Fast uploading streaming video using parallel chunks...")
        mp4_start_time = time.time()

        uploaded_mp4 = await fast_upload(
            client, str(item), reply=dummy_msg, name=item.name
        )

        print("\n⚙️ Fetching video metadata...")
        video_attributes, _ = utils.get_attributes(str(item), supports_streaming=True)

        # Finalize the MP4 upload with thumbnail and strict video MIME type
        await client.send_file(
            target_channel,
            uploaded_mp4,
            attributes=video_attributes,
            mime_type="video/mp4",
            thumb=thumb_path if os.path.exists(thumb_path) else None,
        )
        
        mp4_end_time = time.time()
        mp4_duration_str = format_duration(mp4_end_time - mp4_start_time)
        print(f"✅ Successfully uploaded streaming video in: {mp4_duration_str}")

        # 5. Clean up the temporary thumbnail image
        if os.path.exists(thumb_path):
            os.remove(thumb_path)

        # Calculate total time spent on this entire single pass
        pass_end_time = time.time()
        pass_duration_str = format_duration(pass_end_time - pass_start_time)
        
        # Print nice summary for the completed loop iteration
        print(f"\n⏱️ --- TIME SUMMARY FOR EPISODE {count:02d} ---")
        print(f" ├─ MKV Upload Time: {mkv_duration_str}")
        print(f" ├─ MP4 Upload Time: {mp4_duration_str}")
        print(f" └─ Total Pass Time: {pass_duration_str}")
        print(f"--------------------------------------------------\n")

        count += 1

    # End master clock and report execution metrics
    script_end_time = time.time()
    total_execution_str = format_duration(script_end_time - script_start_time)
    print(f"🎉 All files processed!")
    print(f"⌛ Total script execution time: {total_execution_str}")


with client:
    client.loop.run_until_complete(main())
