"""
tui1.py — Textual-based YouTube Playlist Audio Downloader
Compatible with modern Textual (0.40–0.55+)
"""

import os
import time
import logging
import threading
import concurrent.futures
import tempfile
import shutil
import asyncio
from collections import deque
from dotenv import load_dotenv
from googleapiclient.discovery import build

from selenium import webdriver
from selenium.webdriver.chrome.service import Service
from webdriver_manager.chrome import ChromeDriverManager
from selenium.webdriver.common.by import By
from selenium.webdriver.common.keys import Keys
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import TimeoutException, WebDriverException

# TEXTUAL 0.55+ imports
from textual.app import App, ComposeResult
from textual.widgets import (
    Header,
    Footer,
    Button,
    Input,
    Checkbox,
    Static,
    Label,
    ProgressBar,
)
from textual.containers import (
    Vertical,
    Horizontal,
    ScrollableContainer,
)

load_dotenv()

# --- Config ---
BASE_URL = "https://y2mate.nu/ysM1/"
DOWNLOAD_DIR = os.path.join(os.getcwd(), "downloads")
if not os.path.exists(DOWNLOAD_DIR):
    os.makedirs(DOWNLOAD_DIR)

LOG_MAX_LINES = 500

# --- Logging capture ---
class GuiLogHandler(logging.Handler):
    """Capture logs for display in Textual UI."""
    def __init__(self):
        super().__init__()
        self.buffer = deque(maxlen=LOG_MAX_LINES)
        self.callback = None
        self.setFormatter(logging.Formatter("[%(asctime)s] %(levelname)s: %(message)s", "%H:%M:%S"))

    def emit(self, record):
        text = self.format(record)
        self.buffer.append(text)
        if self.callback:
            try:
                self.callback(text)
            except:
                pass

logger = logging.getLogger("yt_downloader")
logger.setLevel(logging.INFO)
handler = GuiLogHandler()
logger.addHandler(handler)

# Silence noisy libs
logging.getLogger("webdriver_manager").setLevel(logging.ERROR)


# --- Driver cleanup tracking ---
active_drivers = []
drivers_lock = threading.Lock()


def cleanup_all_drivers():
    with drivers_lock:
        for driver, temp_profile, service in list(active_drivers):
            try:
                if driver:
                    try: driver.quit()
                    except: pass
                if service and hasattr(service, "process") and service.process:
                    try: service.process.kill()
                    except: pass
            finally:
                try:
                    if temp_profile and os.path.exists(temp_profile):
                        shutil.rmtree(temp_profile, ignore_errors=True)
                except:
                    pass
        active_drivers.clear()


# --- YouTube API ---
def get_video_links(api_key, playlist_id):
    try:
        youtube = build("youtube", "v3", developerKey=api_key)
        videos = []
        next_page = None

        while True:
            resp = youtube.playlistItems().list(
                part="snippet", playlistId=playlist_id, pageToken=next_page, maxResults=50
            ).execute()

            for item in resp.get("items", []):
                vid = item["snippet"]["resourceId"]["videoId"]
                title = item["snippet"]["title"]
                safe = "".join(c for c in title if c.isalnum() or c in " -_").strip()
                videos.append((f"https://www.youtube.com/watch?v={vid}", safe))

            next_page = resp.get("nextPageToken")
            if not next_page:
                break

        return videos
    except Exception as e:
        logger.error(f"API fetch error: {e}")
        return []


# --- Download helpers ---
def wait_for_download(filename_hint, timeout=180):
    deadline = time.time() + timeout
    while time.time() < deadline:
        files = os.listdir(DOWNLOAD_DIR)
        partial = [f for f in files if f.endswith(".crdownload") or f.endswith(".part")]
        if partial:
            time.sleep(1)
            continue
        matches = [f for f in files if filename_hint.lower() in f.lower()]
        if matches:
            return True
        time.sleep(1)
    return False


def safe_driver_quit_tuple(driver_tuple):
    driver, temp_profile, service = driver_tuple
    try:
        if driver:
            try: driver.quit()
            except: pass
        if service and hasattr(service, "process") and service.process:
            try: service.process.kill()
            except: pass
    finally:
        try:
            if temp_profile and os.path.exists(temp_profile):
                shutil.rmtree(temp_profile, ignore_errors=True)
        except:
            pass


def download_worker(args):
    (url, title), headless = args
    temp_profile = tempfile.mkdtemp(prefix="ytprof_")
    driver = None
    service = None

    try:
        opts = webdriver.ChromeOptions()
        opts.add_experimental_option("prefs", {
            "download.default_directory": DOWNLOAD_DIR,
            "download.prompt_for_download": False,
            "safebrowsing.enabled": True
        })
        opts.add_argument(f"--user-data-dir={temp_profile}")
        opts.add_argument("--no-first-run")
        opts.add_argument("--disable-gpu")

        if headless:
            try:
                opts.add_argument("--headless=new")
            except:
                opts.add_argument("--headless")
            opts.add_argument("--window-size=1200,900")

        chromedriver = ChromeDriverManager().install()
        service = Service(chromedriver)
        driver = webdriver.Chrome(service=service, options=opts)

        with drivers_lock:
            active_drivers.append((driver, temp_profile, service))

        logger.info(f"Processing: {title}")
        driver.get(BASE_URL)

        box = WebDriverWait(driver, 20).until(EC.presence_of_element_located((By.ID, "v")))
        box.clear()
        box.send_keys(url)
        box.send_keys(Keys.RETURN)

        # Convert button
        try:
            btn = WebDriverWait(driver, 5).until(
                EC.element_to_be_clickable((By.XPATH, "//button[contains(text(),'Convert')]"))
            )
            btn.click()
        except:
            pass

        dl = WebDriverWait(driver, 120).until(
            EC.element_to_be_clickable((By.XPATH, "//button[contains(text(),'Download')]"))
        )
        dl.click()

        # Optional next
        try:
            nxt = WebDriverWait(driver, 8).until(
                EC.element_to_be_clickable((By.XPATH, "//button[contains(text(),'Next')]"))
            )
            nxt.click()
        except:
            pass

        hint = title.split(" - ")[0]
        if wait_for_download(hint):
            logger.info(f"✔ Completed: {title}")
        else:
            logger.warning(f"Timeout: {title}")

    except Exception as e:
        logger.error(f"Error on {title}: {e}")

    finally:
        with drivers_lock:
            try:
                active_drivers.remove((driver, temp_profile, service))
            except:
                pass
        safe_driver_quit_tuple((driver, temp_profile, service))


# --- TEXTUAL APP ---
class YouTubeDownloaderApp(App):
    CSS = """
    #form, #middle, #bottom {
        padding: 1;
    }
    #logs_container {
        height: 25;
        border: solid green;
        padding: 1;
    }
    """

    total = 0
    completed = 0
    running = False

    def compose(self) -> ComposeResult:
        yield Header()

        # FORM SECTION
        with Vertical(id="form"):
            with Horizontal():
                yield Label("Playlist ID:")
                yield Input(placeholder="Enter Playlist ID", id="playlist")

            with Horizontal():
                yield Checkbox(label="Headless", id="headless")
                yield Label("Workers:")
                yield Input(value="3", id="input_workers", placeholder="3")

            with Horizontal():
                yield Button("Start", id="start", variant="success")
                yield Button("Stop", id="stop", variant="error")
                yield Button("Clear Logs", id="clear_logs", variant="primary")

        # MIDDLE PROGRESS
        with Horizontal(id="middle"):
            yield ProgressBar(id="prog", total=100)
            yield Label("0/0", id="count")

        # BOTTOM LOGS
        with Vertical(id="bottom"):
            yield Label("Logs:")
            with ScrollableContainer(id="logs_container"):
                yield Static("", id="logs")

        yield Footer()

    async def on_mount(self):
        self.playlist = self.query_one("#playlist", Input)
        self.headless = self.query_one("#headless", Checkbox)
        self.workers_input = self.query_one("#input_workers", Input)

        self.logs_widget = self.query_one("#logs", Static)
        self.logs_container = self.query_one("#logs_container", ScrollableContainer)
        self.prog = self.query_one("#prog", ProgressBar)
        self.count_label = self.query_one("#count", Label)
        self.btn_start = self.query_one("#start", Button)
        self.btn_stop = self.query_one("#stop", Button)

        self.btn_stop.disabled = True

        self.executor = concurrent.futures.ThreadPoolExecutor(max_workers=8)

        handler.callback = lambda line: self.call_from_thread(self.append_log, line)

    def append_log(self, line):
        existing = str(self.logs_widget.renderable)
        lines = existing.splitlines() if existing else []
        lines.append(line)
        lines = lines[-LOG_MAX_LINES:]
        self.logs_widget.update("\n".join(lines))
        self.logs_container.scroll_end(animate=False)

    async def on_button_pressed(self, event: Button.Pressed):
        if event.button.id == "start":
            await self.start_downloads()
        elif event.button.id == "stop":
            await self.stop_downloads()
        elif event.button.id == "clear_logs":
            self.logs_widget.update("")
            handler.buffer.clear()

    async def start_downloads(self):
        if self.running:
            logger.warning("Already running!")
            return

        playlist_id = self.playlist.value.strip()
        if not playlist_id:
            logger.error("Playlist ID required.")
            return

        try:
            workers = int(self.workers_input.value.strip())
            if workers < 1:
                workers = 1
        except:
            workers = 3

        headless = self.headless.value
        api_key = os.getenv("API_KEY")

        if not api_key:
            logger.error("API_KEY missing in .env")
            return

        logger.info("Fetching playlist data...")
        loop = asyncio.get_running_loop()
        video_list = await loop.run_in_executor(self.executor, get_video_links, api_key, playlist_id)

        if not video_list:
            logger.error("No videos found.")
            return

        logger.info(f"Found {len(video_list)} videos.")

        self.total = len(video_list)
        self.completed = 0
        self.prog.total = self.total
        self.prog.update(0)
        self.count_label.update(f"0/{self.total}")

        self.running = True
        self.btn_start.disabled = True
        self.btn_stop.disabled = False

        tasks = [((url, title), headless) for url, title in video_list]

        async def runner():
            loop = asyncio.get_running_loop()
            futures = [
                loop.run_in_executor(self.executor, download_worker, arg)
                for arg in tasks
            ]

            for coro in asyncio.as_completed(futures):
                try:
                    await coro
                except:
                    pass
                self.completed += 1
                self.prog.update(self.completed)
                self.count_label.update(f"{self.completed}/{self.total}")

            logger.info("All tasks completed.")
            self.running = False
            self.btn_start.disabled = False
            self.btn_stop.disabled = True
            cleanup_all_drivers()

        asyncio.create_task(runner())

    async def stop_downloads(self):
        if not self.running:
            logger.info("Not running.")
            return

        logger.info("Stopping downloads...")

        cleanup_all_drivers()
        self.running = False
        self.btn_start.disabled = False
        self.btn_stop.disabled = True

        logger.info("Stopped.")

    async def on_unmount(self):
        cleanup_all_drivers()
        try:
            self.executor.shutdown(wait=False)
        except:
            pass


if __name__ == "__main__":
    YouTubeDownloaderApp().run()
