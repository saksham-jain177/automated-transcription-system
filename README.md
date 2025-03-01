# Automated Transcription System

A Python application that uses OpenAI's Whisper model to transcribe audio and video files. It recursively scans directories, transcribes media automatically, and monitors folders in real-time, all within a sleek PyQt5 GUI with logging.

## Features

- Recursive directory scanning for media files (MP3, WAV, MP4, etc.).
- Automatic transcription with Whisper, saving results as `.txt` files.
- Real-time folder monitoring with Watchdog.
- Skips already transcribed files for efficiency.
- Crash-resilient transcription with atomic file writes.
- User-friendly GUI with live status updates and logs.

## Requirements

- Python 3.8+
- Install dependencies: `pip install -r requirements.txt`

## Usage

1. Clone the repo: `git clone https://github.com/saksham-jain177/automated-transcription-system.git`
2. Install dependencies: `pip install -r requirements.txt`
3. Run: `python transcriber.py`
4. Select a directory and start monitoring!

## Demo

[Watch the video on Vimeo](https://vimeo.com/1061482495)

