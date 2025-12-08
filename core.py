import yt_dlp
import os
import sys

class DownloaderCore:
    def __init__(self):
        self.ydl_opts = {
            'quiet': True,
            'no_warnings': True,
        }

    def get_info(self, url):
        """
        URL의 영상/재생목록 정보를 가져옵니다.
        """
        try:
            with yt_dlp.YoutubeDL(self.ydl_opts) as ydl:
                # download=False로 정보만 추출
                info = ydl.extract_info(url, download=False)
                return info
        except Exception as e:
            print(f"Error fetching info: {e}")
            return None

    def get_channel_videos(self, url, start=1, end=10):
        """
        채널/재생목록에서 특정 범위의 동영상 목록을 가져옵니다.
        """
        opts = {
            'quiet': True,
            'extract_flat': True, # 영상 세부 정보 없이 목록만 빠르게 가져옴
            'playliststart': start,
            'playlistend': end,
        }
        try:
            with yt_dlp.YoutubeDL(opts) as ydl:
                result = ydl.extract_info(url, download=False)
                if 'entries' in result:
                    return result['entries']
                return []
        except Exception as e:
            print(f"Error fetching channel videos: {e}")
            return []

    def download(self, url, options, progress_callback=None, logger=None):
        """
        옵션에 따라 다운로드를 수행합니다.
        options: {
            'save_path': str,
            'type': 'video' | 'audio',
            'resolution': str (e.g., '1080', '720') - video only,
            'subtitles': bool,
            'playlist': bool (default True if url is playlist)
        }
        """
        save_path = options.get('save_path', os.getcwd())
        
        # 기본 옵션 설정
        ydl_opts = {
            'outtmpl': os.path.join(save_path, '%(title)s.%(ext)s'),
            'progress_hooks': [progress_callback] if progress_callback else [],
            'quiet': True,
            'no_warnings': True,
        }

        # FFmpeg 경로 설정
        if getattr(sys, 'frozen', False):
            # 1. EXE와 같은 경로 확인
            ffmpeg_path = os.path.join(os.path.dirname(sys.executable), 'ffmpeg.exe')
            if not os.path.exists(ffmpeg_path):
                # 2. _MEIPASS (번들링된 경우) 확인
                ffmpeg_path = os.path.join(getattr(sys, '_MEIPASS', ''), 'ffmpeg.exe')
        else:
            # 소스 코드 실행 시
            ffmpeg_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'ffmpeg.exe')

        if os.path.exists(ffmpeg_path):
            ydl_opts['ffmpeg_location'] = ffmpeg_path
        else:
            # 못 찾으면 시스템 PATH 사용 (경고 출력 가능)
            if logger:
                logger.warning(f"FFmpeg not found at {ffmpeg_path}. Using system PATH.")


        if logger:
            ydl_opts['logger'] = logger

        # 브라우저 쿠키 사용 (로그인 필요한 사이트용)
        if options.get('cookies_browser'):
            # Chrome이 가장 일반적이므로 기본값으로 설정. 필요시 옵션화 가능.
            # Edge를 쓴다면 'edge', Firefox는 'firefox' 등으로 변경 가능
            ydl_opts['cookiesfrombrowser'] = ('chrome', ) 

        # 오디오 다운로드 (MP3 변환)
        if options.get('type') == 'audio':
            ydl_opts.update({
                'format': 'bestaudio/best',
                'postprocessors': [{
                    'key': 'FFmpegExtractAudio',
                    'preferredcodec': 'mp3',
                    'preferredquality': '192',
                }],
            })
        
        # 비디오 다운로드
        else:
            res = options.get('resolution')
            if res:
                # 해당 해상도 이하의 최고 화질 + 최고 음질
                ydl_opts['format'] = f'bestvideo[height<={res}]+bestaudio/best[height<={res}]'
            else:
                ydl_opts['format'] = 'bestvideo+bestaudio/best'
            
            # MP4로 병합 (호환성 위해)
            ydl_opts['merge_output_format'] = 'mp4'

        # 자막 다운로드
        if options.get('subtitles'):
            ydl_opts.update({
                'writesubtitles': True,       # 자막 파일 다운로드
                'writeautomaticsub': True,    # 자동 생성 자막도 포함
                'subtitleslangs': ['ko', 'en'], # 한국어, 영어 우선 (필요시 'all'로 변경 가능)
                'embedsubtitles': True,       # 영상에 자막 임베딩 (mkv, mp4 등 컨테이너 지원 시)
            })

        try:
            with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                # 정보 먼저 추출 (제목 등을 알기 위해)
                info = ydl.extract_info(url, download=True)
                return {'success': True, 'info': info}
        except Exception as e:
            error_msg = str(e)
            if logger:
                logger.error(f"Download failed: {error_msg}")
            return {'success': False, 'error': error_msg}
