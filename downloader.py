import yt_dlp
import os
import ssl
import urllib3
import sys
from typing import Callable, List, Dict

# Disable SSL warnings and verification globally
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)
ssl._create_default_https_context = ssl._create_unverified_context

class VideoDownloader:
    def __init__(self, progress_callback: Callable[[str, float], None] = None, output_folder: str = None):
        self.progress_callback = progress_callback
        self.output_folder = output_folder or os.getcwd()
        self.downloads_folder = os.path.join(self.output_folder, "downloads")
        
        # Find FFmpeg binaries for yt-dlp
        self.ffmpeg_path = self._find_ffmpeg()
        self.ffprobe_path = self._find_ffprobe()
        
        # Track progress
        self.current_file_index = 0
        self.total_files = 0
        self.current_audio_only = False

    def _find_ffmpeg(self):
        """Find FFmpeg executable - bundled or system"""
        # Check if running as exe (PyInstaller)
        if getattr(sys, 'frozen', False):
            # Running as .exe - look for bundled ffmpeg
            base_path = sys._MEIPASS
            ffmpeg_path = os.path.join(base_path, 'ffmpeg', 'ffmpeg.exe')
            if os.path.exists(ffmpeg_path):
                return ffmpeg_path
        else:
            # Running as script - look in local ffmpeg folder first
            local_ffmpeg = os.path.join(os.path.dirname(__file__), 'ffmpeg', 'ffmpeg.exe')
            if os.path.exists(local_ffmpeg):
                return local_ffmpeg
        
        # Fallback to system ffmpeg
        return 'ffmpeg'

    def _find_ffprobe(self):
        """Find FFprobe executable - bundled or system"""
        # Check if running as exe (PyInstaller)
        if getattr(sys, 'frozen', False):
            # Running as .exe - look for bundled ffprobe
            base_path = sys._MEIPASS
            ffprobe_path = os.path.join(base_path, 'ffmpeg', 'ffprobe.exe')
            if os.path.exists(ffprobe_path):
                return ffprobe_path
        else:
            # Running as script - look in local ffmpeg folder first
            local_ffprobe = os.path.join(os.path.dirname(__file__), 'ffmpeg', 'ffprobe.exe')
            if os.path.exists(local_ffprobe):
                return local_ffprobe
        
        # Fallback to system ffprobe
        return 'ffprobe'

    def _get_output_template(self, audio_only: bool) -> str:
        return os.path.join(self.downloads_folder, "%(title)s.%(ext)s")

    def _progress_hook(self, d: Dict):
        if d['status'] == 'downloading':
            if 'total_bytes' in d and 'downloaded_bytes' in d:
                progress = (d['downloaded_bytes'] / d['total_bytes']) * 100
            elif 'total_bytes_estimate' in d and 'downloaded_bytes' in d:
                progress = (d['downloaded_bytes'] / d['total_bytes_estimate']) * 100
            else:
                progress = 0
            
            if self.progress_callback:
                media_type = "audio" if self.current_audio_only else "video"
                filename = os.path.basename(d.get('filename', 'Unknown'))
                status_msg = f"Downloading {media_type} {self.current_file_index}/{self.total_files}: {filename}"
                self.progress_callback(status_msg, progress)
                
        elif d['status'] == 'finished':
            if self.progress_callback:
                media_type = "audio" if self.current_audio_only else "video"
                filename = os.path.basename(d.get('filename', 'Unknown'))
                
                # Check if we need audio extraction
                if self.current_audio_only and not filename.endswith('.mp3'):
                    status_msg = f"Converting to MP3 {self.current_file_index}/{self.total_files}: {filename}"
                    self.progress_callback(status_msg, 95)  # Show high progress for conversion
                else:
                    status_msg = f"Completed {media_type} {self.current_file_index}/{self.total_files}: {filename}"
                    self.progress_callback(status_msg, 100)
                    
        elif d['status'] == 'error':
            if self.progress_callback:
                filename = os.path.basename(d.get('filename', 'Unknown'))
                status_msg = f"Error downloading {self.current_file_index}/{self.total_files}: {filename}"
                self.progress_callback(status_msg, -1)

    def download_videos(self, urls: List[str], audio_only: bool = False) -> List[str]:
        # Create downloads folder inside the selected output folder
        if not os.path.exists(self.downloads_folder):
            os.makedirs(self.downloads_folder)
            print(f"Created downloads folder: {self.downloads_folder}")

        downloaded_files = []
        self.total_files = len(urls)
        self.current_audio_only = audio_only
        successful_downloads = 0
        
        print(f"Using FFmpeg: {self.ffmpeg_path}")
        print(f"Using FFprobe: {self.ffprobe_path}")
        
        media_type = "audio files" if audio_only else "videos"
        if self.progress_callback:
            self.progress_callback(f"Starting download of {len(urls)} {media_type}...", 0)
        
        # Use a much simpler configuration with maximum SSL bypass
        ydl_opts = {
            'format': 'bestaudio/best' if audio_only else 'worst[height<=480]/best[height<=480]/worst',
            'outtmpl': self._get_output_template(audio_only),
            'progress_hooks': [self._progress_hook],
            'postprocessors': [{
                'key': 'FFmpegExtractAudio',
                'preferredcodec': 'mp3',
            }] if audio_only else [],
            'merge_output_format': 'mp4' if not audio_only else None,
            'quiet': False,
            'no_warnings': False,
            # Tell yt-dlp where to find FFmpeg
            'ffmpeg_location': os.path.dirname(self.ffmpeg_path) if os.path.dirname(self.ffmpeg_path) else None,
            # Maximum SSL bypass options
            'nocheckcertificate': True,
            'prefer_insecure': True,
            'ignoreerrors': True,
            'socket_timeout': 60,
            'retries': 3,
            'no_color': True,
            # Add user agent to avoid detection
            'http_headers': {
                'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36',
            },
            # Try to use legacy server connections
            'legacy_server_connect': True,
            # Disable HTTPS where possible
            'prefer_free_formats': True,
        }

        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            for idx, url in enumerate(urls):
                self.current_file_index = idx + 1
                try:
                    print(f"\nDownloading {idx + 1}/{len(urls)}: {url}")
                    print(f"Format: {'Audio only' if audio_only else 'Video (low quality)'}")
                    print(f"Output folder: {self.downloads_folder}")
                    
                    # Simple download - let yt-dlp handle format selection
                    info = ydl.extract_info(url, download=True)
                    
                    if info is None:
                        print(f"Could not download {url}")
                        if self.progress_callback:
                            self.progress_callback(f"Failed to download {idx + 1}/{len(urls)}", -1)
                        continue

                    # Get filename
                    filename = ydl.prepare_filename(info)
                    if audio_only:
                        # The postprocessor will convert to mp3
                        filename = filename.rsplit(".", 1)[0] + ".mp3"

                    if os.path.exists(filename):
                        downloaded_files.append(filename)
                        successful_downloads += 1
                        print(f"Successfully downloaded: {filename}")
                        
                        if self.progress_callback:
                            media_type = "audio" if audio_only else "video"
                            self.progress_callback(f"✅ Completed {media_type} {idx + 1}/{len(urls)}", 100)
                    else:
                        print(f"File not found after download: {filename}")
                        if self.progress_callback:
                            self.progress_callback(f"❌ Failed {idx + 1}/{len(urls)}", -1)

                except Exception as e:
                    print(f"Error downloading {url}: {str(e)}")
                    if self.progress_callback:
                        self.progress_callback(f"❌ Error {idx + 1}/{len(urls)}: {str(e)}", -1)

        # Final status message
        if self.progress_callback:
            media_type = "audio files" if audio_only else "videos"
            if successful_downloads == len(urls):
                self.progress_callback(f"🎉 All {successful_downloads} {media_type} downloaded successfully!", 100)
            elif successful_downloads > 0:
                self.progress_callback(f"✅ Downloaded {successful_downloads}/{len(urls)} {media_type}", 100)
            else:
                self.progress_callback(f"❌ No {media_type} downloaded", -1)

        return downloaded_files 