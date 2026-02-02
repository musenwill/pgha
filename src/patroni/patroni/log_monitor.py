"""Postgres log (.log) file size monitoring thread for Patroni.

LogMonitor scans PostgreSQL data directory for files ending with `.log` (non-recursive
and recursive) and monitors their sizes. When a log file size exceeds the configured
`log_use_limit` for 10 consecutive samples, the monitor will log a warning and compress
that log file using gzip. Compressed files (`.gz`) are ignored for future monitoring.
"""
import datetime
import gzip
import logging
import os
from threading import Thread, Event, RLock
from typing import Any, Optional, List

from .utils import tzutc

logger = logging.getLogger(__name__)


class LogMonitor(Thread):
    def __init__(self, ha: Any, interval: int) -> None:
        super().__init__(name='patroni-log-monitor', daemon=True)
        self._ha = ha
        self._interval = max(1, int(interval or 10))
        self._stop = Event()
        self._lock = RLock()
        self._consecutive: int = 0
        self._alarmed: bool = False
        self._log_size:int  = 0
        self._updated_at: Optional[datetime.datetime] = None

    def _find_log_files(self) -> List[str]:
        # Prefer postgres data directory as the place to find .log files
        data_dir = getattr(self._ha.state_handler, 'data_dir', None)
        if not data_dir or not os.path.isdir(data_dir):
            return []
        matches: List[str] = []
        for root, _, files in os.walk(data_dir):
            for fn in files:
                if fn.endswith('.log'):
                    full = str(os.path.join(str(root), str(fn)))
                    matches.append(full)
        return matches

    def _compress_file(self, path: str) -> None:
        try:
            gz_path = path + '.gz'
            # stream copy to gzip
            with open(path, 'rb') as f_in, gzip.open(gz_path, 'wb') as f_out:
                while True:
                    chunk = f_in.read(1024 * 64)
                    if not chunk:
                        break
                    f_out.write(chunk)
            try:
                os.remove(path)
            except Exception:
                logger.exception('Failed to remove original log file after compression: %s', path)
        except Exception:
            logger.exception('Exception while compressing log file: %s', path)

    def run(self) -> None:
        logger.info('Starting Log monitor thread, loop wait {} seconds'.format(self._interval))
    
        while not self._stop.wait(self._interval):
            try:
                files = self._find_log_files()
                now = datetime.datetime.now(tzutc)
                limit = self.limit
                total_size:int = 0
                do_compress = False
                for path in files:
                    try:
                        size = os.path.getsize(path)
                        total_size += size
                    except Exception:
                        continue

                with self._lock:
                    self._log_size = total_size
                    self._updated_at = now
                    if total_size < limit:
                        self._consecutive = 0
                        self._alarmed = False
                    else:
                        self._consecutive += 1
                        if not self._alarmed and self._consecutive >= 10:
                            self._alarmed = True
                            do_compress = True
                            logger.warning('Log size %d >= log_use_limit %d (10 consecutive samples)',
                                            total_size, limit)

                if do_compress:
                    # determine newest .log file (most recently modified) and skip compressing it
                    latest_log: Optional[str] = None
                    try:
                        mtimes = {p: os.path.getmtime(p) for p in files}
                        if mtimes:
                            latest_log = max(mtimes, key=mtimes.get)
                    except Exception:
                        latest_log = None

                    for path in files:
                        # skip compressing the newest logfile (likely being written by Postgres)
                        if latest_log is not None and path == latest_log:
                            logger.info('Skipping compression of newest logfile %s', path)
                            continue
                        try:
                            self._compress_file(path)
                        except Exception:
                            continue
            except Exception:
                logger.exception('Exception in LogMonitor')
        logger.info('Stopping Log monitor thread')

    def stop(self) -> None:
        self._stop.set()

    @property
    def log_size(self) -> int:
        with self._lock:
            return self._log_size

    @property
    def alarmed(self) -> bool:
        with self._lock:
            return self._alarmed

    @property
    def updated_at(self) -> Optional[datetime.datetime]:
        with self._lock:
            return self._updated_at

    @property
    def limit(self) -> int:
        try:
            return int(self._ha.patroni.log_use_limit)
        except Exception:
            return 100 * 1024 ** 3
