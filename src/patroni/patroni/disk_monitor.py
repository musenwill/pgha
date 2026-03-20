"""Disk monitoring thread for Patroni.

DiskMonitor runs in background, sampling host disk usage every `interval` seconds and
exposes `disk_usage` and `updated_at` properties. It reads threshold from
`ha.patroni.disk_use_limit` (via `Patroni` implementing `Tags.disk_use_limit`).
"""
import datetime
import logging
from threading import Thread, Event, RLock
from typing import Optional, Any

from .utils import tzutc

logger = logging.getLogger(__name__)


class DiskMonitor(Thread):
    def __init__(self, ha: Any) -> None:
        super().__init__(name='patroni-disk-monitor', daemon=True)
        self._ha = ha
        self._stop = Event()
        self._lock = RLock()
        self._usage: Optional[float] = None
        self._updated_at: Optional[datetime.datetime] = None
        self._total: Optional[int] = None
        self._consecutive: int = 0
        self._consecutive_below: int = 0
        self._alarmed: bool = False
        self.has_set_readonly: bool = False

    def run(self) -> None:
        logger.info('Starting Disk monitor thread')

        try:
            import psutil
        except Exception:
            logger.warning('psutil is not available, disk monitoring disabled')
            return

        while not self._stop.wait(self.loop_wait):
            if self.limit <= 0:
                # disk_use_limit <= 0 means disabled, so skip monitoring
                continue

            try:
                pg_data_dir = self._ha.state_handler.data_dir
                du = psutil.disk_usage(pg_data_dir)
                usage = getattr(du, 'percent', None)
                total = getattr(du, 'total', None)
                now = datetime.datetime.now(tzutc)
                limit = self.limit
                with self._lock:
                    self._usage = usage
                    self._updated_at = now
                    self._total = total
                    if usage is None or usage < limit:
                        self._consecutive = 0
                        self._alarmed = False
                        self._consecutive_below += 1
                    else:
                        self._consecutive_below = 0
                        self._consecutive += 1
                        if not self._alarmed and self._consecutive >= 10:
                            self._alarmed = True
                            logger.warning('Disk usage %.2f%% >= disk_use_limit %d%% (10 consecutive samples)', usage, limit)
            except Exception:
                logger.exception('Exception in DiskMonitor')
        logger.info('Stopping Disk monitor thread')

    def stop(self) -> None:
        self._stop.set()

    @property
    def disk_usage(self) -> Optional[float]:
        with self._lock:
            return self._usage

    @property
    def disk_total(self) -> Optional[int]:
        with self._lock:
            return self._total

    @property
    def alarmed(self) -> bool:
        with self._lock:
            return self._alarmed

    @property
    def should_restore_readonly(self) -> bool:
        """Whether PostgreSQL read-only mode should be restored."""
        with self._lock:
            return self.has_set_readonly and self._consecutive_below >= 10 and not self._alarmed

    @property
    def updated_at(self) -> Optional[datetime.datetime]:
        with self._lock:
            return self._updated_at

    @property
    def limit(self) -> int:
        return int(self._ha.patroni.disk_use_limit)

    @property
    def loop_wait(self) -> int:
        try:
            return max(1, self._ha.dcs.loop_wait)
        except Exception:
            return 10
