import openpyxl
import subprocess
import os
from pathlib import Path

VIDEO_DIR = Path("data/videos/eval")
OUTPUT_DIR = Path("data/audio/eval")

wb = openpyxl.load_workbook(VIDEO_DIR / "ground_truth.xlsx")
ws = wb.active

os.makedirs(OUTPUT_DIR, exist_ok=True)

for row in ws.iter_rows(min_row=2, values_only=True):
    scene, modality, cls, _, _, start_time, end_time, desc = row
    if modality != "audio":
        continue

    scene = int(scene)
    video_path = VIDEO_DIR / f"scene{scene}.mp4"
    if not video_path.exists():
        print(f"WARNING: {video_path} not found, skipping")
        continue

    safe_cls = cls.replace(" ", "_")
    safe_desc = desc[:40].replace(" ", "_").replace("/", "_") if desc else "no_desc"
    out_name = f"scene{scene}_{safe_cls}_{start_time:.3f}-{end_time:.3f}.wav"
    out_path = OUTPUT_DIR / out_name

    cmd = [
        "ffmpeg", "-y",
        "-i", str(video_path),
        "-ss", str(start_time),
        "-to", str(end_time),
        "-vn",
        "-acodec", "pcm_s16le",
        "-ar", "16000",
        "-ac", "1",
        str(out_path),
    ]
    subprocess.run(cmd, check=True, capture_output=True)
    print(f"Extracted: {out_name} ({start_time}-{end_time}s)")

print("\nDone!")
