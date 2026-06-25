# Burn anything just not size comparable right now so we have to keep that in mind in next iteration

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
INPUT_FOLDER = "./TBBT-S10"
OUTPUT_FOLDER = "./telegram-TBBT-S10"
count_start = 1
count_end = -1 #-1 means complete to the end

VIDEO_TYPE = "MKV"  # Set to "MKV" or "MP4"

# Set to True for Anime (10-bit HEVC, Audio Copy, Centered Subs)
# Set to False for TV/Movies (8-bit H264, AAC Stereo, Standard Subs)
ANIME = False  
# cq_anime = 14
cq_anime = 16
cq_other = 20

USE_INBUILT_SUBS = True  # True = Extract from MKV/MP4, False = Use external .srt or .ass

# --- MANUAL SUBTITLE CONTROLS ---
# Note: FFmpeg draws these on a tiny invisible canvas before scaling up to your video.
# 10 to 14 is usually standard. 22 will be extremely large.
SUBTITLE_FONT_SIZE = 22
# SUBTITLE_FONT_SIZE = 52

# Controls how high off the bottom of the screen the text sits
SUBTITLE_MARGIN_V = 15  
# SUBTITLE_MARGIN_V = 25

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

def get_default_audio_relative_index(video_path):
    """Finds which audio track is flagged as 'default' in the metadata."""
    cmd = [
        "ffprobe", "-v", "error", "-select_streams", "a",
        "-show_entries", "stream_disposition=default", 
        "-of", "json", str(video_path)
    ]
    try:
        result = subprocess.check_output(cmd, text=True)
        data = json.loads(result)
        streams = data.get("streams", [])
        for idx, stream in enumerate(streams):
            if stream.get("disposition", {}).get("default") == 1:
                return idx
        return 0 # Fallback to first audio track if none are explicitly marked default
    except:
        return 0

def detect_english_content(video_path, stream_idx):
    """Extracts the first 3 minutes of a text subtitle stream and checks for English words."""
    cmd = [
        "ffmpeg", "-v", "error", 
        "-i", str(video_path),
        "-map", f"0:s:{stream_idx}",
        "-t", "180",          
        "-c:s", "srt",        
        "-f", "srt", "-"      
    ]
    try:
        result = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, encoding='utf-8', errors='ignore')
        text_output = result.stdout.lower()
        words = re.findall(r'\b[a-z]{2,}\b', text_output)
        
        if not words: return False
            
        english_matches = sum(1 for w in words if w in ENGLISH_STOP_WORDS)
        ratio = english_matches / len(words)
        return ratio > 0.05
    except Exception as e:
        return False

def get_english_subtitle_info(video_path, preferred_idx=None):
    """Dynamically finds the stream index and codec type of the first VALID English track."""
    cmd = [
        "ffprobe", "-v", "error", "-select_streams", "s",
        "-show_entries", "stream=index,codec_name:stream_tags:stream_disposition",
        "-of", "json", str(video_path),
    ]
    try:
        result = subprocess.check_output(cmd, text=True)
        data = json.loads(result)
        streams = data.get("streams", [])

        candidate_tracks = []
        text_based_codecs = ['subrip', 'ass', 'webvtt', 'mov_text']
        relative_idx = 0

        for stream in streams:
            tags = stream.get("tags", {})
            lang = tags.get("language", "").lower()
            title = tags.get("title", "").lower()
            codec = stream.get("codec_name", "subrip").lower()
            is_default = stream.get("disposition", {}).get("default", 0) == 1

            track_info = {
                "relative_idx": relative_idx,
                "codec_name": codec,
                "title": title,
                "tags": tags,
                "is_text": codec in text_based_codecs,
                "is_default": is_default
            }
            
            # If explicitly tagged as English, return immediately
            if (lang in ["eng", "en"] or "english" in title) and "forced" not in title:
                for key, value in tags.items():
                    if "NUMBER_OF_BYTES" in key.upper() and str(value).isdigit() and int(value) < 1024:
                        continue 
                return relative_idx, codec

            candidate_tracks.append(track_info)
            relative_idx += 1

        print(f"No explicitly tagged English track found for {video_path.name}. Inspecting track content...")
        
        candidate_tracks.sort(key=lambda x: (
            x["relative_idx"] != preferred_idx, 
            not x["is_default"]
        ))

        for candidate in candidate_tracks:
            priority_note = "[MEMORY CHECK] " if candidate['relative_idx'] == preferred_idx else ("[DEFAULT TRACK] " if candidate['is_default'] else "")
            print(f"  -> {priority_note}Analyzing Track {candidate['relative_idx']} ({candidate['codec_name']})...")
            
            # Text check
            if candidate["is_text"]:
                if detect_english_content(video_path, candidate["relative_idx"]):
                    print(f"  -> Content Match! Track {candidate['relative_idx']} is English (Text).")
                    return candidate["relative_idx"], candidate["codec_name"]
                    
            # PGS/Image check via OCR
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
    if not path_obj: return ""
    return path_obj.absolute().as_posix().replace(':', r'\:').replace(',', r'\,').replace("'", r"\'").replace('"', r'\"').replace('`', r'\`')

def burn_subtitles_nvenc(input_file, output_file, subtitle_inbuilt=False, subtitle_file="", preferred_track=None):
    print(f"\nAnalyzing {input_file.name}...")
    total_duration = get_video_duration(input_file)
    
    audio_idx = get_default_audio_relative_index(input_file)
    print(f"Detected Default Audio Track: {audio_idx}")
    
    input_str_safe = escape_ffmpeg_path(input_file)
    sub_str_safe = escape_ffmpeg_path(subtitle_file) if subtitle_file else ""

    # Inject the manual variables from the top of the script
    premium_style = f"Fontname=Arial,Fontsize={SUBTITLE_FONT_SIZE},PrimaryColour=&H00FFFFFF,OutlineColour=&H00000000,BorderStyle=1,Outline=2,Shadow=1,MarginV={SUBTITLE_MARGIN_V}"
    scale_filter = "scale=trunc(iw/2)*2:trunc(ih/2)*2"

    ffmpeg_cmd = ['ffmpeg', '-i', str(input_file)]
    used_track_index = None

    # --- SUBTITLE MAPPING ---
    if subtitle_inbuilt:
        track_index, codec_name = get_english_subtitle_info(input_file, preferred_idx=preferred_track)
        used_track_index = track_index
        
        if codec_name in ['hdmv_pgs_subtitle', 'dvd_subtitle', 'pgs', 'dvdsub']:
            print(f"Burning in INBUILT IMAGE subtitle track (Index: {track_index}, Codec: {codec_name})...")
            if ANIME:
                filter_complex = f"[0:v:0][0:s:{track_index}]overlay=x=(main_w-overlay_w)/2[v_out]"
            else:
                filter_complex = f"[0:v:0][0:s:{track_index}]overlay=0:0[bg];[bg]{scale_filter}[v_out]"
                
            ffmpeg_cmd.extend(['-filter_complex', filter_complex, '-map', '[v_out]'])
        else:
            print(f"Burning in INBUILT TEXT subtitle track (Index: {track_index}, Codec: {codec_name})...")
            video_filter = f"subtitles='{input_str_safe}':si={track_index}:force_style='{premium_style}',{scale_filter}"
            ffmpeg_cmd.extend(['-map', '0:v:0', '-vf', video_filter])
    else:
        if not subtitle_file: return preferred_track
        print(f"Burning in EXTERNAL subtitle file: {subtitle_file.name}...")
        video_filter = f"subtitles='{sub_str_safe}':force_style='{premium_style}',{scale_filter}"
        ffmpeg_cmd.extend(['-map', '0:v:0', '-vf', video_filter])
    
    # --- AUDIO MAPPING ---
    ffmpeg_cmd.extend(['-map', f'0:a:{audio_idx}'])
    if ANIME:
        ffmpeg_cmd.extend(['-c:a', 'copy'])
    else:
        ffmpeg_cmd.extend(['-c:a', 'aac', '-b:a', '128k', '-ac', '2'])

    # --- VIDEO ENCODING SETTINGS ---
    if ANIME:
        ffmpeg_cmd.extend(['-c:v', 'hevc_nvenc', '-pix_fmt', 'p010le', '-preset', 'p6', '-tune', 'hq', '-cq', f'{cq_anime}', '-bf', '0'])
    else:
        ffmpeg_cmd.extend(['-c:v', 'h264_nvenc', '-preset', 'p5', '-cq', f'{cq_other}', '-profile:v', 'high', '-level', '4.1', '-pix_fmt', 'yuv420p', '-bf', '0'])
        
    ffmpeg_cmd.extend(['-y', str(output_file)])

    print("Starting conversion...")
    
    process = subprocess.Popen(
        ffmpeg_cmd, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True, encoding='utf-8', errors='ignore'
    )

    time_pattern = re.compile(r"time=(\d{2}):(\d{2}):(\d{2})\.\d+")
    ffmpeg_log = []

    with tqdm(total=total_duration, unit='s', desc="Encoding", bar_format="{l_bar}{bar}| {n_fmt}/{total_fmt}s [{elapsed}<{remaining}]") as pbar:
        for line in process.stdout:
            ffmpeg_log.append(line.strip())
            if len(ffmpeg_log) > 50: ffmpeg_log.pop(0)

            match = time_pattern.search(line)
            if match:
                hours, minutes, seconds = map(int, match.groups())
                elapsed_seconds = (hours * 3600) + (minutes * 60) + seconds
                pbar.update(elapsed_seconds - pbar.n)
                
    process.wait()
    
    if process.returncode == 0:
        print(f"Conversion complete for: {output_file.name}")
        return used_track_index
    else:
        print("\nAn error occurred during conversion! Here is what FFmpeg said at the end:\n")
        print("-" * 50)
        for log_line in ffmpeg_log[-20:]: print(log_line)
        print("-" * 50)
        return preferred_track

# =================================================================
# Logic Execution
# =================================================================
if __name__ == "__main__":
    count = 1
    input_dir = Path(INPUT_FOLDER)
    output_dir = Path(OUTPUT_FOLDER)
    output_dir.mkdir(parents=True, exist_ok=True)

    if not input_dir.exists():
        print(f"Error: The input folder '{INPUT_FOLDER}' does not exist.")
        sys.exit(1)

    file_extension = f"*.{VIDEO_TYPE.lower()}"
    video_files = list(input_dir.glob(file_extension))
    
    if not video_files:
        print(f"No {file_extension} files found in '{INPUT_FOLDER}'.")
        sys.exit(0)

    last_successful_track = None 

    for video in video_files:
        if count < count_start:
            count += 1
            continue
            
        if count_end != -1 and count > count_end:
            count += 1
            break
        
        subs = None
        # EXTERNAL SUBTITLE DETECTION (Handles both .srt and .ass)
        if not USE_INBUILT_SUBS:
            srt_path = video.with_suffix(".srt")
            ass_path = video.with_suffix(".ass")
            
            if srt_path.exists():
                subs = srt_path
            elif ass_path.exists():
                subs = ass_path
            else:
                print("========================================")
                print(f"Missing Subtitle for: {video.name}")
                print("\tNo .srt or .ass file found. Skipping...")
                print("========================================\n")
                continue
            
        OUTPUT_FILE = output_dir / f"{video.stem}.mp4"
        
        last_successful_track = burn_subtitles_nvenc(
            input_file=video,
            output_file=OUTPUT_FILE,
            subtitle_inbuilt=USE_INBUILT_SUBS,  
            subtitle_file=subs,
            preferred_track=last_successful_track
        )
        
        print("=================================================================")
        print(f"\t{video.name} DONE")
        print("=================================================================\n")
        count += 1