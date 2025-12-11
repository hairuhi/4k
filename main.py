import customtkinter as ctk
from tkinter import filedialog, messagebox
import threading
import os
import sys
import requests
import subprocess
import time
from download_manager import DownloadManager
from config_manager import ConfigManager
from screen_recorder import ScreenRecorder

# 설정: 테마와 색상
ctk.set_appearance_mode("System")
ctk.set_default_color_theme("blue")

# --- Auto Update Configuration ---
CURRENT_VERSION = "1.2.0"
# IMPORTANT: User must update these URLs to their own repository
GITHUB_REPO_URL = "https://github.com/hairuhi/4k" 
VERSION_URL = f"{GITHUB_REPO_URL.replace('github.com', 'raw.githubusercontent.com')}/main/version.txt"
DOWNLOAD_URL = f"{GITHUB_REPO_URL}/releases/download/latest/Py4KDownloader.exe"

class DownloadItem(ctk.CTkFrame):
    def __init__(self, master, url, title="Processing...", **kwargs):
        super().__init__(master, **kwargs)
        self.url = url
        
        # Grid Layout
        self.grid_columnconfigure(1, weight=1)
        
        # Title
        self.title_label = ctk.CTkLabel(self, text=title, anchor="w", font=("Arial", 12, "bold"))
        self.title_label.grid(row=0, column=0, columnspan=2, padx=10, pady=(5, 0), sticky="ew")
        
        # URL (Small)
        self.url_label = ctk.CTkLabel(self, text=url, anchor="w", font=("Arial", 10), text_color="gray")
        self.url_label.grid(row=1, column=0, columnspan=2, padx=10, pady=(0, 5), sticky="ew")
        
        # Progress Bar
        self.progress_bar = ctk.CTkProgressBar(self)
        self.progress_bar.grid(row=2, column=0, columnspan=2, padx=10, pady=5, sticky="ew")
        self.progress_bar.set(0)
        
        # Status Label
        self.status_label = ctk.CTkLabel(self, text="대기 중...", anchor="w", font=("Arial", 11))
        self.status_label.grid(row=3, column=0, padx=10, pady=(0, 5), sticky="w")
        
        # Action Button (Open Folder) - Initially hidden
        self.open_btn = ctk.CTkButton(self, text="폴더 열기", width=80, height=24, command=self.open_folder, state="disabled")
        self.open_btn.grid(row=3, column=1, padx=10, pady=(0, 5), sticky="e")
        
        self.save_path = ""

    def update_progress(self, d):
        if d['status'] == 'downloading':
            p = d.get('_percent_str', '0%').replace('%','')
            try:
                self.progress_bar.set(float(p) / 100)
            except:
                pass
            
            status_text = f"{d.get('_percent_str')} | {d.get('_speed_str')} | ETA: {d.get('_eta_str')}"
            self.status_label.configure(text=status_text)
            
            # Update title if available and not set
            if self.title_label.cget("text") == "Processing..." and d.get('info_dict'):
                self.title_label.configure(text=d['info_dict'].get('title', 'Unknown Title'))

        elif d['status'] == 'finished':
            self.progress_bar.set(1)
            self.status_label.configure(text="변환/마무리 중...")

    def set_complete(self, result):
        if result['success']:
            self.status_label.configure(text="완료", text_color="green")
            self.progress_bar.set(1)
            self.open_btn.configure(state="normal")
            
            # Update title one last time from result info
            if result.get('info'):
                self.title_label.configure(text=result['info'].get('title', 'Unknown Title'))
        else:
            self.status_label.configure(text=f"오류: {result.get('error')}", text_color="red")
            self.progress_bar.configure(progress_color="red")

    def set_save_path(self, path):
        self.save_path = path

    def open_folder(self):
        if self.save_path and os.path.exists(self.save_path):
            os.startfile(self.save_path)

class App(ctk.CTk):
    def __init__(self):
        super().__init__()

        self.config_manager = ConfigManager()
        self.screen_recorder = ScreenRecorder()

        self.title(f"Py 4K Downloader Ultimate (v{CURRENT_VERSION})")
        self.geometry("900x700")

        self.download_manager = DownloadManager(max_workers=3)
        
        self.check_for_update_async()

        # Layout
        self.grid_columnconfigure(0, weight=1)
        self.grid_rowconfigure(1, weight=1) # Download list expands

        # --- Top Bar (Settings) ---
        self.top_frame = ctk.CTkFrame(self, fg_color="transparent")
        self.top_frame.grid(row=0, column=0, padx=20, pady=(10, 0), sticky="ew")
        
        self.settings_btn = ctk.CTkButton(self.top_frame, text="⚙ Settings", width=80, command=self.open_settings)
        self.settings_btn.pack(side="right")

        # --- Tab View ---
        self.tab_view = ctk.CTkTabview(self)
        self.tab_view.grid(row=1, column=0, padx=20, pady=10, sticky="ew")
        
        self.init_tabs()

        # --- Download List ---
        self.list_label = ctk.CTkLabel(self, text="다운로드/녹화 목록", font=("Arial", 14, "bold"))
        self.list_label.grid(row=2, column=0, padx=20, pady=(10, 0), sticky="w")

        self.scroll_frame = ctk.CTkScrollableFrame(self, label_text="진행 상황")
        self.scroll_frame.grid(row=3, column=0, padx=20, pady=10, sticky="nsew")
        self.scroll_frame.grid_columnconfigure(0, weight=1)

        self.download_items = []

    def init_tabs(self):
        # Define available modules (Name -> Function to setup)
        # We check config to see if they should be added
        
        available_tabs = {
            "YouTube": lambda t: self.setup_tab(t, "YouTube"),
            "YouTube Channel": lambda t: self.setup_channel_tab(t),
            "Udemy": lambda t: self.setup_tab(t, "Udemy", show_cookie_option=True),
            "FC2": lambda t: self.setup_tab(t, "FC2", show_cookie_option=True),
            "Pornhub": lambda t: self.setup_tab(t, "Pornhub", show_cookie_option=True),
            "OnlyFans": lambda t: self.setup_tab(t, "OnlyFans", show_cookie_option=True),
            "XFans": lambda t: self.setup_tab(t, "XFans", show_cookie_option=True),
            "ScreenRecorder": lambda t: self.setup_screen_recorder_tab(t)
        }

        for name, setup_func in available_tabs.items():
            if self.config_manager.get_module_status(name):
                tab = self.tab_view.add(name)
                setup_func(tab)

    def check_for_update_async(self):
        threading.Thread(target=self._check_update_thread, daemon=True).start()

    def _check_update_thread(self):
        if "YOUR_ID" in GITHUB_REPO_URL:
            # print("Update check skipped: Repo URL not set.")
            return

        try:
            # print(f"Checking update from: {VERSION_URL}")
            response = requests.get(VERSION_URL, timeout=5)
            if response.status_code == 200:
                latest_version = response.text.strip()
                if latest_version != CURRENT_VERSION:
                    self.after(0, lambda: self.prompt_update(latest_version))
        except Exception as e:
            print(f"Update check failed: {e}")

    def prompt_update(self, version):
        if messagebox.askyesno("업데이트 발견", f"새 버전({version})이 있습니다. 지금 업데이트하시겠습니까?"):
            threading.Thread(target=self.perform_update, daemon=True).start()

    def perform_update(self):
        try:
            new_exe = "Update_Py4KDownloader.exe"
            r = requests.get(DOWNLOAD_URL, stream=True)
            with open(new_exe, 'wb') as f:
                for chunk in r.iter_content(chunk_size=8192):
                    f.write(chunk)
            
            # Batch script to swap executables
            batch_script = f"""
@echo off
timeout /t 2 /nobreak
del "{sys.executable}"
rename "{new_exe}" "{os.path.basename(sys.executable)}"
start "" "{os.path.basename(sys.executable)}"
del "%~f0"
"""
            with open("updater.bat", "w") as f:
                f.write(batch_script)
            
            subprocess.Popen("updater.bat", shell=True)
            self.quit()
        except Exception as e:
            self.after(0, lambda: messagebox.showerror("업데이트 실패", str(e)))

    def setup_tab(self, tab, name, show_cookie_option=False):
        # URL Input
        url_label = ctk.CTkLabel(tab, text=f"{name} URL:")
        url_label.grid(row=0, column=0, padx=10, pady=10, sticky="w")
        
        url_entry = ctk.CTkEntry(tab, placeholder_text=f"{name} 링크를 입력하세요...", width=400)
        url_entry.grid(row=0, column=1, padx=10, pady=10, sticky="ew")
        
        # Settings Frame
        settings_frame = ctk.CTkFrame(tab)
        settings_frame.grid(row=1, column=0, columnspan=2, padx=10, pady=10, sticky="ew")
        
        # Type Selection
        type_var = ctk.StringVar(value="video")
        ctk.CTkRadioButton(settings_frame, text="Video", variable=type_var, value="video").grid(row=0, column=0, padx=10, pady=10)
        ctk.CTkRadioButton(settings_frame, text="Audio (MP3)", variable=type_var, value="audio").grid(row=0, column=1, padx=10, pady=10)
        
        # Resolution (Only for Video)
        res_option = ctk.CTkOptionMenu(settings_frame, values=["Best", "2160", "1440", "1080", "720", "480"])
        res_option.grid(row=0, column=2, padx=10, pady=10)
        
        # Subtitles
        sub_var = ctk.BooleanVar(value=False)
        ctk.CTkCheckBox(settings_frame, text="자막 (KO/EN)", variable=sub_var).grid(row=0, column=3, padx=10, pady=10)

        # Browser Cookies (Optional)
        cookie_var = ctk.BooleanVar(value=False)
        if show_cookie_option:
            ctk.CTkCheckBox(settings_frame, text="브라우저 쿠키 사용 (Chrome)", variable=cookie_var).grid(row=0, column=4, padx=10, pady=10)

        # Save Path
        path_entry = ctk.CTkEntry(settings_frame, placeholder_text="저장 경로")
        path_entry.insert(0, os.path.join(os.getcwd(), "downloads"))
        path_entry.grid(row=1, column=0, columnspan=3 if not show_cookie_option else 4, padx=10, pady=10, sticky="ew")
        
        browse_btn = ctk.CTkButton(settings_frame, text="...", width=30, command=lambda: self.browse_path(path_entry))
        browse_btn.grid(row=1, column=3 if not show_cookie_option else 4, padx=10, pady=10)

        # Download Button
        download_btn = ctk.CTkButton(tab, text="다운로드 추가", 
                                     command=lambda: self.add_download(url_entry, type_var, res_option, sub_var, cookie_var, path_entry))
        download_btn.grid(row=2, column=0, columnspan=2, padx=10, pady=10, sticky="ew")

        # Configure Grid
        tab.grid_columnconfigure(1, weight=1)

    def setup_screen_recorder_tab(self, tab):
        # Instructions
        info_label = ctk.CTkLabel(tab, text="화면 녹화 (전체 화면)", font=("Arial", 12))
        info_label.grid(row=0, column=0, columnspan=2, padx=10, pady=(10,0))

        # Settings
        settings_frame = ctk.CTkFrame(tab)
        settings_frame.grid(row=1, column=0, columnspan=2, padx=10, pady=10, sticky="ew")

        # Path
        path_entry = ctk.CTkEntry(settings_frame, placeholder_text="저장 경로")
        path_entry.insert(0, os.path.join(os.getcwd(), "downloads"))
        path_entry.grid(row=0, column=0, padx=10, pady=10, sticky="ew")
        
        browse_btn = ctk.CTkButton(settings_frame, text="...", width=30, command=lambda: self.browse_path(path_entry))
        browse_btn.grid(row=0, column=1, padx=10, pady=10)

        # Audio Option Display
        sr_config = self.config_manager.get_screen_recorder_config()
        audio_status_text = "음성 녹음 켜짐" if sr_config.get("audio_enabled") else "음성 녹음 꺼짐 (설정에서 변경 가능)"
        audio_label = ctk.CTkLabel(settings_frame, text=audio_status_text, text_color="gray" if not sr_config.get("audio_enabled") else "green")
        audio_label.grid(row=1, column=0, columnspan=2, pady=(0, 10))

        # Controls
        self.record_btn = ctk.CTkButton(tab, text="녹화 시작", command=lambda: self.toggle_recording(path_entry), fg_color="red", hover_color="darkred")
        self.record_btn.grid(row=2, column=0, columnspan=2, padx=10, pady=10)
        
        self.record_status = ctk.CTkLabel(tab, text="대기 중", font=("Arial", 14, "bold"))
        self.record_status.grid(row=3, column=0, columnspan=2, pady=10)

        tab.grid_columnconfigure(0, weight=1)

    def toggle_recording(self, path_entry):
        if self.screen_recorder.is_recording:
            # Stop
            self.screen_recorder.stop_recording()
            self.record_btn.configure(text="녹화 시작", fg_color="red", hover_color="darkred")
            self.record_status.configure(text="녹화 저장 중...", text_color="orange")
            
            # Wait for save (simple polling)
            self.after(1000, lambda: self.check_recording_saved())
        else:
            # Start
            save_dir = path_entry.get()
            if not os.path.exists(save_dir):
                os.makedirs(save_dir, exist_ok=True)
            
            filename = f"ScreenRecord_{int(time.time())}.mp4"
            filepath = os.path.join(save_dir, filename)
            
            sr_config = self.config_manager.get_screen_recorder_config()
            audio_device = self.screen_recorder.get_audio_devices()[0] if sr_config.get("audio_enabled") and self.screen_recorder.get_audio_devices() else None
            
            success = self.screen_recorder.start_recording(filepath, audio_device=audio_device)
            if success:
                self.record_btn.configure(text="녹화 중지 (Stop)", fg_color="gray", hover_color="gray")
                self.record_status.configure(text="녹화 중... (Stop하려면 버튼 클릭)", text_color="red")
            else:
                messagebox.showerror("Error", "녹화를 시작할 수 없습니다.")

    def check_recording_saved(self):
        if not self.screen_recorder.is_recording:
            self.record_status.configure(text="녹화 완료", text_color="green")
            # Maybe add to list?
            # Creating a dummy item for the list to show it finished
        else:
            self.after(1000, self.check_recording_saved)

    def setup_channel_tab(self, tab):
        # Channel URL Input
        url_label = ctk.CTkLabel(tab, text="채널/재생목록 URL:")
        url_label.grid(row=0, column=0, padx=10, pady=10, sticky="w")
        
        url_entry = ctk.CTkEntry(tab, placeholder_text="채널 또는 재생목록 링크...", width=350)
        url_entry.grid(row=0, column=1, padx=10, pady=10, sticky="ew")

        # Range Settings (Batch)
        range_frame = ctk.CTkFrame(tab, fg_color="transparent")
        range_frame.grid(row=1, column=0, columnspan=2, padx=10, pady=0, sticky="w")

        ctk.CTkLabel(range_frame, text="시작 번호:").pack(side="left", padx=(0, 5))
        start_entry = ctk.CTkEntry(range_frame, width=50)
        start_entry.insert(0, "1")
        start_entry.pack(side="left", padx=5)

        ctk.CTkLabel(range_frame, text="가져올 개수 (Batch):").pack(side="left", padx=5)
        count_entry = ctk.CTkEntry(range_frame, width=50)
        count_entry.insert(0, "10")
        count_entry.pack(side="left", padx=5)
        
        # Settings Frame (Reuse similar options)
        settings_frame = ctk.CTkFrame(tab)
        settings_frame.grid(row=2, column=0, columnspan=2, padx=10, pady=10, sticky="ew")
        
        type_var = ctk.StringVar(value="video")
        ctk.CTkRadioButton(settings_frame, text="Video", variable=type_var, value="video").grid(row=0, column=0, padx=10, pady=10)
        ctk.CTkRadioButton(settings_frame, text="Audio", variable=type_var, value="audio").grid(row=0, column=1, padx=10, pady=10)
        
        res_option = ctk.CTkOptionMenu(settings_frame, values=["Best", "2160", "1440", "1080", "720", "480"])
        res_option.grid(row=0, column=2, padx=10, pady=10)
        
        sub_var = ctk.BooleanVar(value=False)
        ctk.CTkCheckBox(settings_frame, text="자막", variable=sub_var).grid(row=0, column=3, padx=10, pady=10)

        # Skip Duplicates (Visual only, enforced by yt-dlp checks usually, but we can display it)
        # Actually logic will handle it by just queuing them.
        
        path_entry = ctk.CTkEntry(settings_frame, placeholder_text="저장 경로")
        path_entry.insert(0, os.path.join(os.getcwd(), "downloads"))
        path_entry.grid(row=1, column=0, columnspan=3, padx=10, pady=10, sticky="ew")
        
        browse_btn = ctk.CTkButton(settings_frame, text="...", width=30, command=lambda: self.browse_path(path_entry))
        browse_btn.grid(row=1, column=3, padx=10, pady=10)

        # Action Button
        fetch_btn = ctk.CTkButton(tab, text="목록 가져오기 및 다운로드 (Fetch & Download)", 
                                  command=lambda: self.process_channel_download(url_entry, start_entry, count_entry, type_var, res_option, sub_var, path_entry))
        fetch_btn.grid(row=3, column=0, columnspan=2, padx=10, pady=10, sticky="ew")
        
        tab.grid_columnconfigure(1, weight=1)

    def process_channel_download(self, url_entry, start_entry, count_entry, type_var, res_option, sub_var, path_entry):
        url = url_entry.get()
        if not url:
            messagebox.showerror("Error", "URL을 입력해주세요.")
            return

        try:
            start_idx = int(start_entry.get())
            count = int(count_entry.get())
            if start_idx < 1 or count < 1:
                raise ValueError
        except:
            messagebox.showerror("Error", "시작 번호와 개수는 1 이상의 정수여야 합니다.")
            return

        # Disable button? (Not implemented for simplicity, but good practice)
        
        # Prepare options
        res_val = res_option.get()
        resolution = None if res_val == "Best" else res_val
        options = {
            'save_path': path_entry.get(),
            'type': type_var.get(),
            'resolution': resolution,
            'subtitles': sub_var.get(),
            'cookies_browser': False # Channel download usually public
        }
        
        threading.Thread(target=self._fetch_channel_thread, args=(url, start_idx, count, options), daemon=True).start()

    def _fetch_channel_thread(self, url, start, count, options):
        # Using the core directly safely since it's just fetching info
        # Calculate end index
        end = start + count - 1
        
        # Assuming download_manager has access to downloader core
        # Or creating a temporary core instance
        from core import DownloaderCore
        temp_core = DownloaderCore()
        
        entries = temp_core.get_channel_videos(url, start=start, end=end)
        
        if not entries:
            self.after(0, lambda: messagebox.showinfo("Info", "영상을 찾을 수 없거나 목록 끝입니다."))
            return

        for entry in entries:
            vid_url = entry.get('url') or entry.get('webpage_url')
            # If entry has id, construct url
            if not vid_url and entry.get('id'):
                vid_url = f"https://www.youtube.com/watch?v={entry.get('id')}"
            
            if vid_url:
                title = entry.get('title', 'Unknown Title')
                # Add to download list safely on main thread
                self.after(0, lambda u=vid_url, t=title: self._add_download_task(u, options, title=t))
        
        self.after(0, lambda: messagebox.showinfo("완료", f"{len(entries)}개의 영상을 대기열에 추가했습니다."))

    def open_settings(self):
        toplevel = ctk.CTkToplevel(self)
        toplevel.title("설정 (Settings)")
        toplevel.geometry("400x500")
        toplevel.transient(self) # stays on top of main window

        ctk.CTkLabel(toplevel, text="기능 켜기/끄기 (재시작 필요)", font=("Arial", 14, "bold")).pack(pady=10)

        modules_frame = ctk.CTkScrollableFrame(toplevel, height=200)
        modules_frame.pack(fill="x", padx=10, pady=5)

        # Module Toggles
        self.module_vars = {}
        # Module Toggles
        self.module_vars = {}
        for mod_name in ["YouTube", "YouTube Channel", "Udemy", "FC2", "Pornhub", "OnlyFans", "XFans", "ScreenRecorder"]:
            var = ctk.BooleanVar(value=self.config_manager.get_module_status(mod_name))
            chk = ctk.CTkCheckBox(modules_frame, text=mod_name, variable=var)
            chk.pack(anchor="w", padx=5, pady=5)
            self.module_vars[mod_name] = var

        ctk.CTkLabel(toplevel, text="녹화 설정", font=("Arial", 14, "bold")).pack(pady=(20, 10))
        
        # Audio Toggle
        sr_config = self.config_manager.get_screen_recorder_config()
        self.audio_var = ctk.BooleanVar(value=sr_config.get("audio_enabled", False))
        ctk.CTkCheckBox(toplevel, text="화면 녹화 시 오디오 포함 (실험적)", variable=self.audio_var).pack(pady=5)

        # Save Button
        ctk.CTkButton(toplevel, text="저장 및 적용", command=lambda: self.save_settings(toplevel)).pack(pady=20, fill="x", padx=20)

    def save_settings(self, toplevel):
        # Save Modules
        for mod, var in self.module_vars.items():
            self.config_manager.config["modules"][mod] = var.get()
        
        # Save Screen Recorder Config
        self.config_manager.config.setdefault("screen_recorder", {})["audio_enabled"] = self.audio_var.get()
        
        self.config_manager.save_config()
        messagebox.showinfo("저장 완료", "설정이 저장되었습니다.\n변경 사항을 적용하려면 프로그램을 재시작하세요.")
        toplevel.destroy()

    def browse_path(self, entry_widget):
        path = filedialog.askdirectory()
        if path:
            entry_widget.delete(0, "end")
            entry_widget.insert(0, path)

    def add_download(self, url_entry, type_var, res_option, sub_var, cookie_var, path_entry):
        url = url_entry.get()
        if not url:
            messagebox.showerror("Error", "URL을 입력해주세요.")
            return
        
        save_path = path_entry.get()
        if not os.path.exists(save_path):
            try:
                os.makedirs(save_path)
            except:
                pass

        # Prepare Options
        res_val = res_option.get()
        resolution = None if res_val == "Best" else res_val
        
        options = {
            'save_path': save_path,
            'type': type_var.get(),
            'resolution': resolution,
            'subtitles': sub_var.get(),
            'cookies_browser': cookie_var.get()
        }

        self._add_download_task(url, options)
        
        # Clear Input
        url_entry.delete(0, "end")

    def _add_download_task(self, url, options, title="Processing..."):
        # Create UI Item
        item = DownloadItem(self.scroll_frame, url=url, title=title)
        
        # Newest on top
        if self.download_items:
            item.pack(fill="x", padx=5, pady=5, before=self.download_items[0])
        else:
            item.pack(fill="x", padx=5, pady=5)
            
        self.download_items.insert(0, item)
        item.set_save_path(options.get('save_path'))

        # Submit to Manager
        self.download_manager.submit_download(
            url, 
            options, 
            progress_callback=lambda d: self.after(0, item.update_progress, d),
            completion_callback=lambda r: self.after(0, item.set_complete, r)
        )

if __name__ == "__main__":
    app = App()
    app.mainloop()
