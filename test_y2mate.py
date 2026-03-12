import time
from selenium import webdriver
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.common.by import By
from selenium.webdriver.common.keys import Keys
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC

def test_y2mate(video_url):
    print("Starting test...")
    options = webdriver.ChromeOptions()
    
    import os
    download_dir = os.path.join(os.getcwd(), "downloads_test")
    if not os.path.exists(download_dir):
        os.makedirs(download_dir)
    prefs = {
        "download.default_directory": download_dir,
        "download.prompt_for_download": False,
        "download.directory_upgrade": True,
        "safebrowsing.enabled": True,
    }
    options.add_experimental_option("prefs", prefs)
    
    options.add_argument("--headless=new")
    options.add_argument("--disable-gpu")
    options.add_argument("--no-sandbox")
    options.add_argument("--disable-dev-shm-usage")
    options.add_argument("--window-size=1200,900")
    options.add_argument("user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36")
    
    service = Service()
    driver = webdriver.Chrome(service=service, options=options)
    
    try:
        print("Loading https://v1.y2mate.nu...")
        driver.get("https://v1.y2mate.nu")
        
        # 1. Input URL
        print("Finding input field ID 'video'...")
        try:
            input_field = WebDriverWait(driver, 10).until(EC.presence_of_element_located((By.ID, "video")))
            input_field.clear()
            input_field.send_keys(video_url)
            input_field.send_keys(Keys.RETURN)
            print("URL submitted.")
        except Exception as e:
            print(f"Failed to find ID 'video': {e.__class__.__name__}")
            return

        # 2. Click Convert
        print("Looking for Convert button...")
        try:
            convert_btn = WebDriverWait(driver, 5).until(
                EC.element_to_be_clickable((By.XPATH, "//button[contains(text(), 'Convert')]"))
            )
            convert_btn.click()
            print("Convert button clicked.")
        except Exception as e:
            print(f"No Convert button found: {e.__class__.__name__}")

        # 3. Wait for Download
        print("Looking for Download button...")
        try:
            download_btn = WebDriverWait(driver, 60).until(
                EC.element_to_be_clickable((By.XPATH, "//button[contains(text(), 'Download')]"))
            )
            print("Download button found AND is clickable!")
            download_btn.click()
            print("Download button clicked.")
        except Exception as e:
            print(f"No Download button found: {e.__class__.__name__}")

        # 4. Wait for Next (if any)
        print("Looking for Next button...")
        try:
            next_btn = WebDriverWait(driver, 5).until(
                EC.element_to_be_clickable((By.XPATH, "//button[contains(text(), 'Next')]"))
            )
            print("Next button found!")
        except Exception as e:
            print(f"No Next button found: {e.__class__.__name__}")
            
    finally:
        driver.quit()
        print("Test finished.")

if __name__ == "__main__":
    test_y2mate("https://www.youtube.com/watch?v=JjTqE69ZkUs")
