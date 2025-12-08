import concurrent.futures
from core import DownloaderCore

class DownloadManager:
    def __init__(self, max_workers=3):
        self.executor = concurrent.futures.ThreadPoolExecutor(max_workers=max_workers)
        self.downloader = DownloaderCore()
        self.futures = []

    def submit_download(self, url, options, progress_callback=None, completion_callback=None):
        """
        다운로드 작업을 스레드 풀에 제출합니다.
        """
        future = self.executor.submit(self._download_task, url, options, progress_callback)
        
        if completion_callback:
            future.add_done_callback(lambda f: completion_callback(f.result()))
        
        self.futures.append(future)
        return future

    def _download_task(self, url, options, progress_callback):
        """
        실제 다운로드를 수행하는 내부 메서드
        """
        return self.downloader.download(url, options, progress_callback)

    def shutdown(self):
        self.executor.shutdown(wait=False)
