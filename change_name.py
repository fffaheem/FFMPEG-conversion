from pathlib import Path

count = 1
season = "Season 4 Episode"
folder = "./GAS4"
with open("episodes.txt", "w", encoding="utf-8") as f:
    for item in Path(folder).iterdir():
        if item.suffix != ".mkv":
            continue
        old_name = item.name
        new_name = old_name.replace("'", "")

        if old_name == new_name:
            continue

        new_item = item.with_name(new_name)
        item.rename(new_item)
        # d = item.stem.split("-")
        # print(d[1])
        print("==============================================================", file=f)
        print(f"{season} {count}", file=f)
        print("⬇⬇⬇⬇⬇⬇⬇⬇⬇⬇⬇⬇⬇⬇⬇⬇⬇⬇⬇⬇⬇⬇⬇⬇⬇⬇⬇⬇⬇⬇", file=f)
        print("==============================================================", file=f)
        print("\n\n\n", file=f)

        count += 1