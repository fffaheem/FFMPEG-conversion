#=================================================================
#This is for Anime 
#I use high quality c20 10bit color to encode this
#burning in mkv srt since they are not txt but images
#===============================================================

import subprocess
import re
import sys
from tqdm import tqdm
from pathlib import Path

def get_video_duration(input_file):
    cmd = [
        'ffprobe', '-v', 'error', '-show_entries', 'format=duration',
        '-of', 'default=noprint_wrappers=1:nokey=1', input_file
    ]
    try:
        result = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True)
        return float(result.stdout.strip())
    except Exception as e:
        print(f"Error getting duration: {e}")
        sys.exit(1)

def convert_video(input_file, output_file):
    print(f"Analyzing {input_file}...")
    total_duration = get_video_duration(input_file)
    
    ffmpeg_cmd = [
        'ffmpeg',
        '-i', input_file,
        # '-filter_complex', '[0:0][0:3]overlay=x=(main_w-overlay_w)/2:y=(main_h-overlay_h)/2[v]',
        '-filter_complex', '[0:v][0:s:0]overlay=x=(main_w-overlay_w)/2[v]',
        '-map', '[v]',
        '-map', '0:2',
        '-c:v', 'hevc_nvenc',
        '-pix_fmt', 'p010le',
        '-preset', 'p6',
        '-tune', 'hq',
        '-cq', '20',
        '-bf', '0',
        '-c:a', 'copy',
        '-y',
        output_file
    ]

    print("Starting conversion...")
    
    process = subprocess.Popen(
        ffmpeg_cmd,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
        encoding='utf-8',
        errors='ignore'
    )

    time_pattern = re.compile(r"time=(\d{2}):(\d{2}):(\d{2})\.\d+")
    
    # Store the log so we can read it if it crashes
    ffmpeg_log = []

    with tqdm(total=total_duration, unit='s', desc="Encoding", bar_format="{l_bar}{bar}| {n_fmt}/{total_fmt}s [{elapsed}<{remaining}]") as pbar:
        for line in process.stdout:
            ffmpeg_log.append(line.strip()) # Save line to log
            # Keep log from eating all your RAM (store only last 50 lines)
            if len(ffmpeg_log) > 50:
                ffmpeg_log.pop(0)

            match = time_pattern.search(line)
            if match:
                hours, minutes, seconds = map(int, match.groups())
                elapsed_seconds = (hours * 3600) + (minutes * 60) + seconds
                pbar.update(elapsed_seconds - pbar.n)
                
    process.wait()
    
    if process.returncode == 0:
        print("\nConversion complete!")
    else:
        print("\nAn error occurred during conversion! Here is what FFmpeg said at the end:\n")
        print("-" * 50)
        # Print the last 20 lines of the log
        for log_line in ffmpeg_log[-20:]:
            print(log_line)
        print("-" * 50)

if __name__ == "__main__":

    Path("./telegram").mkdir(exist_ok=True)

    for item in Path("./").iterdir():
        if item.is_dir() or item.suffix == ".py" or item.suffix == ".txt":
            continue
        if item.suffix != ".mkv":
            continue
        # print(item)
        INPUT_FILE = fr"./{item.stem}.mkv"
        OUTPUT_FILE = fr"./telegram/{item.stem}.mp4"
        
        # print(OUTPUT_FILE)
        convert_video(INPUT_FILE, OUTPUT_FILE)
        print("=================================================================")
        print(f"\t\t{INPUT_FILE} DONE")
        print("=================================================================")
