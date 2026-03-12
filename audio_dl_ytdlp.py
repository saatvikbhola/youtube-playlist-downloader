# audio_dl_ytdlp.py
import os
import time
import logging
import threading
import concurrent.futures
import sys

# Force utf-8 encoding for standard output to avoid rich layout crash
if sys.platform == "win32":
    sys.stdout.reconfigure(encoding='utf-8')

from dotenv import load_dotenv
from googleapiclient.discovery import build
import yt_dlp

# Rich TUI
from rich.align import Align
from rich.console import Console
from rich.prompt import Prompt, Confirm, IntPrompt
from rich.panel import Panel
from rich.layout import Layout
from rich.live import Live
from rich.progress import Progress, SpinnerColumn, BarColumn, TextColumn
from rich.logging import RichHandler
from rich.traceback import install
from rich.text import Text
from rich.table import Table

# Load env
load_dotenv()

# --- Configurable ---
LOG_WINDOW = 60  # number of log lines visible in Logs panel
DOWNLOAD_DIR = os.path.join(os.getcwd(), "downloads")

# Create download dir if needed
if not os.path.exists(DOWNLOAD_DIR):
    os.makedirs(DOWNLOAD_DIR)

# --- Setup logging & console ---
install()
console = Console(force_terminal=True)

class LogCapture(logging.Handler):
    """Capture recent logs so we can display them in the UI."""
    def __init__(self):
        super().__init__()
        self.logs = []
        self.max_logs = 2000

    def emit(self, record):
        try:
            log_entry = self.format(record)
            self.logs.append(log_entry)
            if len(self.logs) > self.max_logs:
                # Trim older logs
                self.logs = self.logs[-self.max_logs:]
        except Exception:
            pass

    def get_last_lines(self, n):
        return self.logs[-n:]

log_capture = LogCapture()
log_capture.setFormatter(logging.Formatter("[%(asctime)s] %(levelname)-8s %(message)s", datefmt="%H:%M:%S"))

file_handler = logging.FileHandler("downloader.log", encoding="utf-8")
file_handler.setFormatter(logging.Formatter("[%(asctime)s] %(levelname)-8s %(message)s", datefmt="%Y-%m-%d %H:%M:%S"))

logging.basicConfig(
    level="INFO",
    handlers=[log_capture, file_handler]
)
log = logging.getLogger("rich")

# Reduce noisy libs
logging.getLogger("urllib3").setLevel(logging.CRITICAL)

# --- YouTube API helper ---
def get_video_links(api_key, playlist_id):
    """Fetch video links+titles from YouTube Data API (playlistItems)."""
    try:
        youtube = build("youtube", "v3", developerKey=api_key)
        video_links = []
        next_page_token = None

        while True:
            response = youtube.playlistItems().list(
                part="snippet", playlistId=playlist_id, maxResults=50, pageToken=next_page_token
            ).execute()

            for item in response.get("items", []):
                video_id = item["snippet"]["resourceId"]["videoId"]
                video_title = item["snippet"]["title"]
                safe_title = "".join([c for c in video_title if c.isalnum() or c in " -_"]).strip()
                video_links.append((f"https://www.youtube.com/watch?v={video_id}", safe_title))

            next_page_token = response.get("nextPageToken")
            if not next_page_token:
                break

        return video_links
    except Exception as e:
        log.error(f"Error fetching from API: {e}")
        return []

class YtDlpLogger:
    def __init__(self, title):
        self.title = title
    def debug(self, msg):
        pass
    def warning(self, msg):
        pass
    def error(self, msg):
        log.error(f"yt-dlp error on {self.title}: {msg}")

# --- Worker (per-thread) ---
def download_video_task(args):
    """Worker function for downloading a single video via yt-dlp."""
    (video_url, title), headless_mode = args # headless_mode kept for signature compatibility
    
    ydl_opts = {
        'format': 'bestaudio/best',
        'outtmpl': os.path.join(DOWNLOAD_DIR, f"{title}.%(ext)s"),
        'writethumbnail': True,  # Download the video thumbnail
        'keepvideo': False, # Prevent yt-dlp from keeping the original stream file after extraction
        'postprocessors': [
            {
                'key': 'FFmpegExtractAudio',
                'preferredcodec': 'flac',
                'preferredquality': '0', # 0 maps to best quality for flac/ffmpeg audio encoders depending on the version
            },
            {
                'key': 'FFmpegMetadata',  # Embed metadata (title, artist, etc.)
                'add_metadata': True,
            },
            {
                'key': 'EmbedThumbnail',  # Embed the thumbnail image into the audio file
                'already_have_thumbnail': False,
            }
        ],
        'quiet': True,
        'no_warnings': True,
        'logger': YtDlpLogger(title)
    }

    try:
        log.info(f"Processing: {title}")
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            ydl.download([video_url])
        log.info(f"✔ Completed: {title}")
    except Exception as e:
        log.error(f"Error on {title}: {e}")

# --- UI layout helpers ---
def create_layout():
    layout = Layout(name="root")
    layout.split(
        Layout(name="header", size=7),
        Layout(name="main", ratio=1),
        Layout(name="progress_section", size=5),
    )
    layout["main"].split_row(
        Layout(name="left"),
        Layout(name="logs", ratio=2)
    )
    layout["left"].split_column(
        Layout(name="inputs"),
        Layout(name="saved_to_folder")
    )
    return layout

# --- Main application ---
def main():
    layout = create_layout()

    header_text = (
        "[bold bright_blue] YOUTUBE TO MP3 [/bold bright_blue]\n[italic]Powered by yt-dlp and Python[/italic]"
    )

    header_panel = Panel(
        Align.center(header_text),
        border_style="red",
        padding=(1,1)
    )

    layout["header"].size=5
    layout["header"].update(header_panel)
    console.print(header_panel)
    console.print()

    api_key = os.getenv("API_KEY")
    playlist_id = Prompt.ask("Enter Playlist ID")
    
    # yt-dlp doesn't need headless browsers. We'll set a standard default worker count.
    workers = 2

    if not api_key or not playlist_id:
        console.print("[bold red]Missing Credentials! Make sure API_KEY is set in environment or .env[/bold red]")
        return

    video_data = get_video_links(api_key, playlist_id)
    if not video_data:
        return

    inputs_table = Table.grid(padding=(0, 2))
    inputs_table.add_column(style="cyan", justify="right")
    inputs_table.add_column(style="white")
    inputs_table.add_row("Playlist ID:", playlist_id)
    inputs_table.add_row("Total Videos:", str(len(video_data)))
    
    layout["inputs"].update(Panel(inputs_table, title="[bold]Configuration[/bold]", border_style="green"))

    folder_text = Text()
    folder_text.append(f"Starting download for {len(video_data)} videos...\n\n", style="bold yellow")
    folder_text.append("Output folder:\n", style="cyan")
    folder_text.append(DOWNLOAD_DIR, style="white")
    layout["saved_to_folder"].update(Panel(folder_text, title="[bold]Download Info[/bold]", border_style="blue"))

    progress = Progress(
        SpinnerColumn(),
        # Make the description BOLD and UPPERCASE
        TextColumn("[bold bright_white]{task.description}"), 
        BarColumn(bar_width=None),
        # Make percentage BOLD
        TextColumn("[bold yellow]{task.percentage:>3.0f}%"), 
        expand=True
    )
    
    # Uppercase title for visual weight
    overall_task = progress.add_task("TOTAL PROGRESS", total=len(video_data))
    layout["progress_section"].update(Panel(progress, title="[bold]Status[/bold]", border_style="magenta", padding=(1, 2)))
    
    # Increase the size of the bottom section slightly
    layout["progress_section"].size = 6

    # Start Live UI
    with Live(layout, console=console, refresh_per_second=4, screen=True):
        task_args = [((link, title), False) for link, title in video_data]

        # Use ThreadPoolExecutor for concurrency
        with concurrent.futures.ThreadPoolExecutor(max_workers=workers) as executor:
            futures = {executor.submit(download_video_task, arg) for arg in task_args}

            # Loop while futures remain
            while futures:
                done, not_done = concurrent.futures.wait(
                    futures,
                    timeout=0.1,
                    return_when=concurrent.futures.FIRST_COMPLETED
                )

                # Advance progress for completed tasks and remove them
                for f in list(done):
                    try:
                        f.result()
                    except Exception as e:
                        log.error(f"Worker exception: {e}")
                    try:
                        progress.advance(overall_task)
                    except Exception:
                        pass
                    futures.discard(f)

                # Update Logs panel (show last LOG_WINDOW lines)
                last_lines = log_capture.get_last_lines(LOG_WINDOW)
                logs_joined = "\n".join(last_lines) if last_lines else "[no logs yet]"
                layout["logs"].update(
                    Panel(logs_joined, title="[bold]Logs[/bold]", border_style="yellow", padding=(1, 2))
                )

    time.sleep(0.2)
    print("\n[bold green]All downloads complete![/bold green]")

if __name__ == "__main__":
    main()
