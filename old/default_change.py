#=============================================
#This script is for chaning default 
#like changing default from english to japaneses audio 
#and srt from track 1 to 2 
#==============================================


import subprocess
from pathlib import Path

def remux_mkv_default_japanese(input_file, output_file):
    print(f"Processing {input_file}...")
    
    ffmpeg_cmd = [
        'ffmpeg',
        '-i', input_file,
        '-map', '0:0',                    # Keep Video
        '-map', '0:1',                    # Keep English Audio (but we will remove its default status)
        '-map', '0:2',                    # Keep Japanese Audio
        '-map', '0:3',                    # Keep the good Dialogue Subtitle, drop the other one
        '-c', 'copy',                     # 100% exact copy of quality
        
        # Metadata / Default Flags:
        '-disposition:a:0', '0',          # Output Audio 1 (English): Remove default flag (set to 0)
        '-disposition:a:1', 'default',    # Output Audio 2 (Japanese): Set as default
        '-disposition:s:0', 'default',    # Output Subtitle 1 (Dialogue): Set as default
        
        '-y',                             # Overwrite output file if it exists
        output_file
    ]

    print("Copying streams and updating defaults (this will be fast)...")
    
    process = subprocess.run(
        ffmpeg_cmd,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True
    )
    
    if process.returncode == 0:
        print("\nSuccess! The MKV has been remuxed with Japanese as default.")
    else:
        print("\nAn error occurred! Here is the output:")
        print("-" * 50)
        print(process.stderr)
        print("-" * 50)

if __name__ == "__main__":
    
    for item in Path(".").iterdir():
        if item.is_dir() or item.suffix == ".py":
            continue
        print(item)

        INPUT_FILE = fr"./{item}"
        OUTPUT_FILE = fr"./default/{item}"
    
        remux_mkv_default_japanese(INPUT_FILE, OUTPUT_FILE)
