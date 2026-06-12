'''
This script is for Tv shows and Movies.
It'll work for any psg and srt inbuilt or external
even if track has lable like track - English 
if no label it'll read it and tell 
it pgs then ocr reader will decipher if it's english

It needs another script 
check_english_in_PGS.py

'''

import subprocess
import re
import sys
import json
from tqdm import tqdm
from pathlib import Path
from check_english_in_PGS import is_pgs_english

# =================================================================
# USER CONFIGURATION
# =================================================================
INPUT_FOLDER = "./TBBT-S04"
OUTPUT_FOLDER = "./telegram-TBBT-S04"

USE_INBUILT_SUBS = True  # True = Extract from MKV, False = Use external .srt

# Common English stop words for language detection heuristic
ENGLISH_STOP_WORDS = {"the", "and", "you", "that", "was", "for", "on", "are", "with", "his", 
                      "they", "this", "have", "from", "one", "had", "word", "but", "not", 
                      "what", "all", "were", "we", "when", "your", "can", "said", "there", 
                      "use", "an", "each", "which", "she", "do", "how", "their", "if", "will", "up"}
# =================================================================

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

def detect_english_content(video_path, stream_idx):
    """
    Extracts the first 3 minutes of a text subtitle stream and checks for English words.
    Returns True if it looks like English, False otherwise.
    """
    cmd = [
        "ffmpeg", "-v", "error", 
        "-i", str(video_path),
        "-map", f"0:s:{stream_idx}",
        "-t", "180",          # Only extract the first 3 minutes to be fast
        "-c:s", "srt",        # Force conversion to SRT format text
        "-f", "srt", "-"      # Output to stdout
    ]
    
    try:
        result = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, encoding='utf-8', errors='ignore')
        text_output = result.stdout.lower()
        
        # Extract all words from the subtitle text
        words = re.findall(r'\b[a-z]{2,}\b', text_output)
        
        if not words:
            return False
            
        # Count how many of those words are common English words
        english_matches = sum(1 for w in words if w in ENGLISH_STOP_WORDS)
        
        # If more than 5% of the total words are common English stop words, it's almost certainly English
        ratio = english_matches / len(words)
        return ratio > 0.05

    except Exception as e:
        return False

def get_english_subtitle_info(video_path, preferred_idx=None):
    """Dynamically finds the stream index and codec type of the first VALID English track."""
    cmd = [
        "ffprobe", "-v", "error", "-select_streams", "s",
        "-show_entries", "stream=index,codec_name:stream_tags",
        "-of", "json", str(video_path),
    ]
    try:
        result = subprocess.check_output(cmd, text=True)
        data = json.loads(result)
        streams = data.get("streams", [])

        candidate_tracks = []
        text_based_codecs = ['subrip', 'ass', 'webvtt', 'mov_text']
        relative_idx = 0

        # Step 1: Identify tagged English tracks
        for stream in streams:
            tags = stream.get("tags", {})
            lang = tags.get("language", "").lower()
            title = tags.get("title", "").lower()
            codec = stream.get("codec_name", "subrip").lower()

            track_info = {
                "relative_idx": relative_idx,
                "codec_name": codec,
                "title": title,
                "tags": tags,
                "is_text": codec in text_based_codecs
            }
            
            # If explicitly tagged as English, return immediately
            if (lang in ["eng", "en"] or "english" in title) and "forced" not in title:
                for key, value in tags.items():
                    if "NUMBER_OF_BYTES" in key.upper() and str(value).isdigit() and int(value) < 1024:
                        continue 
                return relative_idx, codec

            candidate_tracks.append(track_info)
            relative_idx += 1

        # Step 2: FALLBACK - Content Inspection 
        print(f"No explicitly tagged English track found for {video_path.name}. Inspecting track content...")
        
        # SMART SORTING: If we have a successful track from the last episode, check it FIRST!
        if preferred_idx is not None:
            # Sorts the list so the preferred_idx is moved to index 0
            candidate_tracks.sort(key=lambda x: x["relative_idx"] != preferred_idx)

        for candidate in candidate_tracks:
            # Add a little note in the console if it's checking the prioritized track
            priority_note = "[PRIORITY CHECK] " if candidate['relative_idx'] == preferred_idx else ""
            print(f"  -> {priority_note}Analyzing Track {candidate['relative_idx']} ({candidate['codec_name']})...")
            
            # Fast Check: Text-based subtitles
            if candidate["is_text"]:
                if detect_english_content(video_path, candidate["relative_idx"]):
                    print(f"  -> Content Match! Track {candidate['relative_idx']} is English (Text).")
                    return candidate["relative_idx"], candidate["codec_name"]
                    
            # Heavy Check: Image-based subtitles via OCR
            elif candidate["codec_name"] in ['hdmv_pgs_subtitle', 'dvd_subtitle', 'pgs', 'dvdsub']:
                if is_pgs_english(video_path, candidate["relative_idx"]):
                    print(f"  -> OCR Match! Track {candidate['relative_idx']} is English (PGS).")
                    return candidate["relative_idx"], candidate["codec_name"]

        print("Warning: Content inspection failed. Defaulting to first subtitle track (0).")
        return 0, candidate_tracks[0]["codec_name"] if candidate_tracks else "subrip"

    except Exception as e:
        print(f"Error reading subtitle streams for {video_path.name}: {e}. Defaulting to 0.")
        return 0, "subrip"

def escape_ffmpeg_path(path_obj):
    if not path_obj:
        return ""
    path_str = path_obj.absolute().as_posix()
    escaped_str = path_str.replace(':', r'\:').replace(',', r'\,').replace("'", r"\'").replace('"', r'\"').replace('`', r'\`')
    return escaped_str

def burn_subtitles_nvenc(input_file, output_file, subtitle_inbuilt=False, subtitle_file="", preferred_track=None):
    print(f"\nAnalyzing {input_file.name}...")
    total_duration = get_video_duration(input_file)
    
    input_str_safe = escape_ffmpeg_path(input_file)
    sub_str_safe = escape_ffmpeg_path(subtitle_file) if subtitle_file else ""

    premium_style = "Fontname=Arial,Fontsize=22,PrimaryColour=&H00FFFFFF,OutlineColour=&H00000000,BorderStyle=1,Outline=2,Shadow=1,MarginV=25"
    scale_filter = "scale=trunc(iw/2)*2:trunc(ih/2)*2"

    ffmpeg_cmd = [
        'ffmpeg',
        '-i', str(input_file),
    ]

    used_track_index = None

    # DYNAMIC TRACK SELECTION
    if subtitle_inbuilt:
        track_index, codec_name = get_english_subtitle_info(input_file, preferred_idx=preferred_track)
        used_track_index = track_index
        
        if codec_name in ['hdmv_pgs_subtitle', 'dvd_subtitle', 'pgs', 'dvdsub']:
            print(f"Burning in INBUILT IMAGE subtitle track (Index: {track_index}, Codec: {codec_name})...")
            filter_complex = f"[0:v:0][0:s:{track_index}]overlay[bg];[bg]{scale_filter}[v_out]"
            ffmpeg_cmd.extend(['-filter_complex', filter_complex, '-map', '[v_out]', '-map', '0:a:0'])
        else:
            print(f"Burning in INBUILT TEXT subtitle track (Index: {track_index}, Codec: {codec_name})...")
            video_filter = f"subtitles='{input_str_safe}':si={track_index}:force_style='{premium_style}',{scale_filter}"
            ffmpeg_cmd.extend(['-map', '0:v:0', '-map', '0:a:0', '-vf', video_filter])
    else:
        if not subtitle_file:
            print("Error: Provide a subtitle_file when subtitle_inbuilt is False.")
            return preferred_track
        print(f"Burning in EXTERNAL subtitle file: {subtitle_file.name}...")
        video_filter = f"subtitles='{sub_str_safe}':force_style='{premium_style}',{scale_filter}"
        ffmpeg_cmd.extend(['-map', '0:v:0', '-map', '0:a:0', '-vf', video_filter])
    
    # ENCODING SETTINGS
    ffmpeg_cmd.extend([
        '-c:v', 'h264_nvenc',
        '-preset', 'p5',
        '-cq', '20',
        '-profile:v', 'high',
        '-level', '4.1',
        '-pix_fmt', 'yuv420p',
        '-c:a', 'aac',
        '-b:a', '128k',
        '-ac', '2',
        '-bf', '0',
        '-y',
        str(output_file)
    ])

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
        return used_track_index # Return the winning track to be used in the next loop
    else:
        print("\nAn error occurred during conversion! Here is what FFmpeg said at the end:\n")
        print("-" * 50)
        for log_line in ffmpeg_log[-20:]:
            print(log_line)
        print("-" * 50)
        return preferred_track # If it crashed, keep the old preferred track memory

# =================================================================
# Logic Execution
# =================================================================
if __name__ == "__main__":
    
    input_dir = Path(INPUT_FOLDER)
    output_dir = Path(OUTPUT_FOLDER)
    output_dir.mkdir(parents=True, exist_ok=True)

    if not input_dir.exists():
        print(f"Error: The input folder '{INPUT_FOLDER}' does not exist.")
        sys.exit(1)

    mkv_files = list(input_dir.glob("*.mkv"))
    if not mkv_files:
        print(f"No .mkv files found in '{INPUT_FOLDER}'.")
        sys.exit(0)

    # Initialize the memory variable before the loop starts
    last_successful_track = None 

    for video in mkv_files:
        subs = video.with_suffix(".srt")
        
        if not USE_INBUILT_SUBS and not subs.exists():
            print("========================================")
            print(f"Missing Subtitle: {subs.name}")
            print("\tFile doesn't exist. Skipping...")
            print("========================================\n")
            continue
            
        OUTPUT_FILE = output_dir / f"{video.stem}.mp4"
        
        # Pass the memory variable in, and catch the new winning track coming out!
        last_successful_track = burn_subtitles_nvenc(
            input_file=video,
            output_file=OUTPUT_FILE,
            subtitle_inbuilt=USE_INBUILT_SUBS,  
            subtitle_file=subs if not USE_INBUILT_SUBS else "",
            preferred_track=last_successful_track
        )
        
        print("=================================================================")
        print(f"\t\t{video.name} DONE")
        print("=================================================================\n")
