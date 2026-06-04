#=======================================================================
#Script to change mkv to mp4 by choosing a size 
#subtitles can be togglable or burn in
#also, can be from inbuilt or outside file
#=======================================================================
import subprocess
from tqdm import tqdm
from pathlib import Path

# =========================
# CONFIG
# =========================
FOLDER = "./"
SEASON = "s01"
EPISODE = "e01"
VIDEO = f"{FOLDER}{EPISODE}.mkv"
for item in Path(".").iterdir():
    if item.suffix == ".mkv":
        VIDEO = f"{FOLDER}{item}"

OUTPUT = f"{FOLDER}{SEASON}{EPISODE}.mp4"

TARGET_SIZE_MB = 1900

SUBTITLE = f"{FOLDER}{EPISODE}.srt"
SUBTITLE_TOGGLABLE = False
SUBTITLE_INBUILT = True
SUBTITLE_TRACK   = 0  # Note: FFmpeg is 0-indexed. 0 = 1st track, 1 = 2nd track.

# =========================
# GET DURATION
# =========================
print(f"{SEASON}-{EPISODE}")
duration = float(
    subprocess.check_output([
        "ffprobe",
        "-v", "error",
        "-show_entries", "format=duration",
        "-of", "default=noprint_wrappers=1:nokey=1",
        VIDEO
    ]).decode().strip()
)

# =========================
# GET AUDIO BITRATE
# =========================
audio_bitrate = subprocess.check_output([
    "ffprobe",
    "-v", "error",
    "-select_streams", "a:0",
    "-show_entries", "stream=bit_rate",
    "-of", "default=noprint_wrappers=1:nokey=1",
    VIDEO
]).decode().strip()

audio_bitrate = int(audio_bitrate) // 1000 if audio_bitrate else 128

# =========================
# CALCULATE VIDEO BITRATE
# =========================
video_bitrate = int(
    ((TARGET_SIZE_MB * 8192) / duration)
    - audio_bitrate
)

print(f"Duration      : {duration:.0f} sec")
print(f"Audio bitrate : {audio_bitrate} kbps")
print(f"Video bitrate : {video_bitrate} kbps")
print()

# =========================
# BUILD COMMAND
# =========================

if SUBTITLE_TOGGLABLE:
    if SUBTITLE_INBUILT:
        # Togglable + Internal Track
        cmd = [
            "ffmpeg",
            "-i", VIDEO,
            
            "-map", "0:v:0",
            "-map", "0:a:0",
            "-map", f"0:s:{SUBTITLE_TRACK}", # Map specific internal sub stream
            
            "-c:v", "hevc_nvenc",
            "-preset", "p5",
            "-b:v", f"{video_bitrate}k",
            
            "-c:a", "copy",
            "-c:s", "mov_text",
            
            "-movflags", "+faststart",
            "-progress", "pipe:1",
            "-nostats",
            OUTPUT
        ]
    else:
        # Togglable + External File
        cmd = [
            "ffmpeg",
            "-i", VIDEO,
            "-i", SUBTITLE,
            
            "-map", "0:v:0",
            "-map", "0:a:0",
            "-map", "1:0", # Map first stream of the second input (the .srt)
            
            "-c:v", "hevc_nvenc",
            "-preset", "p5",
            "-b:v", f"{video_bitrate}k",
            
            "-c:a", "copy",
            "-c:s", "mov_text",
            
            "-movflags", "+faststart",
            "-progress", "pipe:1",
            "-nostats",
            OUTPUT
        ]

else:
    if SUBTITLE_INBUILT:
        # Burned-in + Internal Track
        cmd = [
            "ffmpeg",
            "-i", VIDEO,
            
            # Point subtitle filter at the video file itself and use stream index (si)
            "-vf", f"subtitles={VIDEO}:si={SUBTITLE_TRACK}",
            
            "-c:v", "hevc_nvenc",
            "-preset", "p5",
            "-b:v", f"{video_bitrate}k",
            
            "-c:a", "copy",
            "-movflags", "+faststart",
            "-progress", "pipe:1",
            "-nostats",
            OUTPUT
        ]
    else:
        # Burned-in + External File
        cmd = [
            "ffmpeg",
            "-i", VIDEO,
            
            "-vf", f"subtitles={SUBTITLE}",
            
            "-c:v", "hevc_nvenc",
            "-preset", "p5",
            "-b:v", f"{video_bitrate}k",
            
            "-c:a", "copy",
            "-movflags", "+faststart",
            "-progress", "pipe:1",
            "-nostats",
            OUTPUT
        ]

# =========================
# RUN + PROGRESS BAR
# =========================

process = subprocess.Popen(
    cmd,
    stdout=subprocess.PIPE,
    stderr=subprocess.DEVNULL,
    text=True
)

pbar = tqdm(
    total=duration,
    unit="sec",
    desc="Encoding"
)

for line in process.stdout:
    if line.startswith("out_time_ms="):
        current = int(line.split("=")[1]) / 1_000_000
        pbar.n = min(current, duration)
        pbar.refresh()

pbar.close()
process.wait()

print("\nDone!")
