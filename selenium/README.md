# Selenium YouTube Downloader

This subdirectory contains the Selenium-based implementation of the YouTube Playlist Downloader.

## Overview

The scripts in this directory utilize Selenium WebDriver to automate interaction with `v1.y2mate.nu` to convert and download audio files from YouTube videos. This method acts as a web scraper/automator simulating human interactions on the web converter service.

## Core Files

- **`audio_dl.py`**: The primary backend script handling concurrent downloading using Selenium and Chrome WebDriver in headless/windowed modes. It uses the YouTube Data API to fetch playlist data and manages independent browser instances for concurrent execution.
- **`main_script.py`**: An alternative backend script configured with Firefox WebDriver.
- **`test_y2mate.py`**: A testing script to verify the interaction sequence with the y2mate converter website.
- **`geckodriver.exe`**: Provide Mozilla Firefox WebDriver capabilities.

## User Interfaces

- **`app.py` & `tui.py` & `tui1.py`**: Terminal User Interface (TUI) variations powered by the `rich` and `textual` libraries. They provide a text-based, visual progress interface within the terminal. `tui1.py` showcases an interactive Textual app.
- **`streamlit_app.py`**: A graphical web interface using `streamlit` to quickly input the API key, playlist ID, and start the processing dynamically.

## Installation & Setup

1. Ensure the dependencies (`selenium`, `webdriver-manager`, `google-api-python-client`, `python-dotenv`, `rich`, `textual`, `streamlit`) are installed.
2. An `.env` file should be present in the directory specifying your YouTube API Key (`API_KEY=your_api_key_here`).
3. You can run any of the interfaces (e.g., `python tui1.py` or `streamlit run streamlit_app.py`).

## Notes
Using `selenium` can be more resource-intensive due to launching headless browser profiles per concurrent download. The yt-dlp version provides a lightweight alternative if preferred.
