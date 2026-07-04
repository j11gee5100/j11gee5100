from __future__ import annotations

import logging
import signal
import time
from dataclasses import dataclass

from app.core.logging import configure_logging


@dataclass
class WorkerContext:
    name: str
    poll_interval_sec: int
    should_exit: bool = False


def bootstrap_worker(worker_name: str, log_level: str, poll_interval_sec: int) -> WorkerContext:
    configure_logging(log_level)
    ctx = WorkerContext(name=worker_name, poll_interval_sec=poll_interval_sec)
    logger = logging.getLogger(worker_name)

    def _handle_signal(signum, _frame):
        logger.info("received signal=%s, stopping worker", signum)
        ctx.should_exit = True

    signal.signal(signal.SIGTERM, _handle_signal)
    signal.signal(signal.SIGINT, _handle_signal)
    return ctx


def run_forever(ctx: WorkerContext, work_label: str) -> None:
    logger = logging.getLogger(ctx.name)
    logger.info("worker started: %s (interval=%ss)", work_label, ctx.poll_interval_sec)
    while not ctx.should_exit:
        logger.info("tick: %s", work_label)
        time.sleep(ctx.poll_interval_sec)
    logger.info("worker stopped: %s", work_label)

