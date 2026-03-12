import os
import shutil

selenium_dir = "selenium"
ytdlp_dir = "ytdlp"

os.makedirs(selenium_dir, exist_ok=True)
os.makedirs(ytdlp_dir, exist_ok=True)

selenium_files = [
    "audio_dl.py", "main_script.py", "test_y2mate.py", "tui1.py", 
    "tui.py", "app.py", "text.py", "streamlit_app.py", "geckodriver.exe"
]

ytdlp_files = [
    "audio_dl_ytdlp.py"
]

for f in selenium_files:
    if os.path.exists(f):
        shutil.move(f, os.path.join(selenium_dir, f))

for f in ytdlp_files:
    if os.path.exists(f):
        shutil.move(f, os.path.join(ytdlp_dir, f))

print("Moved files successfully")
