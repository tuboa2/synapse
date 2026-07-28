import asyncio
import multiprocessing
import os
import sys

# Ensure src is in the python path for absolute imports
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "src"))

import argparse
import contextlib

from cli.main import run_cli, start_daemon_process

if __name__ == "__main__":
    multiprocessing.freeze_support()

    parser = argparse.ArgumentParser(description="Synapse Telemetry Daemon")
    parser.add_argument("--query", type=str, help="Start daemon with custom SQL telemetry query")
    args = parser.parse_args()

    # Spawn the background daemon silently, passing the query if present
    daemon_process = multiprocessing.Process(
        target=start_daemon_process,
        args=(args.query,),
        daemon=True
    )
    daemon_process.start()

    if sys.platform != "win32":
        import uvloop
        uvloop.install()
    with contextlib.suppress(KeyboardInterrupt):
        asyncio.run(run_cli())
