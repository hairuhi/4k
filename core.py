import yt_dlp
import os
import sys
import re
from curl_cffi import requests as cffi_requests

class DownloaderCore:
    def __init__(self):
        self.ydl_opts = {
            'quiet': True,
            'no_warnings': True,
            'nocheckcertificate': True, # Ignore SSL errors
        }

    def get_info(self, url):
        """
        URL의 영상/재생목록 정보를 가져옵니다.
        """
        # Supjav handling
        if "supjav.com" in url:
            resolved_url = self._resolve_supjav_url(url)
            if resolved_url:
                print(f"Resolving Supjav to: {resolved_url}")
                url = resolved_url
                # Update opts for this request
                self.ydl_opts['http_headers'] = {'Referer': 'https://supjav.com/'}
            else:
                 print("Failed to resolve Supjav URL")
                 # Fallback to normal yt-dlp might fail but we try
        
        try:
            with yt_dlp.YoutubeDL(self.ydl_opts) as ydl:
                # download=False로 정보만 추출
                info = ydl.extract_info(url, download=False)
                return info
        except Exception as e:
            print(f"Error fetching info: {e}")
            return None

    def _resolve_supjav_url(self, url):
        try:
            # 1. Fetch Page
            r = cffi_requests.get(url, impersonate="chrome", headers={"Referer": "https://supjav.com/"})
            if r.status_code != 200:
                print(f"Supjav page fetch failed: {r.status_code}")
                return None
            
            html = r.text
            
            # 2. Extract Server Tokens
            servers = {}
            matches = re.finditer(r'data-link="([^"]+)">([^<]+)</a>', html)
            for m in matches:
                token = m.group(1)
                name = m.group(2).strip()
                servers[name] = token
            
            # Priority: ST (StreamTape) > DS (DoodStream) > JPA
            priority_list = ['ST', 'DS', 'JPA']
            
            for server_name in priority_list:
                if server_name not in servers:
                    continue
                
                print(f"Attempting to resolve video using server: {server_name}")
                target_token = servers[server_name]
                reversed_token = target_token[::-1]
                
                api_url = f"https://lk1.supremejav.com/supjav.php?c={reversed_token}"
                
                try:
                    r2 = cffi_requests.get(
                        api_url, 
                        impersonate="chrome", 
                        headers={"Referer": "https://supjav.com/"},
                        allow_redirects=False 
                    )
                    
                    if r2.status_code in [301, 302]:
                        final_url = r2.headers.get('Location')
                        
                        # Handle StreamTape manually since yt-dlp extractor is missing/broken
                        if "streamtape" in final_url and "/e/" in final_url:
                             try:
                                 print(f"Manually extracting from StreamTape: {final_url}")
                                 st_resp = cffi_requests.get(final_url, impersonate="chrome", headers={"Referer": "https://supjav.com/"})
                                 if st_resp.status_code == 200:
                                     # 1. Find the target element ID used by the player
                                     # Pattern: var srclink = $('#botlink').text()
                                     id_match = re.search(r"var\s+srclink\s*=\s*\$\('#([^']+)'\)\.text", st_resp.text)
                                     target_id = id_match.group(1) if id_match else 'botlink' # Default to botlink
                                     
                                     # 2. Find the assignment logic
                                     # Pattern: document.getElementById('botlink').innerHTML = '...' + ('...').substring(...)
                                     # Note: There might be multiple assignments, usually the last one or the one matching the pattern matters.
                                     # We look for the one with substring()
                                     assign_regex = r"document\.getElementById\('" + re.escape(target_id) + r"'\)\.innerHTML\s*=\s*'([^']*)'\s*\+\s*(?:''\s*\+\s*)?\('([^']*)'\)\.substring\((\d+)\)(?:\.substring\((\d+)\))?"
                                     
                                     assign_match = re.search(assign_regex, st_resp.text)
                                     if assign_match:
                                         part1 = assign_match.group(1)
                                         part2 = assign_match.group(2)
                                         offset1 = int(assign_match.group(3))
                                         
                                         # Apply substring logic
                                         decoded_part2 = part2[offset1:]
                                         # Handle optional second substring
                                         if assign_match.group(4):
                                             offset2 = int(assign_match.group(4))
                                             decoded_part2 = decoded_part2[offset2:]
                                             
                                         direct_url = part1 + decoded_part2
                                         if direct_url.startswith('//'):
                                             direct_url = "https:" + direct_url
                                         
                                         # Append &stream=1 if not present (as seen in JS)
                                         # var srclink = ... + '&stream=1';
                                         if "&stream=1" not in direct_url:
                                              direct_url += "&stream=1"
                                              
                                         print(f"Extracted direct StreamTape URL: {direct_url}")
                                         return direct_url
                             except Exception as e:
                                 print(f"StreamTape manual extraction failed: {e}")
                                 # Fallback to generic URL if extraction fails
                        
                        # Validate URL availability (Basic 404 check)
                        # We use cffi again because normal requests had SSL/403 issues
                        # Disable verify to avoid local cert issues
                        # Add Referer because StreamTape/others might block without it
                        check = cffi_requests.head(
                            final_url, 
                            impersonate="chrome", 
                            headers={"Referer": "https://supjav.com/"},
                            timeout=5, 
                            verify=False
                        )
                        if check.status_code == 404:
                            print(f"Server {server_name} returned 404. Video likely deleted.")
                            # If ST failed with 404, we continue to next server (DS)
                            continue
                        elif check.status_code == 200 or check.status_code == 302:
                             print(f"Server {server_name} seems valid.")
                             return final_url
                        else:
                             print(f"Server {server_name} returned status {check.status_code}. Using it anyway.")
                             return final_url

                except Exception as e:
                    print(f"Error resolving {server_name}: {e}")
                    continue
            
            print("All server attempts failed.")
            return None
                
        except Exception as e:
            print(f"Supjav resolution error: {e}")
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
        """
        
        # Supjav handling
        if "supjav.com" in url:
            resolved_url = self._resolve_supjav_url(url)
            if resolved_url:
                url = resolved_url
                if logger: logger.info(f"Resolved Supjav URL to: {url}")
                # Add Referer for Supjav resolved links
                ydl_opts['http_headers'] = {'Referer': 'https://supjav.com/'}
        
        # OnlyFans / XFans handling
        elif "onlyfans.com" in url:
            if logger: logger.info("Detected OnlyFans URL. Ensuring cookies are used.")
            # OnlyFans almost always requires cookies.
            if not options.get('cookie_file') and not options.get('cookies_browser'):
                 if logger: logger.warning("OnlyFans requires authentication. Please use 'cookies.txt' or Browser Cookies.")
        
        elif "xfans.com" in url or "xfans" in url: # Adjust domain match as needed
             if logger: logger.info("Detected XFans URL.")
             # Assume it behaves like other fan sites requiring Referer or Cookies
             ydl_opts['http_headers'] = {'Referer': url} # Basic referer just in case
        
        save_path = options.get('save_path', os.getcwd())
        
        # 기본 옵션 설정
        ydl_opts = {
            'outtmpl': os.path.join(save_path, '%(title)s.%(ext)s'),
            'progress_hooks': [progress_callback] if progress_callback else [],
            'quiet': True,
            'no_warnings': True,
            'nocheckcertificate': True, # Ignore SSL errors
            'user_agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36',
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

        if options.get('cookie_file'):
            ydl_opts['cookiefile'] = options.get('cookie_file')
        # 브라우저 쿠키 사용 (로그인 필요한 사이트용) - 파일이 없을 때만
        elif options.get('cookies_browser'):
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
            # Chrome 쿠키 잠금 에러에 대한 친절한 메시지 추가
            if "Could not copy Chrome cookie database" in error_msg:
                error_msg = f"오류: Chrome 브라우저가 실행 중이어서 인증 정보를 가져올 수 없습니다.\nChrome을 완전히 종료(백그라운드 포함)한 후 다시 시도해주세요.\n\n(원문: {error_msg})"
            elif "DPAPI" in error_msg:
                error_msg = f"오류: Chrome 쿠키 암호 해독에 실패했습니다.\n이 문제는 보통 권한 문제나 보안 설정 때문입니다.\n해결책: 'Get cookies.txt LOCALLY' 크롬 확장 프로그램을 설치하여\ncookies.txt 파일을 추출한 뒤, 프로그램에서 해당 파일을 선택하여 시도해주세요.\n\n(원문: {error_msg})"
            elif "403" in error_msg and "Forbidden" in error_msg:
                 if options.get('cookie_file'):
                     error_msg = f"오류: 403 Forbidden (접근 거부)\n[cookies.txt] 파일을 사용했으나 차단되었습니다.\n1. 쿠키 파일이 만료되었을 수 있습니다. 새로 추출해주세요.\n2. Netscape 포맷이 맞는지 확인해주세요.\n3. 추출 시 사용한 계정과 현재 접속 IP가 다르면 차단될 수 있습니다.\n\n(원문: {error_msg})"
                 elif options.get('cookies_browser'):
                     error_msg = f"오류: 403 Forbidden (접근 거부)\n[{options.get('cookies_browser')}] 브라우저 쿠키를 사용했으나 차단되었습니다.\n1. 브라우저에서 Udemy에 로그인되어 있는지 확인하세요.\n2. 브라우저를 완전히 종료 후 다시 시도하거나, [cookies.txt] 방식을 사용해보세요.\n\n(원문: {error_msg})"
                 else:
                     error_msg = f"오류: 403 Forbidden (접근 거부)\n인증 정보 없이 접근하여 차단되었습니다. 로그인 또는 쿠키 설정이 필요합니다.\n\n(원문: {error_msg})"
            
            if logger:
                logger.error(f"Download failed: {error_msg}")
            return {'success': False, 'error': error_msg}
