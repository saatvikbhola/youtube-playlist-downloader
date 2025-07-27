import os
import time
import concurrent.futures
from dotenv import load_dotenv
from googleapiclient.discovery import build
from selenium import webdriver
from selenium.webdriver.firefox.service import Service
from selenium.webdriver.common.by import By
from selenium.webdriver.common.keys import Keys
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.firefox.options import Options

# --- Create a directory for downloads if it doesn't exist ---
DOWNLOAD_DIR = os.path.join(os.getcwd(), "downloads")
if not os.path.exists(DOWNLOAD_DIR):
    os.makedirs(DOWNLOAD_DIR)
    print(f"Created download directory at: {DOWNLOAD_DIR}")

# --- Part 1: Get all video links from the playlist ---
print(f"Current working directory: {os.getcwd()}")

load_dotenv()

API_KEY = os.getenv("API_KEY", " ") 
# This line will be dynamically replaced by the Streamlit app
playlist_id = "" 

if not playlist_id:
    print("ERROR: Playlist ID is missing. Exiting.")
    exit()

print("Fetching video links from YouTube playlist...")
try:
    youtube = build("youtube", "v3", developerKey=API_KEY)
    video_links = []
    next_page_token = None
    while True:
        response = youtube.playlistItems().list(
            part="snippet", playlistId=playlist_id, maxResults=50, pageToken=next_page_token
        ).execute()
        for item in response["items"]:
            video_id = item["snippet"]["resourceId"]["videoId"]
            video_links.append(f"https://www.youtube.com/watch?v={video_id}")
        next_page_token = response.get("nextPageToken")
        if not next_page_token:
            break
    print(f"Found {len(video_links)} videos in the playlist.")
    print("-" * 50)
except Exception as e:
    print(f"ERROR fetching from YouTube API: {e}")
    exit()

# --- Part 2: Process videos using multiple threads ---

BASE_URL = "https://y2mate.nu/en-s60K/"
GECKO_DRIVER_PATH = 'geckodriver.exe'

def download_video(video_url):
    """
    Initializes a Selenium WebDriver, processes a single video URL,
    and waits for the download to complete before exiting.
    """
    firefox_options = Options()
    # To prevent dozens of windows from opening, headless is strongly recommended
    firefox_options.add_argument("--headless")
    
    # --- Configure Firefox to auto-download files ---
    firefox_options.set_preference("browser.download.folderList", 2) # 0 for desktop, 1 for default downloads, 2 for custom folder
    firefox_options.set_preference("browser.download.dir", DOWNLOAD_DIR)
    firefox_options.set_preference("browser.download.useDownloadDir", True)
    firefox_options.set_preference("browser.helperApps.neverAsk.saveToDisk", "video/mp4, application/octet-stream") # Add other MIME types if needed

    service = Service(GECKO_DRIVER_PATH)
    driver = None
    try:
        driver = webdriver.Firefox(service=service, options=firefox_options)
        print(f"THREAD: Starting to process {video_url}")
        driver.get(BASE_URL)

        input_field = WebDriverWait(driver, 15).until(EC.presence_of_element_located((By.ID, "v")))
        input_field.send_keys(video_url)
        input_field.send_keys(Keys.RETURN)

        download_button = WebDriverWait(driver, 20).until(EC.element_to_be_clickable((By.XPATH, "//button[contains(text(), 'Download')]")))
        download_button.click()

        next_button = WebDriverWait(driver, 15).until(EC.element_to_be_clickable((By.XPATH, "//button[contains(text(), 'Next')]")))
        next_button.click()
        
        print(f"THREAD: Download initiated for {video_url}. Waiting for completion...")

        # --- Wait for the download to finish ---
        wait_time = 0
        download_timeout = 300  # 5 minutes
        while wait_time < download_timeout:
            # Check for .part files (Firefox's temporary download files)
            part_files = [f for f in os.listdir(DOWNLOAD_DIR) if f.endswith('.part')]
            if not part_files:
                print(f"THREAD: Download complete for {video_url}")
                break
            time.sleep(2) # Wait 2 seconds before checking again
            wait_time += 2
        else: # This 'else' belongs to the 'while' loop, runs if loop finishes without break
            print(f"THREAD: ERROR - Download timed out for {video_url} after {download_timeout} seconds.")

    except Exception as e:
        print(f"THREAD: An unexpected error occurred with {video_url}: {e}")
    finally:
        if driver:
            driver.quit()

# --- Main execution block ---
if video_links:
    with concurrent.futures.ThreadPoolExecutor(max_workers=5) as executor:
        print(f"Starting downloader with 5 workers...")
        executor.map(download_video, video_links)

print("All downloads are complete.")
