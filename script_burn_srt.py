import subprocess
import re
import sys
from tqdm import tqdm
from pathlib import Path

def get_video_duration(input_file):
    cmd = [
        'ffprobe', '-v', 'error', '-show_entries', 'format=duration',
        '-of', 'default=noprint_wrappers=1:nokey=1', str(input_file)
    ]
    try:
        result = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True)
        return float(result.stdout.strip())
    except Exception as e:
        print(f"Error getting duration: {e}")
        sys.exit(1)

def burn_subtitles_nvenc(input_file, output_file, subtitle_inbuilt=False, subtitle_track=1, subtitle_file=""):
    print(f"\nAnalyzing {input_file.name}...")
    total_duration = get_video_duration(input_file)
    
    # We do the math here so you can just type "1" for the first track
    track_index = subtitle_track - 1 
    
    # THE FIX: We replace backward slashes with forward slashes, AND we escape the colon 
    # in the Windows drive letter (e.g., changing C:/ to C\:/) so FFmpeg parses it correctly.
    input_str_safe = str(input_file.absolute()).replace('\\', '/').replace(':', r'\:')
    sub_str_safe = str(subtitle_file.absolute()).replace('\\', '/').replace(':', r'\:') if subtitle_file else ""

    if subtitle_inbuilt:
        print(f"Burning in INBUILT subtitle track {subtitle_track}...")
        video_filter = f"subtitles='{input_str_safe}':si={track_index}"
    else:
        if not subtitle_file:
            print("Error: Provide a subtitle_file when subtitle_inbuilt is False.")
            return
        print(f"Burning in EXTERNAL subtitle file: {subtitle_file.name}...")
        video_filter = f"subtitles='{sub_str_safe}'"
    
    ffmpeg_cmd = [
        'ffmpeg',
        '-i', str(input_file),
        '-map', '0:v:0', 
        '-map', '0:a',   
        '-vf', video_filter, 
        '-c:v', 'hevc_nvenc',
        '-pix_fmt', 'p010le',
        '-preset', 'p6',
        '-tune', 'hq',
        '-cq', '20',
        '-bf', '0',
        '-c:a', 'copy',
        '-y',
        str(output_file)
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
    ffmpeg_log = []

    with tqdm(total=total_duration, unit='s', desc="Encoding", bar_format="{l_bar}{bar}| {n_fmt}/{total_fmt}s [{elapsed}<{remaining}]") as pbar:
        for line in process.stdout:
            ffmpeg_log.append(line.strip())
            if len(ffmpeg_log) > 50:
                ffmpeg_log.pop(0)

            match = time_pattern.search(line)
            if match:
                hours, minutes, seconds = map(int, match.groups())
                elapsed_seconds = (hours * 3600) + (minutes * 60) + seconds
                pbar.update(elapsed_seconds - pbar.n)
                
    process.wait()
    
    if process.returncode == 0:
        print(f"Conversion complete for: {output_file.name}")
    else:
        print("\nAn error occurred during conversion! Here is what FFmpeg said at the end:\n")
        print("-" * 50)
        for log_line in ffmpeg_log[-20:]:
            print(log_line)
        print("-" * 50)

# =================================================================
# Logic Execution
# =================================================================
if __name__ == "__main__":
    
    output_dir = Path("./telegram")
    output_dir.mkdir(exist_ok=True)

    # ---------------------------------------------------------
    # USER CONFIGURATION: CHANGE THESE TWO VARIABLES
    # ---------------------------------------------------------
    USE_INBUILT_SUBS = True
    TRACK_NUMBER = 1 
    # ---------------------------------------------------------

    for item in Path("./").iterdir():
        if item.suffix != ".mkv":
            continue
            
        video = item
        subs = Path(f"{video.stem}.srt")
        
        # The logic now ONLY skips if you explicitly want external subs AND they are missing
        if not USE_INBUILT_SUBS and not subs.exists():
            print("========================================")
            print(f"Missing Subtitle: {subs.name}")
            print("\tFile doesn't exist. Skipping...")
            print("========================================\n")
            continue
            
        OUTPUT_FILE = output_dir / f"{video.stem}.mp4"
        
        burn_subtitles_nvenc(
            input_file=video,
            output_file=OUTPUT_FILE,
            subtitle_inbuilt=USE_INBUILT_SUBS,  
            subtitle_track=TRACK_NUMBER,
            subtitle_file=subs if not USE_INBUILT_SUBS else ""
        )
        
        print("=================================================================")
        print(f"\t\t{video.name} DONE")
        print("=================================================================\n")
