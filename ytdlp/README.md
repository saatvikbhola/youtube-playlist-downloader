# yt-dlp YouTube Downloader

This subdirectory contains the `yt-dlp`-based implementation of the YouTube Playlist Downloader.

## Overview

Unlike the Selenium scraper alternative, this directory houses the script using the highly efficient `yt-dlp` library to directly download and extract audio from YouTube URLs. This approach is much faster, uses fewer system resources, and does not require launching web browsers or automated UI interactions.

## Core Files

- **`audio_dl_ytdlp.py`**: The main script driving the process. It uses the YouTube Data API to fetch your specified playlist items and employs multi-threading to pass those URLs directly to `yt-dlp`. Features include:
  - Best-audio filtering.
  - Automatic `ffmpeg` post-processing to convert tracks to FLAC format.
  - Embedding metadata and video thumbnails directly into the audio files.
  - An integrated terminal UI built with `rich` for visualizing live download progress and logs tracking.

## Installation & Setup

1. Ensure `yt-dlp`, `ffmpeg`, `google-api-python-client`, `python-dotenv`, and `rich` are installed.
2. Make sure you have an `.env` file containing your `API_KEY` (e.g., `API_KEY=your_key_here`).
3. Optionally, ensure the download directory is set based on your preferences inside the script.

## Usage

Simply run the script:
```bash
python audio_dl_ytdlp.py
```

The script will ask for a playlist ID using a terminal prompt and download everything concurrently into the designated local folder (`downloads`).
