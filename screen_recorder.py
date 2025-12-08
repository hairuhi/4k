import subprocess
import threading
import os
import re
import signal
import time

class ScreenRecorder:
    def __init__(self, ffmpeg_path="ffmpeg.exe"):
        self.ffmpeg_path = ffmpeg_path
        self.process = None
        self.is_recording = False
        self._stop_event = threading.Event()

    def get_audio_devices(self):
        """
        Parses ffmpeg -list_devices true -f dshow -i dummy output to find audio devices.
        """
        cmd = [self.ffmpeg_path, "-list_devices", "true", "-f", "dshow", "-i", "dummy"]
        try:
            # ffmpeg prints device list to stderr
            result = subprocess.run(cmd, stderr=subprocess.PIPE, stdout=subprocess.PIPE, text=True, encoding='utf-8', errors='replace')
            output = result.stderr
            
            devices = []
            # Regex to find devices. 
            # Pattern looks like:  [dshow @ ...]  "Microphone (Realtek Audio)"
            # followed by: [dshow @ ...]     Alternative name "@device_cm_{...}"
            
            # Simple parsing: look for lines with "DirectShow audio devices" and then grab quoted names until "DirectShow video devices" or end
            
            in_audio_section = False
            for line in output.splitlines():
                if "DirectShow audio devices" in line:
                    in_audio_section = True
                    continue
                if "DirectShow video devices" in line:
                    in_audio_section = False
                    continue
                
                if in_audio_section:
                    match = re.search(r'\"([^\"]+)\"', line)
                    if match:
                        device_name = match.group(1)
                        # Avoid duplicates or alternative names if possible (often appear as duplicates on separate lines)
                        if device_name not in devices and not device_name.startswith("@device_"):
                            devices.append(device_name)
            return devices
        except Exception as e:
            print(f"Error listing audio devices: {e}")
            return []

    def start_recording(self, output_path, resolution="1920x1080", frame_rate=30, audio_device=None):
        if self.is_recording:
            return False

        self._stop_event.clear()
        
        # Build command
        # ffmpeg -f gdigrab -framerate 30 -i desktop -c:v libx264 -preset ultrafast -pix_fmt yuv420p output.mp4
        
        # Scaling if necessary? for now let's just record desktop full size or use a specific region?
        # User said "screen capture", implying full screen usually.
        # -video_size can be used if we want to secure a specific resolution, but gdigrab 'desktop' grabs full screen.
        
        cmd = [
            self.ffmpeg_path,
            "-f", "gdigrab",
            "-framerate", str(frame_rate),
            "-i", "desktop",
            "-c:v", "libx264",
            "-preset", "ultrafast",
            "-pix_fmt", "yuv420p",
            "-y" # overwrite
        ]

        if audio_device:
            # -f dshow -i audio="name"
            cmd.extend(["-f", "dshow", "-i", f"audio={audio_device}"])
            # simple aac encoding
            cmd.extend(["-c:a", "aac"])

        cmd.append(output_path)

        def run_ffmpeg():
            self.is_recording = True
            # Creationflags to hide console window on Windows
            startupinfo = subprocess.STARTUPINFO()
            startupinfo.dwFlags |= subprocess.STARTF_USESHOWWINDOW
            
            try:
                self.process = subprocess.Popen(
                    cmd, 
                    stdin=subprocess.PIPE, 
                    stdout=subprocess.PIPE, 
                    stderr=subprocess.PIPE,
                    creationflags=subprocess.CREATE_NO_WINDOW if os.name == 'nt' else 0
                )
                
                # Wait until stop needed
                while not self._stop_event.is_set():
                    if self.process.poll() is not None:
                         # Process exited unexpectedly
                         break
                    time.sleep(0.5)
                
                # Stop recording
                if self.process.poll() is None:
                    # Send 'q' to stop gracefully
                    try:
                        self.process.communicate(input=b'q', timeout=5)
                    except subprocess.TimeoutError:
                        self.process.kill()
                
            except Exception as e:
                print(f"Recording error: {e}")
            finally:
                self.is_recording = False
                self.process = None

        self.thread = threading.Thread(target=run_ffmpeg, daemon=True)
        self.thread.start()
        return True

    def stop_recording(self):
        if self.is_recording:
            self._stop_event.set()
            # Wait for thread to join? or just let it finish
            # Better to wait a bit to ensure file is finalized
            return True
        return False
