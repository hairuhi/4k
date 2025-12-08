# Py4KDownloader

A Python-based 4K video downloader with GUI.

## Prerequisities

This application requires [FFmpeg](https://ffmpeg.org/) to be installed and available in the system path or placed in the application directory.

### How to set up FFmpeg

1.  Download FFmpeg from [https://ffmpeg.org/download.html](https://ffmpeg.org/download.html).
2.  Extract the downloaded archive.
3.  Copy `ffmpeg.exe` and `ffprobe.exe` from the `bin` folder.
4.  Paste them into the same folder as this application (or `dist/` folder if running from executable).

## Installation

1.  Clone this repository.
2.  Install dependencies:
    ```bash
    pip install -r requirements.txt
    ```

## Usage

Run the main script:
```bash
python main.py
```
