import time
import socket
import logging
import threading
import subprocess
from datetime import datetime, timedelta
from patroni.postgresql import Postgresql, PgIsReadyStatus

logger = logging.getLogger(__name__)


class PostmasterPhonyMonitor(threading.Thread):
    def __init__(self, postgresql: Postgresql, interval:int=10, fail_count:int=3, phony_long_cycle_time:int=300):
        super().__init__(name="postgres_d_monitor", daemon=True)
        self._pg = postgresql
        self._interval = interval
        self._fail_count = fail_count
        self._consecutive_failures = 0
        self._last_phony_failover_at = None
        self._phony_long_cycle_time = phony_long_cycle_time
        self._lock = threading.Lock()
        self._phony = False
        self._stop = threading.Event()

    def stop(self):
        self._stop.set()

    def is_phony(self):
        with self._lock:
            return self._phony

    def recover(self):
        with self._lock:
            self._phony = False
            self._consecutive_failures = 0

    def run(self):
        while not self._stop.is_set():
            try:
                if self._check_d_state() and self._check_connect_timeout():
                    with self._lock:
                        self._consecutive_failures += 1
                    logger.info(
                        "Postgres D-state detected (%d/%d)",
                        self._consecutive_failures, self._fail_count
                    )
                else:
                    with self._lock:
                        self._consecutive_failures = 0

                with self._lock:
                    if (self._last_phony_failover_at and 
                        datetime.now() - self._last_phony_failover_at > timedelta(seconds=self._phony_long_cycle_time)):
                        self._phony = self._consecutive_failures >= self._fail_count
                        if self._phony:
                            logger.info("Postmaster phony confirmed (%d/%d)", self._consecutive_failures, self._fail_count)
                            self._last_phony_failover_at = datetime.now()
                    elif self._consecutive_failures >= self._fail_count:
                        logger.info("Postmaster phony suspected (%d/%d)", self._consecutive_failures, self._fail_count)

            except Exception:
                logger.exception("postgres d monitor failed")

            time.sleep(self._interval)

    def _check_d_state(self):
        pid = self._pg.postmaster_pid()
        if pid < 0:
            return False

        try:
            out = subprocess.check_output(
                ["ps", "-o", "stat=", "--pid", str(pid)],
                text=True
            ).strip()
            return "D" in out
        except Exception:
            return False

    def _check_connect_timeout(self):
        try:
            ready = self._pg.pg_isready()
            return ready == PgIsReadyStatus.NO_RESPONSE
        except socket.timeout:
            return True
        except Exception:
            return 
