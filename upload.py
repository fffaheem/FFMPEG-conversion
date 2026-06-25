# upload even if original is more than 2gb

from numbers import Number
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

FOLDER_NAME = "./telegram-TBBT-S10"
MKV_FOLDER_NAME = "./TBBT-S10"

# Create a local temporary directory to hold the split chunks (Bypasses F: drive permission errors)
TEMP_SPLIT_DIR = Path("./temp_chunks")
TEMP_SPLIT_DIR.mkdir(exist_ok=True)

season_text = "S010E"
count_start = 1
count_end = -1#-1 means complete to the end
ORIGINAL_FILE_TYPE = "mkv"
api_id = int(os.getenv("TELEGRAM_API_ID"))
api_hash = os.getenv("TELEGRAM_API_HASH")
target_channel = int(os.getenv("TELEGRAM_CHANNEL"))

# 2GB is 2,147,483,648 bytes. We set the limit to 1.9 GB (2,040,109,465 bytes) for safety.
MAX_FILE_SIZE = 1.9 * 1024 * 1024 * 1024 

if not api_id or not api_hash:
    raise ValueError(
        "Missing TELEGRAM_API_ID or TELEGRAM_API_HASH in environment variables!"
    )

client = TelegramClient("session_name", api_id, api_hash)


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


def format_duration(seconds):
    mins, secs = divmod(int(seconds), 60)
    if mins > 0:
        return f"{mins}m {secs}s"
    return f"{secs}s"


# Helper function to split a large file into smaller chunks in a safe local directory
def split_file(file_path: Path, chunk_size: int, output_dir: Path) -> list[Path]:
    part_files = []
    part_num = 1
    
    print(f"✂️ File exceeds 2GB. Splitting into chunks of {chunk_size / (1024**3):.2f} GB...")
    
    with open(file_path, 'rb') as infile:
        while True:
            chunk = infile.read(int(chunk_size))
            if not chunk:
                break
                
            # Writes to the temporary folder instead of the F: drive
            part_name = output_dir / f"{file_path.name}.{part_num:03d}"
            with open(part_name, 'wb') as outfile:
                outfile.write(chunk)
                
            part_files.append(part_name)
            print(f"   ├─ Generated: {part_name.name}")
            part_num += 1
            
    return part_files

def upload_message(item, count):
    # For Naruto
    # title = int(item.stem.split("-")[1].lstrip().rstrip().split(" ")[0].lstrip().rstrip())

    # message_to_send = (
    #     "==============================================================\n"
    #     f"{season_text}{count:02d} - {title:03d}\n"
    #     "⬇⬇⬇⬇⬇⬇⬇⬇⬇⬇⬇⬇⬇⬇⬇⬇⬇⬇⬇⬇⬇⬇⬇⬇⬇⬇⬇⬇⬇⬇\n"
    #     "=============================================================="
    # )

    # For Big bang theory
    title = " ".join(item.stem.split(".")[5::]).split("1080p")[0]

    message_to_send = (
        "==============================================================\n"
        f"{season_text}{count:02d} - {title}\n"
        "⬇⬇⬇⬇⬇⬇⬇⬇⬇⬇⬇⬇⬇⬇⬇⬇⬇⬇⬇⬇⬇⬇⬇⬇⬇⬇⬇⬇⬇⬇\n"
        "=============================================================="
    )

    return message_to_send


async def main():
    script_start_time = time.time()

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
        
        pass_start_time = time.time()

        message_to_send = upload_message(item,count)

        print(f"\n==================================================")
        print(f"🎬 Starting process for: {item.name}")
        print(f"==================================================")

        # 1. Send the intro text message
        await client.send_message(target_channel, message_to_send)
        print("✅ Text message sent.")

        # ==========================================
        # MKV UPLOAD LOGIC (With Dynamic Splitting & Albums)
        # ==========================================
        mkv_file = Path(f"{MKV_FOLDER_NAME}/{item.stem}.{ORIGINAL_FILE_TYPE}")
        mkv_duration_str = "N/A"
        
        if mkv_file.exists():
            mkv_start_time = time.time()
            file_size = mkv_file.stat().st_size
            
            if file_size > MAX_FILE_SIZE:
                # Split the file into pieces inside the safe temporary folder
                split_parts = split_file(mkv_file, MAX_FILE_SIZE, TEMP_SPLIT_DIR)
                
                uploaded_media_objects = []
                
                # Upload each piece sequentially but don't send to channel yet
                for idx, part in enumerate(split_parts, start=1):
                    print(f"📦 Fast uploading part {idx}/{len(split_parts)}: {part.name}...")
                    
                    uploaded_part = await fast_upload(
                        client, str(part), reply=dummy_msg, name=part.name
                    )
                    uploaded_media_objects.append(uploaded_part)
                
                # Send all uploaded parts grouped together as a single Album
                print(f"\n🚀 Sending grouped album to Telegram...")
                await client.send_file(
                    target_channel,
                    uploaded_media_objects, # Passing a list creates an album automatically
                    force_document=True,
                    caption=f"📁 **Split File:** Please download all parts and extract the `.001` file to combine them."
                )
                
                # Delete the temporary parts AFTER successful album transmission
                print("🧹 Cleaning up temporary split files...")
                for part in split_parts:
                    if part.exists():
                        part.unlink()
                        
                print(f"✅ All parts grouped and uploaded successfully.")
                
            else:
                # Normal upload for files under 2GB
                print(f"📦 Fast uploading MKV file: {mkv_file.name}...")
                uploaded_mkv = await fast_upload(
                    client, str(mkv_file), reply=dummy_msg, name=mkv_file.name
                )
                await client.send_file(
                    target_channel,
                    uploaded_mkv,
                    force_document=True 
                )
            
            mkv_end_time = time.time()
            mkv_duration_str = format_duration(mkv_end_time - mkv_start_time)
        else:
            print(f"⚠️ No matching MKV found at {mkv_file}. Skipping MKV upload.")

        # 2. Generate a thumbnail screenshot using FFmpeg for the MP4
        print("\n📸 Generating thumbnail for Telegram Web compatibility...")
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