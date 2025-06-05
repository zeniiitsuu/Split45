import customtkinter as ctk
import tkinter as tk
from tkinter import filedialog
import threading
import queue
import time
import json
from datetime import datetime, timedelta
from downloader import VideoDownloader
from processor import MediaProcessor
import os

class App(ctk.CTk):
    def __init__(self):
        super().__init__()
        self.title("Split45")
        self.geometry("800x650")
        ctk.set_appearance_mode("dark")
        ctk.set_default_color_theme("blue")
        self.settings_file = os.path.join(os.path.dirname(__file__), "settings.json")
        self.output_folder = self.load_output_folder()
        self.download_queue = queue.Queue()
        self.processing_active = False
        self.download_stats = {"current": 0, "total": 0, "completed": 0}
        self.processing_stats = {"current": 0, "completed": 0, "total_segments": 0}
        self.start_time = None
        self.download_start_time = None
        self.processing_start_time = None
        self.estimated_time = None
        self.timer_running = False
        self.setup_output_folder_selection()
        self.tabview = ctk.CTkTabview(self)
        self.tabview.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)
        self.download_tab = self.tabview.add("Download")
        self.setup_download_tab()
        self.process_tab = self.tabview.add("Process")
        self.setup_process_tab()
        self.update_processors()

    def load_output_folder(self):
        try:
            if os.path.exists(self.settings_file):
                with open(self.settings_file, 'r') as f:
                    settings = json.load(f)
                    saved_folder = settings.get('output_folder', os.getcwd())
                    if os.path.exists(saved_folder):
                        print(f"📁 Loaded saved output folder: {saved_folder}")
                        return saved_folder
                    else:
                        print(f"⚠️ Saved folder no longer exists: {saved_folder}")
        except Exception as e:
            print(f"Error loading settings: {e}")
        return os.getcwd()

    def save_output_folder(self):
        try:
            settings = {'output_folder': self.output_folder}
            with open(self.settings_file, 'w') as f:
                json.dump(settings, f, indent=2)
            print(f"💾 Saved output folder setting: {self.output_folder}")
        except Exception as e:
            print(f"Error saving settings: {e}")

    def estimate_time(self, video_count, audio_only=False, pipeline=False):
        download_time_per_video = 25 if audio_only else 35
        processing_time_per_video = 10 if audio_only else 15
        if pipeline:
            total_download_time = video_count * download_time_per_video
            total_processing_time = video_count * processing_time_per_video
            estimated_seconds = max(total_download_time, total_processing_time) + (video_count * 2)
        else:
            estimated_seconds = (video_count * download_time_per_video) + (video_count * processing_time_per_video)
        return estimated_seconds

    def format_duration(self, seconds):
        if seconds < 60:
            return f"{int(seconds)} seconds"
        elif seconds < 3600:
            minutes = int(seconds // 60)
            remaining_seconds = int(seconds % 60)
            if remaining_seconds > 0:
                return f"{minutes}m {remaining_seconds}s"
            else:
                return f"{minutes} minutes"
        else:
            hours = int(seconds // 3600)
            minutes = int((seconds % 3600) // 60)
            return f"{hours}h {minutes}m"

    def get_elapsed_time(self, start_time):
        if start_time:
            return time.time() - start_time
        return 0

    def setup_output_folder_selection(self):
        folder_frame = ctk.CTkFrame(self)
        folder_frame.pack(fill=tk.X, padx=10, pady=5)
        folder_label = ctk.CTkLabel(folder_frame, text="Output Folder:")
        folder_label.pack(side=tk.LEFT, padx=10, pady=10)
        self.folder_path_label = ctk.CTkLabel(
            folder_frame,
            text=self.output_folder,
            fg_color=("gray75", "gray25"),
            corner_radius=5
        )
        self.folder_path_label.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=5, pady=10)
        self.browse_button = ctk.CTkButton(
            folder_frame,
            text="Browse",
            width=80,
            command=self.select_output_folder
        )
        self.browse_button.pack(side=tk.RIGHT, padx=10, pady=10)

    def select_output_folder(self):
        folder = filedialog.askdirectory(
            title="Select Output Folder",
            initialdir=self.output_folder
        )
        if folder:
            self.output_folder = folder
            display_path = folder
            if len(display_path) > 60:
                display_path = "..." + display_path[-57:]
            self.folder_path_label.configure(text=display_path)
            self.save_output_folder()
            self.update_processors()
            print(f"Output folder changed to: {folder}")

    def update_processors(self):
        self.downloader = VideoDownloader(self.update_download_progress, self.output_folder)
        self.processor = MediaProcessor(self.update_processing_progress, self.output_folder)

    def setup_download_tab(self):
        url_frame = ctk.CTkFrame(self.download_tab)
        url_frame.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)
        url_label = ctk.CTkLabel(url_frame, text="Enter YouTube URLs (one per line, max 10):")
        url_label.pack(padx=10, pady=5)
        self.url_text = ctk.CTkTextbox(url_frame, height=200)
        self.url_text.pack(fill=tk.BOTH, expand=True, padx=10, pady=5)
        self.download_format = ctk.CTkSegmentedButton(
            url_frame,
            values=["MP4 (Lowest Quality)", "MP3"],
            command=self.format_changed
        )
        self.download_format.pack(padx=10, pady=10)
        self.download_format.set("MP4 (Lowest Quality)")
        self.process_together_var = ctk.BooleanVar()
        self.process_together_checkbox = ctk.CTkCheckBox(
            url_frame,
            text="Process together (pipeline: process while downloading for faster completion)",
            variable=self.process_together_var
        )
        self.process_together_checkbox.pack(padx=10, pady=5)
        self.download_button = ctk.CTkButton(
            url_frame,
            text="Download",
            command=self.start_download
        )
        self.download_button.pack(padx=10, pady=10)
        self.download_progress_frame = ctk.CTkFrame(url_frame)
        download_header_frame = ctk.CTkFrame(self.download_progress_frame, fg_color="transparent")
        download_header_frame.pack(fill=tk.X, padx=10, pady=(5,0))
        download_label = ctk.CTkLabel(download_header_frame, text="Download Progress:")
        download_label.pack(side=tk.LEFT)
        self.download_time_label = ctk.CTkLabel(
            download_header_frame,
            text="",
            text_color=("gray50", "gray60"),
            font=("", 11)
        )
        self.download_time_label.pack(side=tk.RIGHT)
        self.download_progress = ctk.CTkProgressBar(self.download_progress_frame)
        self.download_progress.pack(fill=tk.X, padx=10, pady=2)
        self.download_progress.set(0)
        self.download_status = ctk.CTkLabel(self.download_progress_frame, text="")
        self.download_status.pack(anchor="w", padx=10, pady=2)
        processing_header_frame = ctk.CTkFrame(self.download_progress_frame, fg_color="transparent")
        self.processing_label = ctk.CTkLabel(processing_header_frame, text="Processing Progress:")
        self.processing_label.pack(side=tk.LEFT)
        self.processing_time_label = ctk.CTkLabel(
            processing_header_frame,
            text="",
            text_color=("gray50", "gray60"),
            font=("", 11)
        )
        self.processing_time_label.pack(side=tk.RIGHT)
        self.processing_progress = ctk.CTkProgressBar(self.download_progress_frame)
        self.processing_status = ctk.CTkLabel(self.download_progress_frame, text="")
        self.processing_header_frame = processing_header_frame
        self.download_progress_frame.pack_forget()
        self.processing_header_frame.pack_forget()
        self.processing_progress.pack_forget()
        self.processing_status.pack_forget()

    def setup_process_tab(self):
        process_frame = ctk.CTkFrame(self.process_tab)
        process_frame.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)
        select_button = ctk.CTkButton(
            process_frame,
            text="Select Files",
            command=self.select_files
        )
        select_button.pack(padx=10, pady=10)
        self.selected_files_text = ctk.CTkTextbox(process_frame, height=100)
        self.selected_files_text.pack(fill=tk.BOTH, expand=True, padx=10, pady=5)
        self.output_format = ctk.CTkSegmentedButton(
            process_frame,
            values=["Keep Original", "Convert to MP3"],
            command=self.format_changed
        )
        self.output_format.pack(padx=10, pady=10)
        self.output_format.set("Keep Original")
        self.process_button = ctk.CTkButton(
            process_frame,
            text="Process Files",
            command=self.start_processing
        )
        self.process_button.pack(padx=10, pady=10)
        self.process_progress_frame = ctk.CTkFrame(process_frame)
        self.process_progress_frame.pack(fill=tk.X, padx=10, pady=5)
        self.process_progress = ctk.CTkProgressBar(self.process_progress_frame)
        self.process_progress.pack(fill=tk.X, padx=10, pady=5)
        self.process_progress.set(0)
        self.process_status = ctk.CTkLabel(self.process_progress_frame, text="")
        self.process_status.pack(padx=10, pady=5)

    def format_changed(self, value):
        pass

    def update_download_progress(self, message, progress):
        """Update download progress and stats"""
        def update():
            self.download_progress_frame.pack(fill=tk.X, padx=10, pady=5)
            
            clean_message = message
            if "(elapsed:" in clean_message:
                clean_message = clean_message.split(" (elapsed:")[0]
            if "estimated time:" in clean_message:
                clean_message = clean_message.split(" - estimated time:")[0]
            
            self.download_status.configure(text=clean_message)
            if progress >= 0:
                self.download_progress.set(progress / 100)

        self.after(10, update)

    def update_processing_progress(self, message, progress):
        """Update processing progress and stats"""
        def update():
            if self.processing_active:
                self.download_progress_frame.pack(fill=tk.X, padx=10, pady=5)
                
                self.processing_header_frame.pack(fill=tk.X, padx=10, pady=(10,0))
                self.processing_progress.pack(fill=tk.X, padx=10, pady=2)
                self.processing_status.pack(anchor="w", padx=10, pady=(2,5))
            
            clean_message = message
            if "(elapsed:" in clean_message:
                clean_message = clean_message.split(" (elapsed:")[0]
                
            self.processing_status.configure(text=clean_message)
            if progress >= 0:
                self.processing_progress.set(progress / 100)

        self.after(10, update)

    def update_progress(self, filename, progress):
        """Legacy progress callback for single operations"""
        def update():
            if progress < 0:
                status_text = f"Error: {filename}"
                progress_value = 0
            else:
                if "segment" in str(filename).lower() or "copying" in str(filename).lower() or "completed" in str(filename).lower():
                    status_text = str(filename)
                else:
                    status_text = f"Processing {os.path.basename(filename)}: {progress:.1f}%"
                progress_value = progress / 100

            if self.tabview.get() == "Download":
                self.download_progress_frame.pack(fill=tk.X, padx=10, pady=5)
                self.download_status.configure(text=status_text)
                self.download_progress.set(progress_value)
            else:
                self.process_status.configure(text=status_text)
                self.process_progress.set(progress_value)

        self.after(10, update)

    def select_files(self):
        files = filedialog.askopenfilenames(
            title="Select files to process",
            filetypes=[("Media files", "*.mp4 *.mp3")]
        )
        self.selected_files_text.delete("1.0", tk.END)
        self.selected_files_text.insert("1.0", "\n".join(files))

    def start_download(self):
        urls = self.url_text.get("1.0", tk.END).strip().split("\n")
        urls = [url.strip() for url in urls if url.strip()]
        
        if len(urls) > 10:
            self.download_status.configure(text="Maximum 10 URLs allowed")
            return
        
        if not urls:
            self.download_status.configure(text="Please enter at least one URL")
            return

        self.download_button.configure(state="disabled")
        audio_only = self.download_format.get() == "MP3"
        process_together = self.process_together_var.get()
        
        self.download_stats = {"current": 0, "total": len(urls), "completed": 0}
        self.processing_stats = {"current": 0, "completed": 0, "total_segments": 0}
        self.processing_active = process_together
        self.start_time = time.time()
        
        self.estimated_time = self.estimate_time(len(urls), audio_only, process_together)
        self.start_time_updater()
        
        media_type = "audio files" if audio_only else "videos"
        mode = "pipeline" if process_together else "sequential"
        
        self.download_status.configure(
            text=f"⏱️ Starting {mode} processing of {len(urls)} {media_type} - estimated time: {self.format_duration(self.estimated_time)}"
        )
        
        if process_together:
            self.start_pipeline(urls, audio_only)
        else:
            thread = threading.Thread(
                target=self.download_thread,
                args=(urls, audio_only, False)
            )
            thread.start()

    def start_pipeline(self, urls, audio_only):
        """Start the concurrent download-process pipeline"""
        print("🚀 Starting pipeline mode: download + process concurrently")
        
        while not self.download_queue.empty():
            try:
                self.download_queue.get_nowait()
            except queue.Empty:
                break
        
        download_thread = threading.Thread(
            target=self.pipeline_download_thread,
            args=(urls, audio_only)
        )
        download_thread.start()
        
        processing_thread = threading.Thread(
            target=self.pipeline_processing_thread,
            args=(audio_only,)
        )
        processing_thread.start()

    def pipeline_download_thread(self, urls, audio_only):
        """Download files and queue them for processing"""
        try:
            self.download_start_time = time.time()
            media_type = "audio files" if audio_only else "videos"
            
            for idx, url in enumerate(urls):
                self.download_stats["current"] = idx + 1
                
                try:
                    self.update_download_progress(
                        f"⬇️ Downloading {idx + 1}/{len(urls)}: {media_type[:-1]}", 0
                    )
                    
                    downloaded_files = self.downloader.download_videos([url], audio_only)
                    
                    if downloaded_files:
                        self.download_stats["completed"] += 1
                        
                        self.download_queue.put({
                            'file': downloaded_files[0],
                            'audio_only': audio_only,
                            'index': idx + 1,
                            'total': len(urls)
                        })
                        
                        self.update_download_progress(
                            f"✅ Downloaded {idx + 1}/{len(urls)} - queued for processing", 
                            ((idx + 1) / len(urls)) * 100
                        )
                    else:
                        self.update_download_progress(f"❌ Failed {idx + 1}/{len(urls)}", -1)
                        
                except Exception as e:
                    print(f"Error downloading {url}: {e}")
                    self.update_download_progress(f"❌ Error {idx + 1}/{len(urls)}: {str(e)}", -1)
            
            self.download_queue.put(None)
            
            completed = self.download_stats["completed"]
            total = len(urls)
            
            if completed == total:
                self.update_download_progress(
                    f"🎉 All {completed} {media_type} downloaded! Processing in progress...", 100
                )
            else:
                self.update_download_progress(
                    f"Downloaded {completed}/{total} {media_type}. Processing in progress...", 100
                )
                
        except Exception as e:
            print(f"Pipeline download error: {e}")
            self.update_download_progress(f"❌ Download error: {str(e)}", -1)
            self.download_queue.put(None)

    def pipeline_processing_thread(self, audio_only):
        """Process files from the download queue"""
        processed_files = []
        total_segments = 0
        self.processing_start_time = time.time()
        
        try:
            while True:
                item = self.download_queue.get()
                
                if item is None:
                    break
                
                file_path = item['file']
                file_index = item['index']
                file_total = item['total']
                
                self.processing_stats["current"] = file_index
                
                try:
                    self.update_processing_progress(
                        f"⚙️ Processing {file_index}/{file_total}: {os.path.basename(file_path)}", 0
                    )
                    
                    segments = self.processor.process_video(file_path, audio_only, delete_original=True)
                    
                    if segments:
                        processed_files.extend(segments)
                        total_segments += len(segments)
                        self.processing_stats["completed"] += 1
                        self.processing_stats["total_segments"] = total_segments
                        
                        self.update_processing_progress(
                            f"✅ Processed {file_index}/{file_total}: {len(segments)} segments created", 100
                        )
                    else:
                        self.update_processing_progress(f"❌ Failed processing {file_index}/{file_total}", -1)
                        
                except Exception as e:
                    print(f"Error processing {file_path}: {e}")
                    self.update_processing_progress(f"❌ Error processing {file_index}/{file_total}: {str(e)}", -1)
                
                self.download_queue.task_done()
            
            total_time = self.get_elapsed_time(self.start_time)
            completed_downloads = self.download_stats["completed"]
            completed_processing = self.processing_stats["completed"]
            media_type = "audio files" if audio_only else "videos"
            
            if completed_processing > 0:
                self.update_processing_progress(
                    f"🎉 Pipeline complete! Processed {completed_processing} {media_type}, created {total_segments} segments", 100
                )
                
                self.update_download_progress(
                    f"🚀 Pipeline finished! {completed_downloads} downloaded, {completed_processing} processed, {total_segments} segments created", 100
                )
            else:
                self.update_processing_progress("❌ No files processed successfully", -1)
                
        except Exception as e:
            print(f"Pipeline processing error: {e}")
            self.update_processing_progress(f"❌ Processing error: {str(e)}", -1)
        finally:
            self.processing_active = False
            self.stop_time_updater()
            self.after(10, lambda: self.download_button.configure(state="normal"))

    def download_thread(self, urls, audio_only, process_together):
        """Traditional sequential download thread"""
        try:
            self.after(10, lambda: self.download_status.configure(text="Starting downloads..."))
            downloaded_files = self.downloader.download_videos(urls, audio_only)
            
            if downloaded_files:
                media_type = "audio files" if audio_only else "videos"
                elapsed = self.get_elapsed_time(self.start_time)
                
                if process_together:
                    self.after(10, lambda: self.download_status.configure(
                        text=f"Downloaded {len(downloaded_files)} {media_type} in {self.format_duration(elapsed)}. Starting processing..."
                    ))
                    processed_segments = self.processor.process_files(downloaded_files, audio_only, delete_originals=True)
                    
                    total_time = self.get_elapsed_time(self.start_time)
                    if processed_segments:
                        self.after(10, lambda: self.download_status.configure(
                            text=f"🎉 Complete in {self.format_duration(total_time)}! Downloaded {len(downloaded_files)} {media_type}, created {len(processed_segments)} segments!"
                        ))
                    else:
                        self.after(10, lambda: self.download_status.configure(text="Downloaded but processing failed"))
                else:
                    self.after(10, lambda: self.download_status.configure(
                        text=f"🎉 Downloaded {len(downloaded_files)} {media_type} successfully in {self.format_duration(elapsed)}!"
                    ))
            else:
                elapsed = self.get_elapsed_time(self.start_time)
                self.after(10, lambda: self.download_status.configure(text=f"❌ No files were downloaded (took {self.format_duration(elapsed)})"))
                
        except Exception as e:
            elapsed = self.get_elapsed_time(self.start_time)
            self.after(10, lambda: self.download_status.configure(text=f"❌ Error after {self.format_duration(elapsed)}: {str(e)}"))
        finally:
            self.stop_time_updater()
            self.after(10, lambda: self.download_button.configure(state="normal"))

    def start_processing(self):
        files = self.selected_files_text.get("1.0", tk.END).strip().split("\n")
        files = [f for f in files if f.strip()]
        
        if not files:
            self.process_status.configure(text="Please select files to process")
            return

        self.process_button.configure(state="disabled")
        audio_only = self.output_format.get() == "Convert to MP3"
        
        self.start_time = time.time()
        self.estimated_time = len(files) * 15
        self.start_time_updater()
        
        media_type = "audio files" if audio_only else "videos"
        
        self.process_status.configure(
            text=f"⏱️ Starting processing of {len(files)} {media_type} - estimated time: {self.format_duration(self.estimated_time)}"
        )
        
        thread = threading.Thread(
            target=self.process_thread,
            args=(files, audio_only)
        )
        thread.start()

    def process_thread(self, files, audio_only):
        try:
            delete_originals = any("downloads" in f.lower() for f in files)
            processed_segments = self.processor.process_files(files, audio_only, delete_originals=delete_originals)
            
            total_time = self.get_elapsed_time(self.start_time)
            media_type = "audio files" if audio_only else "videos"
            
            if processed_segments:
                if delete_originals:
                    self.after(10, lambda: self.process_status.configure(
                        text=f"🎉 Processed {len(files)} {media_type} in {self.format_duration(total_time)}, created {len(processed_segments)} segments with cleanup!"
                    ))
                else:
                    self.after(10, lambda: self.process_status.configure(
                        text=f"🎉 Processed {len(files)} {media_type} in {self.format_duration(total_time)}, created {len(processed_segments)} segments!"
                    ))
            else:
                self.after(10, lambda: self.process_status.configure(text=f"❌ Processing failed after {self.format_duration(total_time)}"))
        finally:
            self.stop_time_updater()
            self.after(10, lambda: self.process_button.configure(state="normal"))

    def start_time_updater(self):
        """Start continuous time updates every second"""
        if not self.timer_running:
            self.timer_running = True
            self.update_time_displays()

    def stop_time_updater(self):
        """Stop continuous time updates"""
        self.timer_running = False

    def update_time_displays(self):
        """Update time displays every second"""
        if self.timer_running and self.start_time:
            elapsed = self.get_elapsed_time(self.start_time)
            
            if hasattr(self, 'download_time_label'):
                if self.estimated_time and elapsed < 5:
                    self.download_time_label.configure(text=f"Est: {self.format_duration(self.estimated_time)}")
                else:
                    self.download_time_label.configure(text=f"Elapsed: {self.format_duration(elapsed)}")
            
            if self.processing_active and hasattr(self, 'processing_time_label'):
                self.processing_time_label.configure(text=f"Elapsed: {self.format_duration(elapsed)}")
        
        if self.timer_running:
            self.after(1000, self.update_time_displays)

if __name__ == "__main__":
    app = App()
    app.mainloop() 