"""Memory monitoring thread for Patroni.

MemMonitor runs in background, sampling host memory usage every `interval` seconds and
exposes `mem_usage` and `updated_at` properties. It reads threshold from
`ha.patroni.mem_use_limit` (via `Patroni` implementing `Tags.mem_use_limit`).
"""
import datetime
import logging
from threading import Thread, Event, RLock
from typing import Optional, Any

from .utils import tzutc

logger = logging.getLogger(__name__)


class MemMonitor(Thread):
    def __init__(self, ha: Any, interval: int) -> None:
        super().__init__(name='patroni-mem-monitor', daemon=True)
        self._ha = ha
        self._interval = max(1, int(interval or 10))
        self._stop = Event()
        self._lock = RLock()
        self._usage: Optional[float] = None
        self._updated_at: Optional[datetime.datetime] = None
        self._total: Optional[int] = None
        self._consecutive: int = 0
        self._alarmed: bool = False

    def run(self) -> None:
        logger.info('Starting Memory monitor thread, loop wait {} seconds'.format(self._interval))

        try:
            import psutil
        except Exception:
            logger.warning('psutil is not available, memory monitoring disabled')
            return

        while not self._stop.wait(self._interval):
            try:
                mem = psutil.virtual_memory()
                usage = getattr(mem, 'percent', None)
                total = getattr(mem, 'total', None)
                now = datetime.datetime.now(tzutc)
                try:
                    limit = self.limit
                except Exception:
                    limit = 90
                with self._lock:
                    self._usage = usage
                    self._updated_at = now
                    self._total = total
                    if usage is None or usage < limit:
                        self._consecutive = 0
                        self._alarmed = False
                    else:
                        self._consecutive += 1
                        if not self._alarmed and self._consecutive >= 10:
                            self._alarmed = True
                            logger.warning('Memory usage %.2f%% >= mem_use_limit %d%% (10 consecutive samples)', usage, limit)
            except Exception:
                logger.exception('Exception in MemMonitor')
        logger.info('Stopping Memory monitor thread')

    def stop(self) -> None:
        self._stop.set()

    @property
    def mem_usage(self) -> Optional[float]:
        with self._lock:
            return self._usage

    @property
    def mem_total(self) -> Optional[int]:
        with self._lock:
            return self._total

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
            return self._ha.patroni.mem_use_limit
        except Exception:
            logger.warning('Failed fetch mem_use_limit, using default 90')
            return 90
