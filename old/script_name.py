from pathlib import Path

count = 1
season = "S03"
with open("episodes.txt", "w", encoding="utf-8") as f:
    for item in Path(".").iterdir():
        if item.is_dir() or item.suffix == ".py"  or item.suffix == ".txt" :
            continue
        if item.suffix != ".mkv":
            continue
            
        d = item.stem.split("-")
        print("==============================================================",file=f)
        print(f"{season}E{count:02d} - Episode {d[1].lstrip()} ({"-".join(d[2::]).lstrip()})",file=f)
        print("⬇⬇⬇⬇⬇⬇⬇⬇⬇⬇⬇⬇⬇⬇⬇⬇⬇⬇⬇⬇⬇⬇⬇⬇⬇⬇⬇⬇⬇⬇",file=f)
        print("==============================================================",file=f)
        print("\n\n\n", file=f)

        count += 1
