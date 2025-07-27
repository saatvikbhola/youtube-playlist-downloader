# YouTube Playlist Downloader

This project provides a web-based interface to download all videos from a specified YouTube playlist. It uses a combination of the YouTube Data API to fetch video information and a web scraping component to handle the video downloads.

## Table of Contents
- [Features](#features)
- [How It Works](#how-it-works)
- [Setup and Installation](#setup-and-installation)
- [Usage](#usage)
- [Scripts Description](#scripts-description)
- [Dependencies](#dependencies)
- [License](#license)

## Features

* **Web Interface:** A user-friendly UI built with Streamlit to input your API key and playlist ID.
* **Real-time Logging:** View the script's progress and any potential errors directly in the web interface.
* **Concurrent Downloads:** Utilizes multithreading to download multiple videos simultaneously, speeding up the process.
* **Automated Downloading:** Employs Selenium to automate the process of downloading videos from a third-party service.
* **Secure API Key Handling:** Uses a `.env` file to manage your YouTube API key, keeping it out of the source code.

## How It Works

The application is composed of two main Python scripts:

1.  **`main_script.py` (The Backend Downloader):**
    * It first uses the YouTube Data API v3 to retrieve a list of all video URLs from a given playlist ID.
    * For each video URL, it spins up a new thread to handle the download.
    * Each thread launches a headless Firefox browser using Selenium.
    * It navigates to a video downloading website (`y2mate`), inputs the video URL, and initiates the download.
    * It then waits for the download to complete before closing the browser instance.

2.  **`app.py` (The Streamlit Web UI):**
    * This script creates a simple web page with input fields for the YouTube API Key and the Playlist ID.
    * When the "Start Processing" button is clicked, it reads the content of `main_script.py`.
    * It dynamically injects the user-provided `playlist_id` into the script's content.
    * It then runs the modified script as a subprocess, passing the `API_KEY` as an environment variable.
    * The output of the subprocess (both `stdout` and `stderr`) is captured and displayed in real-time on the web page.

## Setup and Installation

Follow these steps to get the project running on your local machine.

### 1. Prerequisites
* Python 3.7+
* Mozilla Firefox browser installed.
* A YouTube Data API v3 key. You can get one from the [Google Cloud Console](https://console.cloud.google.com/).

### 2. Clone the Repository
```bash
git clone <your-repository-url>
cd <your-repository-name>
```

### 3. Install Dependencies

Create a `requirements.txt` file with the following content:
```
streamlit
python-dotenv
google-api-python-client
selenium
```
Then, install the required packages:
```bash
pip install -r requirements.txt
```

### 4. GeckoDriver Setup
The script requires Mozilla's GeckoDriver to control the Firefox browser.
* Download the latest version of GeckoDriver for your operating system from the [official releases page](https://github.com/mozilla/geckodriver/releases).
* Extract the downloaded file and place `geckodriver.exe` (or `geckodriver` on Linux/macOS) in the root directory of this project.

### 5. Configuration
Create a file named `.env` in the root of your project directory and add your YouTube API key to it:
```
API_KEY="YOUR_YOUTUBE_API_KEY_HERE"
```
The Streamlit app will automatically load this key. You can also enter it directly in the web interface.

## Usage

1.  Ensure all setup steps are complete.
2.  Open your terminal, activate the virtual environment, and run the Streamlit app:
    ```bash
    streamlit run app.py
    ```
3.  Your web browser should open with the application's UI.
4.  If you didn't create a `.env` file, enter your YouTube API Key.
5.  Enter the ID of the YouTube playlist you want to download.
6.  Click the "▶️ Start Processing" button.
7.  The logs from the download script will appear on the page, and the downloaded videos will be saved in a new `downloads` directory within the project folder.

## Scripts Description

### `main_script.py`
This is the core script responsible for the download logic.

* **`DOWNLOAD_DIR`**: A constant that defines the directory where videos will be saved.
* **API Interaction**: Fetches video links from the specified YouTube playlist using the `googleapiclient`.
* **`download_video(video_url)`**: A function that orchestrates the download of a single video. It configures and launches a headless Firefox instance, navigates the download website, and waits for the file to be fully downloaded.
* **Multithreading**: Uses a `ThreadPoolExecutor` to run multiple instances of `download_video` concurrently, with a default of 5 workers.

### `app.py`
This script provides the web front-end for the downloader.

* **Streamlit UI**: Sets up the page title, description, and input fields for the API key and playlist ID.
* **Dynamic Script Execution**: When the start button is pressed, it:
    1.  Reads the `main_script.py` file.
    2.  Replaces a placeholder with the actual `playlist_id`.
    3.  Saves this modified script to a temporary file.
    4.  Executes the temporary script using `subprocess.Popen`, ensuring that the `API_KEY` is available as an environment variable.
    5.  Captures and displays the script's output in real-time.
    6.  Cleans up by deleting the temporary file once execution is complete.

## Dependencies

* **streamlit**: To create the web application interface.
* **python-dotenv**: To load environment variables from a `.env` file.
* **google-api-python-client**: To interact with the YouTube Data API.
* **selenium**: To automate the web browser for downloading videos.

## License

This project is licensed under the MIT License. See the `LICENSE` file for more details.
