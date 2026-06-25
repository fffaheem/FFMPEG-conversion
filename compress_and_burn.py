import json
import os
import re
import subprocess
import sys
import tempfile
from pathlib import Path

from tqdm import tqdm

try:
    import pytesseract
    from PIL import Image

    # Point pytesseract to the default Windows installation path
    pytesseract.pytesseract.tesseract_cmd = (
        r"C:\Program Files\Tesseract-OCR\tesseract.exe"
    )
except ImportError:
    print("Error: Missing required libraries. Run: pip install pytesseract Pillow")
    sys.exit(1)

# =========================================================================
# GLOBAL BATCH CONFIGURATION
# =========================================================================
TARGET_SIZE_MB = 1900  # Target file size in MB
INPUT_FOLDER = "./GAS5"  # Folder containing your MKVs
OUTPUT_FOLDER = "./telegram"
AUDIO_BITRATE_KBPS = 128  # Audio will be converted to this bitrate

ENGLISH_STOP_WORDS = {
    "the",
    "and",
    "you",
    "that",
    "was",
    "for",
    "are",
    "with",
    "his",
    "they",
    "this",
    "have",
    "from",
    "one",
    "had",
    "not",
    "what",
    "all",
    "were",
    "when",
    "your",
    "can",
    "there",
    "use",
    "each",
    "which",
    "she",
    "how",
    "their",
    "will",
    "it",
    "is",
    "in",
    "to",
    "of",
    "he",
    "as",
    "at",
    "be",
    "or",
    "by",
    "on",
    "do",
    "we",
    "up",
    "out",
    "me",
    "my",
    "so",
    "now",
    "here",
    "why",
    "who",
    "then",
    "about",
    "them",
    "because",
    "yeah",
    "yes",
    "no",
    "okay",
    "hey",
    "oh",
    "well",
    "right",
    "know",
    "think",
    "just",
    "like",
    "get",
    "did",
    "got",
    "come",
    "see",
    "good",
    "want",
    "let",
    "tell",
    "look",
    "im",
    "dont",
    "its",
    "thats",
    "cant",
    "youre",
    "didnt",
    "ill",
    "weve",
    "theyre",
}


# =========================================================================
# HELPER FUNCTIONS
# =========================================================================
def escape_ffmpeg_path(path_obj):
    return (
        path_obj.absolute()
        .as_posix()
        .replace(":", r"\:")
        .replace(",", r"\,")
        .replace("'", r"\'")
        .replace('"', r"\"")
    )


def get_video_duration(input_file):
    cmd = [
        "ffprobe",
        "-v",
        "error",
        "-show_entries",
        "format=duration",
        "-of",
        "default=noprint_wrappers=1:nokey=1",
        str(input_file),
    ]
    try:
        return float(subprocess.check_output(cmd, text=True).strip())
    except Exception:
        return 0.0


def get_default_audio_relative_index(video_path):
    cmd = [
        "ffprobe",
        "-v",
        "error",
        "-select_streams",
        "a",
        "-show_entries",
        "stream_disposition=default",
        "-of",
        "json",
        str(video_path),
    ]
    try:
        data = json.loads(subprocess.check_output(cmd, text=True))
        for idx, stream in enumerate(data.get("streams", [])):
            if stream.get("disposition", {}).get("default") == 1:
                return idx
        return 0
    except:
        return 0


# =========================================================================
# SUBTITLE DETECTION LOGIC
# =========================================================================
def detect_english_content_text(video_path, stream_idx):
    """Checks the first 3 minutes of a TEXT track for English."""
    cmd = [
        "ffmpeg",
        "-v",
        "error",
        "-i",
        str(video_path),
        "-map",
        f"0:s:{stream_idx}",
        "-t",
        "180",
        "-c:s",
        "srt",
        "-f",
        "srt",
        "-",
    ]
    try:
        text_output = subprocess.run(
            cmd,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            encoding="utf-8",
            errors="ignore",
        ).stdout.lower()
        words = re.findall(r"\b[a-z]{2,}\b", text_output)
        if not words:
            return False
        english_matches = sum(1 for w in words if w in ENGLISH_STOP_WORDS)
        return (english_matches / len(words)) > 0.05
    except:
        return False


def is_pgs_english(video_path, stream_idx, frames_to_check=20):
    """Extracts images from PGS/DVDSub and uses OCR to check for English."""
    with tempfile.TemporaryDirectory() as temp_dir:
        filter_str = f"[0:v:0]drawbox=x=0:y=0:w=iw:h=ih:color=black:t=fill[bg];[bg][0:s:{stream_idx}]overlay,fps=1[final]"
        cmd = [
            "ffmpeg",
            "-v",
            "error",
            "-y",
            "-ss",
            "00:01:00",
            "-i",
            str(video_path),
            "-filter_complex",
            filter_str,
            "-map",
            "[final]",
            "-frames:v",
            str(frames_to_check),
            os.path.join(temp_dir, "sub_frame_%03d.png"),
        ]
        try:
            subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
            png_files = sorted([f for f in os.listdir(temp_dir) if f.endswith(".png")])
            if not png_files:
                return False

            extracted_text = ""
            for img_name in png_files:
                img_path = os.path.join(temp_dir, img_name)
                try:
                    extracted_text += (
                        pytesseract.image_to_string(Image.open(img_path)).lower() + " "
                    )
                except:
                    pass

            extracted_text = extracted_text.replace("'", "").replace("’", "")
            words = re.findall(r"\b[a-z]{2,}\b", extracted_text)
            if not words:
                return False

            english_matches = sum(1 for w in words if w in ENGLISH_STOP_WORDS)
            return (english_matches / len(words)) > 0.10
        except:
            return False


def get_english_subtitle_info(video_path):
    """Finds the correct English track and identifies its format."""
    cmd = [
        "ffprobe",
        "-v",
        "error",
        "-select_streams",
        "s",
        "-show_entries",
        "stream=index,codec_name:stream_tags:stream_disposition",
        "-of",
        "json",
        str(video_path),
    ]
    try:
        data = json.loads(subprocess.check_output(cmd, text=True))
        streams = data.get("streams", [])
        text_based_codecs = ["subrip", "ass", "webvtt", "mov_text"]
        candidate_tracks = []

        for idx, stream in enumerate(streams):
            tags = stream.get("tags", {})
            title = tags.get("title", "").lower()
            lang = tags.get("language", "").lower()
            codec = stream.get("codec_name", "subrip").lower()

            # Fast-track explicit English tags that aren't forced
            if (lang in ["eng", "en"] or "english" in title) and "forced" not in title:
                # Ignore empty tracks
                is_empty = False
                for k, v in tags.items():
                    if (
                        "NUMBER_OF_BYTES" in k.upper()
                        and str(v).isdigit()
                        and int(v) < 1024
                    ):
                        is_empty = True
                if not is_empty:
                    return idx, codec

            candidate_tracks.append(
                {"idx": idx, "codec": codec, "is_text": codec in text_based_codecs}
            )

        print("  -> No explicit English tag found. Scanning content...")
        for candidate in candidate_tracks:
            print(f"  -> Testing Track {candidate['idx']} ({candidate['codec']})...")
            if candidate["is_text"]:
                if detect_english_content_text(video_path, candidate["idx"]):
                    return candidate["idx"], candidate["codec"]
            elif candidate["codec"] in [
                "hdmv_pgs_subtitle",
                "dvd_subtitle",
                "pgs",
                "dvdsub",
            ]:
                if is_pgs_english(video_path, candidate["idx"]):
                    return candidate["idx"], candidate["codec"]

        print("  -> Could not verify English. Defaulting to first track (0).")
        return 0, candidate_tracks[0]["codec"] if candidate_tracks else "subrip"
    except:
        return 0, "subrip"


# =========================================================================
# CORE PROCESSING
# =========================================================================
def process_video(video_path, output_path):
    print(f"\nProcessing: {video_path.name}")
    duration = get_video_duration(video_path)

    if duration == 0:
        print("Skipping: Could not read duration.")
        return

    # Exact max bitrate calculation (Size in KB divided by duration, minus Audio Bitrate)
    video_bitrate = int(((TARGET_SIZE_MB * 8192) / duration) - AUDIO_BITRATE_KBPS)

    if video_bitrate <= 0:
        print(
            f"Skipping: Target size {TARGET_SIZE_MB}MB is too small for this duration."
        )
        return

    audio_idx = get_default_audio_relative_index(video_path)
    sub_idx, sub_codec = get_english_subtitle_info(video_path)

    print(f"  -> Duration      : {duration:.2f} sec")
    print(f"  -> Video Bitrate : {video_bitrate} kbps")
    print(f"  -> Audio Track   : {audio_idx}")
    print(f"  -> Sub Track     : {sub_idx} ({sub_codec})")

    safe_path = escape_ffmpeg_path(video_path)
    scale_filter = "scale=trunc(iw/2)*2:trunc(ih/2)*2"

    ffmpeg_cmd = ["ffmpeg", "-i", str(video_path)]
    # -hwaccel auto tells FFmpeg to use your GPU to unpack the video before filtering
    # ffmpeg_cmd = ["ffmpeg", "-hwaccel", "auto", "-i", str(video_path)]

    # Dynamic Filter Graph Creation
    if sub_codec in ["hdmv_pgs_subtitle", "dvd_subtitle", "pgs", "dvdsub"]:
        print("  -> Using Image OVERLAY mode for subtitles.")
        filter_complex = (
            f"[0:v:0][0:s:{sub_idx}]overlay=0:0[bg];[bg]{scale_filter}[v_out]"
        )
        ffmpeg_cmd.extend(["-filter_complex", filter_complex, "-map", "[v_out]"])
    else:
        print("  -> Using Text BURN mode for subtitles.")
        video_filter = f"subtitles='{safe_path}':si={sub_idx},{scale_filter}"
        ffmpeg_cmd.extend(["-map", "0:v:0", "-vf", video_filter])

    ffmpeg_cmd.extend(
        [
            "-map",
            f"0:a:{audio_idx}",
            "-c:v",
            "h264_nvenc",
            "-preset",
            "p5",
            "-b:v",
            f"{video_bitrate}k",
            "-maxrate",
            f"{int(video_bitrate * 1.1)}k",  # Prevent spikes from exceeding size
            "-bufsize",
            f"{video_bitrate * 2}k",
            "-profile:v",
            "high",
            "-level",
            "4.1",
            "-pix_fmt",
            "yuv420p",
            "-c:a",
            "aac",
            "-b:a",
            f"{AUDIO_BITRATE_KBPS}k",
            "-ac",
            "2",
            "-bf",
            "0",
            "-movflags",
            "+faststart",
            "-y",
            str(output_path),
        ]
    )

    process = subprocess.Popen(
        ffmpeg_cmd,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
        encoding="utf-8",
        errors="ignore",
    )

    time_pattern = re.compile(r"time=(\d{2}):(\d{2}):(\d{2})\.\d+")
    ffmpeg_log = []

    with tqdm(
        total=duration,
        unit="sec",
        desc="Encoding",
        bar_format="{l_bar}{bar}| {n_fmt}/{total_fmt}s [{elapsed}<{remaining}]",
    ) as pbar:
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
        print(f"\nSuccessfully created: {output_path.name}")
    else:
        print("\n[ERROR] FFmpeg crash detected. Final logs:")
        print("-" * 50)
        for log_line in ffmpeg_log[-20:]:
            print(log_line)
        print("-" * 50)


# =========================================================================
# ENTRY POINT
# =========================================================================
if __name__ == "__main__":
    input_dir = Path(INPUT_FOLDER)
    output_dir = Path(OUTPUT_FOLDER)
    output_dir.mkdir(parents=True, exist_ok=True)

    mkv_files = list(input_dir.glob("*.mkv")) + list(input_dir.glob("*.mp4"))

    if not mkv_files:
        print(f"No video files detected in {INPUT_FOLDER}.")
        sys.exit(0)

    print(f"Found {len(mkv_files)} video files to process.")
    print("=================================================================")

    for item in mkv_files:
        if item.parent == output_dir:
            continue
        destination_file = output_dir / f"{item.stem}.mp4"
        process_video(item, destination_file)

    print("=================================================================")
    print("All batch video operations completed!")
