# Split45

A YouTube video downloader and 45-minute splitter tool.

## Download

**Want to use Split45 right away? No installation needed!**

[📥 Download Split45.exe](https://github.com/zeniiitsuu/Split45/releases/tag/1.0) - Just download and double-click to run

## Features

- Download YouTube videos in lowest quality or MP3 audio
- Split long videos into 45-minute and remainders
- Handle up to 10 Videos simultaneously
- Zeni created it (Most important!)
- Automatic Sorting of results in folders and cleanup of original files

## Installation

1. Clone the repository:
```
git clone https://github.com/zeniiitsuu/Split45.git
cd Split45
```

2. Install dependencies:
```
pip install -r requirements.txt
```

3. Install FFmpeg from https://ffmpeg.org/download.html and add to PATH

4. Run:
```
python main.py
```


Output folders:
- downloads/ - Original files
- 45min/ - 45-minute parts
- remainder/ - Shorter final parts

## Requirements

- Python 3.7+
- FFmpeg
- Internet connection 