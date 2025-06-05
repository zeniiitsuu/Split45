import os
import subprocess
import math
import sys
from typing import List, Callable

# Windows-specific configuration to hide console windows
if sys.platform == "win32":
    import subprocess
    startupinfo = subprocess.STARTUPINFO()
    startupinfo.dwFlags |= subprocess.STARTF_USESHOWWINDOW
    startupinfo.wShowWindow = subprocess.SW_HIDE
    subprocess_kwargs = {
        'startupinfo': startupinfo,
        'creationflags': subprocess.CREATE_NO_WINDOW
    }
else:
    subprocess_kwargs = {}

class MediaProcessor:
    SEGMENT_LENGTH = 2700

    def __init__(self, progress_callback: Callable[[str, float], None] = None, output_folder: str = None):
        self.progress_callback = progress_callback
        self.output_folder = output_folder or os.getcwd()
        self.downloads_folder = os.path.join(self.output_folder, "downloads")
        self.min45_folder = os.path.join(self.output_folder, "45min")
        self.remainder_folder = os.path.join(self.output_folder, "remainder")
        
        self.ffmpeg_path = self._find_ffmpeg()
        self.ffprobe_path = self._find_ffprobe()
        
        print(f"MediaProcessor initialized with FFmpeg: {self.ffmpeg_path}")
        print(f"Output folders will be created in: {self.output_folder}")

    def _find_ffmpeg(self):
        bundled_path = os.path.join(os.path.dirname(__file__), "ffmpeg", "ffmpeg.exe")
        if os.path.exists(bundled_path):
            return bundled_path
        
        try:
            result = subprocess.run(['where', 'ffmpeg'], capture_output=True, text=True, shell=True, **subprocess_kwargs)
            if result.returncode == 0:
                return result.stdout.strip().split('\n')[0]
        except:
            pass
        
        return "ffmpeg"

    def _find_ffprobe(self):
        bundled_path = os.path.join(os.path.dirname(__file__), "ffmpeg", "ffprobe.exe")
        if os.path.exists(bundled_path):
            return bundled_path
        
        try:
            result = subprocess.run(['where', 'ffprobe'], capture_output=True, text=True, shell=True, **subprocess_kwargs)
            if result.returncode == 0:
                return result.stdout.strip().split('\n')[0]
        except:
            pass
        
        return "ffprobe"

    def _create_output_dirs(self):
        os.makedirs(self.min45_folder, exist_ok=True)
        os.makedirs(self.remainder_folder, exist_ok=True)

    def _get_base_name(self, file_path: str) -> str:
        return os.path.splitext(os.path.basename(file_path))[0]

    def _get_output_path(self, base_name: str, part: int, is_full: bool, extension: str) -> str:
        folder = self.min45_folder if is_full else self.remainder_folder
        return os.path.join(folder, f"{base_name}_part{part}{extension}")

    def _get_video_duration(self, file_path: str) -> float:
        try:
            cmd = [
                self.ffprobe_path, '-v', 'quiet', '-print_format', 'json', '-show_format', file_path
            ]
            
            result = subprocess.run(cmd, capture_output=True, text=True, timeout=30, **subprocess_kwargs)
            
            if result.returncode != 0:
                print(f"FFprobe error: {result.stderr}")
                return 0
            
            import json
            data = json.loads(result.stdout)
            duration = float(data['format']['duration'])
            return duration
            
        except Exception as e:
            print(f"Error getting duration: {e}")
            return 0

    def _copy_short_video(self, file_path: str, audio_only: bool = False) -> str:
        base_name = self._get_base_name(file_path)
        
        if audio_only:
            output_path = os.path.join(self.remainder_folder, f"{base_name}.mp3")
            cmd = [
                self.ffmpeg_path, '-i', file_path,
                '-acodec', 'mp3', '-ab', '128k',
                '-y', output_path
            ]
        else:
            output_path = os.path.join(self.remainder_folder, f"{base_name}.mp4")
            cmd = [
                self.ffmpeg_path, '-i', file_path,
                '-c', 'copy',
                '-y', output_path
            ]
        
        print(f"Running: {' '.join(cmd)}")
        result = subprocess.run(cmd, capture_output=True, text=True, **subprocess_kwargs)
        
        if result.returncode == 0:
            return output_path
        else:
            print(f"FFmpeg error: {result.stderr}")
            return ""

    def _split_video_ffmpeg(self, file_path: str, start_time: int, duration: int, output_path: str, audio_only: bool = False):
        try:
            if audio_only:
                cmd = [
                    self.ffmpeg_path, '-i', file_path, 
                    '-ss', str(start_time), '-t', str(duration),
                    '-acodec', 'mp3', '-ab', '128k',
                    '-y', output_path
                ]
            else:
                cmd = [
                    self.ffmpeg_path, '-i', file_path,
                    '-ss', str(start_time), '-t', str(duration),
                    '-c', 'copy',
                    '-y', output_path
                ]
            
            print(f"Running: {' '.join(cmd)}")
            result = subprocess.run(cmd, capture_output=True, text=True, **subprocess_kwargs)
            
            if result.returncode != 0:
                print(f"FFmpeg error: {result.stderr}")
                if not audio_only and '-c copy' in cmd:
                    print("Stream copy failed, trying with re-encoding...")
                    cmd = [
                        self.ffmpeg_path, '-i', file_path,
                        '-ss', str(start_time), '-t', str(duration),
                        '-c:v', 'libx264', '-preset', 'ultrafast',
                        '-c:a', 'aac', '-b:a', '128k',
                        '-y', output_path
                    ]
                    result = subprocess.run(cmd, capture_output=True, text=True, **subprocess_kwargs)
            
            return result.returncode == 0
            
        except Exception as e:
            print(f"Error splitting with ffmpeg: {e}")
            return False

    def _delete_original_file(self, file_path: str):
        try:
            if os.path.exists(file_path):
                os.remove(file_path)
                print(f"Deleted original file: {os.path.basename(file_path)}")
                return True
        except Exception as e:
            print(f"Could not delete original file {file_path}: {e}")
            return False

    def process_video(self, file_path: str, audio_only: bool = False, delete_original: bool = True) -> List[str]:
        self._create_output_dirs()
        output_files = []
        processing_successful = False
        
        try:
            print(f"Processing: {os.path.basename(file_path)}")
            print(f"Using FFmpeg: {self.ffmpeg_path}")
            print(f"Output folder: {self.output_folder}")
            
            if self.progress_callback:
                self.progress_callback("Getting video duration...", 10)
            
            duration = self._get_video_duration(file_path)
            if duration <= 0:
                print("Could not get video duration")
                return []
            
            print(f"Duration: {duration/60:.1f} minutes")

            if duration <= self.SEGMENT_LENGTH:
                print("Video is short - copying to remainder folder")
                
                if self.progress_callback:
                    self.progress_callback("Copying short video to remainder folder...", 50)
                
                output_path = self._copy_short_video(file_path, audio_only)
                
                if os.path.exists(output_path):
                    output_files.append(output_path)
                    processing_successful = True
                    
                    if self.progress_callback:
                        self.progress_callback("Short video copied successfully!", 100)
                    
                    print(f"Completed: {output_path}")
                else:
                    print("Failed to copy/convert short video")
                    return []

            else:
                print("Video is long - splitting...")
                num_segments = math.ceil(duration / self.SEGMENT_LENGTH)
                base_name = self._get_base_name(file_path)
                extension = ".mp3" if audio_only else ".mp4"
                successful_segments = 0

                for i in range(num_segments):
                    start_time = i * self.SEGMENT_LENGTH
                    segment_duration = min(self.SEGMENT_LENGTH, duration - start_time)
                    is_full = abs(segment_duration - self.SEGMENT_LENGTH) < 1

                    print(f"Creating segment {i+1}/{num_segments} ({start_time/60:.1f}-{(start_time+segment_duration)/60:.1f} min)")
                    
                    if self.progress_callback:
                        self.progress_callback(f"Processing segment {i+1}/{num_segments}", 
                                             (i / num_segments) * 100)
                    
                    output_path = self._get_output_path(base_name, i + 1, is_full, extension)
                    
                    print(f"Writing segment to: {output_path}")
                    print("Processing with FFmpeg...")
                    
                    success = self._split_video_ffmpeg(file_path, int(start_time), int(segment_duration), output_path, audio_only)
                    
                    if success and os.path.exists(output_path):
                        output_files.append(output_path)
                        successful_segments += 1
                        print(f"Completed segment {i+1}/{num_segments} in seconds (not minutes!)")
                    else:
                        print(f"Failed to create segment {i+1}")

                    if self.progress_callback:
                        progress = ((i + 1) / num_segments) * 100
                        self.progress_callback(f"FFmpeg completed segment {i+1}/{num_segments}", progress)

                processing_successful = (successful_segments == num_segments)
                
                if processing_successful:
                    print(f"Completed splitting into {num_segments} segments with FFmpeg!")
                    if self.progress_callback:
                        self.progress_callback("All segments completed with FFmpeg!", 100)
                else:
                    print(f"Only {successful_segments}/{num_segments} segments were successful")

            if processing_successful and delete_original:
                print(f"Processing successful! Cleaning up original file...")
                if self.progress_callback:
                    self.progress_callback("Cleaning up original file...", 100)
                
                self._delete_original_file(file_path)
                
            return output_files

        except Exception as e:
            print(f"Error processing {file_path}: {str(e)}")
            if self.progress_callback:
                self.progress_callback(f"Error: {str(e)}", -1)
            return []

    def process_files(self, file_paths: List[str], audio_only: bool = False, delete_originals: bool = True) -> List[str]:
        all_output_files = []
        total_files = len(file_paths)
        successful_files = 0
        
        print(f"\n=== Starting batch processing in output folder: {self.output_folder} ===")
        
        media_type = "audio files" if audio_only else "videos"
        if self.progress_callback:
            self.progress_callback(f"Starting processing of {total_files} {media_type}...", 0)
        
        for idx, file_path in enumerate(file_paths):
            file_num = idx + 1
            print(f"\n=== Processing file {file_num}/{total_files} with FFmpeg ===")
            
            if self.progress_callback:
                filename = os.path.basename(file_path)
                self.progress_callback(f"Processing {media_type[:-1]} {file_num}/{total_files}: {filename}", 0)
            
            output_files = self.process_video(file_path, audio_only, delete_originals)
            
            if output_files:
                all_output_files.extend(output_files)
                successful_files += 1
                
                if self.progress_callback:
                    filename = os.path.basename(file_path)
                    segments_created = len(output_files)
                    self.progress_callback(f"Completed {file_num}/{total_files}: {filename} ({segments_created} segments)", 100)
            else:
                if self.progress_callback:
                    filename = os.path.basename(file_path)
                    self.progress_callback(f"Failed {file_num}/{total_files}: {filename}", -1)
            
        if self.progress_callback:
            total_segments = len(all_output_files)
            if successful_files == total_files:
                self.progress_callback(f"All {successful_files} {media_type} processed successfully! Created {total_segments} segments.", 100)
            elif successful_files > 0:
                self.progress_callback(f"Processed {successful_files}/{total_files} {media_type}. Created {total_segments} segments.", 100)
            else:
                self.progress_callback(f"No {media_type} processed successfully", -1)
            
        if delete_originals and successful_files > 0:
            print(f"\nCleanup completed! Original files have been removed to save space.")
            
        print(f"\nAll files processed and saved to: {self.output_folder}")
        print(f"   45-minute segments: {self.min45_folder}")
        print(f"   Shorter segments: {self.remainder_folder}")
        print(f"   Total segments created: {len(all_output_files)}")
            
        return all_output_files
