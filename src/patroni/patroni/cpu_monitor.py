"""CPU monitoring thread for Patroni.

CPUMonitor runs in background, sampling host CPU usage every `interval` seconds and
exposes `cpu_usage` and `updated_at` properties. It reads threshold from
`ha.patroni.cpu_use_limit` (via `Patroni` implementing `Tags.cpu_use_limit`).
"""
import datetime
import logging
from threading import Thread, Event, RLock
from typing import Optional, Any

from .utils import tzutc

logger = logging.getLogger(__name__)


class CPUMonitor(Thread):
    def __init__(self, ha: Any, interval: int) -> None:
        super().__init__(name='patroni-cpu-monitor', daemon=True)
        self._ha = ha
        self._interval = max(1, int(interval or 10))
        self._stop = Event()
        self._lock = RLock()
        self._usage: Optional[float] = None
        self._updated_at: Optional[datetime.datetime] = None
        self._consecutive: int = 0
        self._alarmed: bool = False

    def run(self) -> None:
        logger.info('Starting CPU monitor thread, loop wait {} seconds'.format(self._interval))

        try:
            import psutil
        except Exception:
            logger.warning('psutil is not available, CPU monitoring disabled')
            return

        while not self._stop.wait(self._interval):
            try:
                usage = psutil.cpu_percent(interval=None)
                now = datetime.datetime.now(tzutc)
                limit = self.limit
                with self._lock:
                    self._usage = usage
                    self._updated_at = now
                    if usage < limit:
                        self._consecutive = 0
                        self._alarmed = False
                    else:
                        self._consecutive += 1
                        if not self._alarmed and self._consecutive >= 10:
                            self._alarmed = True
                            logger.warning('CPU usage %.2f%% >= cpu_use_limit %d%% (10 consecutive samples)', usage, limit)
            except Exception:
                logger.exception('Exception in CPUMonitor')
        logger.info('Stopping CPU monitor thread')

    def stop(self) -> None:
        self._stop.set()

    @property
    def cpu_usage(self) -> Optional[float]:
        with self._lock:
            return self._usage

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
            return self._ha.patroni.cpu_use_limit
        except Exception:
            logger.warning('Failed fetch cpu_use_limit, using default 90')
            return 90
