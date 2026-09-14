"""Single-instance retention and privacy maintenance worker.

Run this process separately from stateless API replicas.  It owns material
retention and the account-deletion cooling-period processor, both of which
perform external object-store/checkpoint cleanup in addition to SQL deletes.
"""

from __future__ import annotations

import asyncio
import contextlib
import logging
import signal

from services.material_retention import run_material_retention

logger = logging.getLogger(__name__)


def main() -> None:
    async def serve() -> None:
        stop = asyncio.Event()
        loop = asyncio.get_running_loop()
        for signum in (signal.SIGINT, signal.SIGTERM):
            with contextlib.suppress(NotImplementedError, RuntimeError):
                loop.add_signal_handler(signum, stop.set)
        task = asyncio.create_task(run_material_retention(stop))
        try:
            await stop.wait()
        finally:
            stop.set()
            task.cancel()
            await asyncio.gather(task, return_exceptions=True)

    asyncio.run(serve())


if __name__ == "__main__":
    main()
