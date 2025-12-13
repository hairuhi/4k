import json
import os

CONFIG_FILE = "config.json"

DEFAULT_CONFIG = {
    "modules": {
        "YouTube": True,
        "YouTube Channel": True,
        "FC2": True,
        "Pornhub": True,
        "OnlyFans": True,
        "XFans": True,
        "ScreenRecorder": True
    },
    "screen_recorder": {
        "audio_enabled": False,
        "frame_rate": 30
    }
}

class ConfigManager:
    def __init__(self):
        self.config = self.load_config()

    def load_config(self):
        if not os.path.exists(CONFIG_FILE):
            return DEFAULT_CONFIG
        
        try:
            with open(CONFIG_FILE, 'r', encoding='utf-8') as f:
                saved_config = json.load(f)
                # Merge with default to ensure all keys exist
                config = DEFAULT_CONFIG.copy()
                # Recursive update nicely would be better but simple update for now
                # basic checking for missing keys
                for key, value in saved_config.items():
                   if key in config and isinstance(value, dict):
                       config[key].update(value)
                   else:
                       config[key] = value
                return config
        except Exception as e:
            print(f"Error loading config: {e}")
            return DEFAULT_CONFIG

    def save_config(self):
        try:
            with open(CONFIG_FILE, 'w', encoding='utf-8') as f:
                json.dump(self.config, f, indent=4)
        except Exception as e:
            print(f"Error saving config: {e}")

    def get_module_status(self, module_name):
        return self.config["modules"].get(module_name, True)

    def set_module_status(self, module_name, enabled):
        self.config["modules"][module_name] = enabled
        self.save_config()

    def get_screen_recorder_config(self):
        return self.config.get("screen_recorder", DEFAULT_CONFIG["screen_recorder"])
