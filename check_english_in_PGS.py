import subprocess
import os
import re
import tempfile
import sys
try:
    from PIL import Image
    import pytesseract
except ImportError:
    print("Error: Missing required libraries. Run: pip install pytesseract Pillow")
    sys.exit(1)

# UPGRADED: TV-Conversational English Dictionary + Common Grammatical Words
ENGLISH_STOP_WORDS = {
    # Common grammar
    "the", "and", "you", "that", "was", "for", "are", "with", "his", "they", "this", "have", 
    "from", "one", "had", "not", "what", "all", "were", "when", "your", "can", "there", "use", 
    "each", "which", "she", "how", "their", "will", "it", "is", "in", "to", "of", "he", "as", 
    "at", "be", "or", "by", "on", "do", "we", "up", "out", "me", "my", "so", "now", "here", 
    "why", "who", "then", "about", "them", "because",
    # TV Conversation & Dialogue
    "yeah", "yes", "no", "okay", "hey", "oh", "well", "right", "know", "think", "just", 
    "like", "get", "did", "got", "come", "see", "good", "want", "let", "tell", "look",
    # Contractions (Apostrophes removed by our script below)
    "im", "dont", "its", "thats", "cant", "youre", "didnt", "ill", "weve", "theyre"
}

def is_pgs_english(video_path, stream_idx, frames_to_check=20):
    with tempfile.TemporaryDirectory() as temp_dir:
        
        filter_str = f"[0:v:0]drawbox=x=0:y=0:w=iw:h=ih:color=black:t=fill[bg];[bg][0:s:{stream_idx}]overlay,fps=1[final]"
        
        cmd = [
            "ffmpeg", "-v", "error", "-y",
            "-ss", "00:01:00",  # Skip the first 60 seconds
            "-i", str(video_path),
            "-filter_complex", filter_str,
            "-map", "[final]",
            "-frames:v", str(frames_to_check),
            os.path.join(temp_dir, "sub_frame_%03d.png")
        ]
        
        try:
            result = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
            
            png_files = sorted([f for f in os.listdir(temp_dir) if f.endswith(".png")])
            
            if not png_files:
                print(f"  [Extraction Failed]: No subtitle images could be extracted for track {stream_idx}.")
                return False
                
            extracted_text = ""
            
            for img_name in png_files:
                img_path = os.path.join(temp_dir, img_name)
                try:
                    text = pytesseract.image_to_string(Image.open(img_path))
                    extracted_text += text.lower() + " "
                except Exception as ocr_err:
                    print(f"  [OCR Error on {img_name}]: {ocr_err}")
                    continue
            
            # UPGRADE: Remove apostrophes so "don't" becomes "dont" and matches our dictionary
            extracted_text = extracted_text.replace("'", "").replace("’", "")
            
            # UPGRADE: Only check words of 2 or more letters. Kills OCR "dust" noise.
            words = re.findall(r'\b[a-z]{2,}\b', extracted_text)
            
            if not words:
                return False
                
            english_matches = sum(1 for w in words if w in ENGLISH_STOP_WORDS)
            
            if len(words) == 0:
                return False
                
            ratio = english_matches / len(words)
            
            # UPGRADE: Raised threshold to 10% because our dictionary is much stronger now.
            return ratio > 0.10

        except Exception as e:
            print(f"  [Unexpected Error in PGS OCR]: {e}")
            return False

if __name__ == "__main__":
    if len(sys.argv) < 3:
        print("Usage: python check_english_in_PGS.py <video.mkv> <stream_index>")
    else:
        video = sys.argv[1]
        idx = int(sys.argv[2])
        print(f"Checking stream {idx} in {video} for English PGS...")
        result = is_pgs_english(video, idx)
        print(f"Result: {'ENGLISH MATCH' if result else 'NOT ENGLISH (or failed)'}")
