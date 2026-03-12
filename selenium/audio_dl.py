# audio_dl.py
import os
import time
import logging
import threading
import concurrent.futures
import atexit
import tempfile
import shutil
import struct
import sys

# Force utf-8 encoding for standard output to avoid rich layout crash
if sys.platform == "win32":
    sys.stdout.reconfigure(encoding='utf-8')

from dotenv import load_dotenv
from googleapiclient.discovery import build

# Selenium / WebDriver Manager (stable for multithreading)
from selenium import webdriver
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.common.by import By
from selenium.webdriver.common.keys import Keys
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import TimeoutException, WebDriverException

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
BASE_URL = "https://v1.y2mate.nu"
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

logging.basicConfig(
    level="INFO",
    format="%(message)s",
    handlers=[ log_capture]
)
log = logging.getLogger("rich")

# Reduce noisy libs
logging.getLogger("urllib3").setLevel(logging.CRITICAL)
logging.getLogger("selenium").setLevel(logging.CRITICAL)
logging.getLogger("WDM").setLevel(logging.ERROR)

# --- Driver tracking for cleanup ---
active_drivers = []  # list of tuples (driver, temp_profile_dir, service)
drivers_lock = threading.Lock()

def cleanup_all_drivers():
    """Cleanup any active drivers (called at exit)."""
    with drivers_lock:
        for driver, temp_profile, service in list(active_drivers):
            # Force kill service process first to avoid .quit() hanging
            process_killed = False
            try:
                if service and hasattr(service, "process") and service.process:
                    service.process.kill()
                    process_killed = True
            except Exception:
                pass
                
            if not process_killed:
                try:
                    if driver:
                        driver.quit()
                except Exception:
                    pass

            try:
                if temp_profile and os.path.exists(temp_profile):
                    shutil.rmtree(temp_profile, ignore_errors=True)
            except Exception:
                pass
        active_drivers.clear()

    # Aggressively clear any lingering chromedriver processes
    try:
        if sys.platform == "win32":
            os.system("taskkill /f /im chromedriver.exe >nul 2>&1")
        else:
            os.system("pkill -f chromedriver >/dev/null 2>&1")
    except Exception:
        pass

atexit.register(cleanup_all_drivers)

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

# --- Download utilities ---
def _wait_for_download_completion(expected_filename_substr, timeout=180, poll_interval=1):
    """
    Wait for any .crdownload/.part files to disappear in DOWNLOAD_DIR and for a file that
    contains expected_filename_substr to appear. Conservative but robust.
    """
    deadline = time.time() + timeout
    while time.time() < deadline:
        try:
            files = os.listdir(DOWNLOAD_DIR)
        except Exception:
            files = []

        partials = [f for f in files if f.endswith('.crdownload') or f.endswith('.part')]
        if partials:
            time.sleep(poll_interval)
            continue

        # If no partials, check for an output file that matches the hint.
        if expected_filename_substr:
            matches = [f for f in files if expected_filename_substr.lower() in f.lower()]
            if matches:
                return True
            # If no matches, still wait a bit to allow file rename
            time.sleep(poll_interval)
            continue
        else:
            # No hint provided, we can treat lack of partials as finished.
            return True

    return False

def safe_driver_quit_tuple(driver_tuple):
    """Given (driver, temp_profile, service) ensure tidy shutdown and profile cleanup."""
    driver, temp_profile, service = driver_tuple
    
    #force fill (becuase of hanging)
    process_killed=False
    try:
        if service and hasattr(service,"process") and service.process:
            service.process.kill()
            process_killed = True
    except Exception:
        pass

    #quit driver as process dead
    if not process_killed:
        try:
            if driver:
                driver.quit()
        except Exception:
            pass

    # temporary folder clean
    try:
        if temp_profile and os.path.exists(temp_profile):
            time.sleep(1)
            shutil.rmtree(temp_profile, ignore_errors=True)
    except Exception:
        pass

# --- Worker (per-thread) ---
def download_video_task(args):
    """Worker function for downloading a single video via the conversion site."""
    (video_url, title), headless_mode = args
    driver = None
    temp_profile = None
    service = None
    try:
        # Unique profile dir for this browser instance to avoid collisions
        temp_profile = tempfile.mkdtemp(prefix="ytprof_")

        options = webdriver.ChromeOptions()
        prefs = {
            "download.default_directory": DOWNLOAD_DIR,
            "download.prompt_for_download": False,
            "download.directory_upgrade": True,
            "safebrowsing.enabled": True,
        }
        options.add_experimental_option("prefs", prefs)
        options.add_argument(f"--user-data-dir={temp_profile}")
        options.add_argument("--no-first-run")
        options.add_argument("--no-default-browser-check")
        options.add_argument("--disable-gpu")
        options.add_argument("--disable-dev-shm-usage")
        options.add_argument("--disable-extensions")
        options.add_argument("--log-level=3")
        # Headless mode (modern Chrome)
        if headless_mode:
            try:
                options.add_argument("--headless=new")
            except Exception:
                options.add_argument("--headless")
            options.add_argument("--window-size=1200,900")

        # Ensure chromedriver is present via webdriver_manager (downloads once)
        
        service = Service()

        # Start driver
        driver = webdriver.Chrome(service=service, options=options)

        # Track driver tuple for cleanup
        with drivers_lock:
            active_drivers.append((driver, temp_profile, service))

        log.info(f"Processing: {title}")
        driver.get(BASE_URL)

        # 1. Input URL
        input_field = WebDriverWait(driver, 20).until(EC.presence_of_element_located((By.ID, "video")))
        input_field.clear()
        input_field.send_keys(video_url)
        input_field.send_keys(Keys.RETURN)

        # 2. Click Convert (optional)
        try:
            convert_btn = WebDriverWait(driver, 5).until(
                EC.element_to_be_clickable((By.XPATH, "//button[contains(text(), 'Convert')]"))
            )
            convert_btn.click()
        except Exception:
            pass

        # 3. Wait for Download Button and click
        download_btn = WebDriverWait(driver, 120).until(
            EC.element_to_be_clickable((By.XPATH, "//button[contains(text(), 'Download')]"))
        )
        download_btn.click()

        # 4. Handle optional 'Next' or popups
        try:
            next_btn = WebDriverWait(driver, 10).until(
                EC.element_to_be_clickable((By.XPATH, "//button[contains(text(), 'Next')]"))
            )
            next_btn.click()
        except Exception:
            pass

        # 5. Wait for download completion (watch the download folder)
        filename_hint = title.split(" - ")[0] if title else "youtube"
        finished = _wait_for_download_completion(filename_hint, timeout=180)
        if not finished:
            log.warning(f"Timeout waiting for file to complete: {title}")
        else:
            log.info(f"✔ Completed: {title}")

    except TimeoutException:
        log.warning(f"Timeout waiting for conversion: {title}")
    except WebDriverException as e:
        log.error(f"WebDriver error on {title}: {e}")
    except Exception as e:
        log.error(f"Error on {title}: {e}")
    finally:
        # Remove from active_drivers if present
        try:
            with drivers_lock:
                for tup in active_drivers[:]:
                    if tup[0] is driver:
                        active_drivers.remove(tup)
                        break
        except Exception:
            pass

        safe_driver_quit_tuple((driver, temp_profile, service))
        driver = None
        temp_profile = None
        service = None

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
        "[bold bright_blue] YOUTUBE TO MP3 [/bold bright_blue]\n[italic]Powered by Selenium and Python[/italic]"
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
    headless_choice = Confirm.ask("Run in Headless mode? (Hidden Windows)", default=False)

    #console.print("\n[yellow]How many windows to run at once?[/yellow]")
    #console.print("[italic]Warning: Too many windows (e.g., >4) may crash your PC or get IP blocked.[/italic]")
    workers = IntPrompt.ask("Number of concurrent downloads", default=3)

    if not api_key or not playlist_id:
        console.print("[bold red]Missing Credentials! Make sure API_KEY is set in environment or .env[/bold red]")
        return

    #console.print("\n[bold green]Fetching playlist data...[/bold green]")
    video_data = get_video_links(api_key, playlist_id)
    if not video_data:
        return

    #console.print(f"[green]✔ Found {len(video_data)} videos.[/green]\n")

    inputs_table = Table.grid(padding=(0, 2))
    inputs_table.add_column(style="cyan", justify="right")
    inputs_table.add_column(style="white")
    inputs_table.add_row("Playlist ID:", playlist_id)
    inputs_table.add_row("Headless Mode:", "Yes" if headless_choice else "No")
    inputs_table.add_row("Concurrent Downloads:", str(workers))
    inputs_table.add_row("Total Videos:", str(len(video_data)))
    #inputs_table.add_row()
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
        task_args = [((link, title), headless_choice) for link, title in video_data]

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
                        # If exception occurred in worker, it will be raised here
                        f.result()
                    except Exception as e:
                        # Already logged inside worker; ensure it doesn't crash the loop
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

    # Final cleanup, ensure drivers removed
    cleanup_all_drivers()
    time.sleep(0.2)

if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        console.print("\n[bold red]Download interrupted by user (Ctrl+C). Cleaning up drivers...[/bold red]")
    except Exception as e:
        console.print(f"\n[bold red]Script crashed: {e}. Cleaning up drivers...[/bold red]")
    finally:
        cleanup_all_drivers()
        time.sleep(0.5)
