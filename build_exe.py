import PyInstaller.__main__
import customtkinter
import os
import shutil

# Get customtkinter path for data
ctk_path = os.path.dirname(customtkinter.__file__)

print(f"CustomTkinter path: {ctk_path}")

# Clean up previous build artifacts
if os.path.exists('build'):
    shutil.rmtree('build', ignore_errors=True)
if os.path.exists('dist'):
    shutil.rmtree('dist', ignore_errors=True)

PyInstaller.__main__.run([
    'main.py',
    '--name=Py4KDownloader',
    '--onefile',
    '--windowed',
    '--noconfirm',
    '--clean',
    '--workpath=./build_release', # Avoid locked build folder
    f'--add-data={ctk_path};customtkinter',
    '--icon=NONE', # 아이콘이 있다면 설정, 없으면 기본
])

# Build 완료 후 ffmpeg 파일 복사
print("Copying FFmpeg binaries to dist folder...")
dist_dir = os.path.join(os.getcwd(), 'dist')
if not os.path.exists(dist_dir):
    os.makedirs(dist_dir)

for binary in ['ffmpeg.exe', 'ffprobe.exe']:
    src = os.path.join(os.getcwd(), binary)
    if not os.path.exists(src):
        # Check parent directory
        src = os.path.join(os.path.dirname(os.getcwd()), binary)
    
    dst = os.path.join(dist_dir, binary)
    if os.path.exists(src):
        shutil.copy2(src, dst)
        print(f"Copied {binary} to {dist_dir}")
    else:
        print(f"Warning: {binary} not found in source or parent directory.")

