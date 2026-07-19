import multiprocessing
import asyncio
import sys
import uvloop
import os

# Ensure src is in the python path for absolute imports
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "src"))

from cli.main import run_cli, transpile_query, start_daemon_process
import argparse

if __name__ == "__main__":
    multiprocessing.freeze_support()
    
    parser = argparse.ArgumentParser(description="Synapse Telemetry Daemon")
    parser.add_argument("--query", type=str, help="Transpile a SQL query into eBPF C code and exit")
    args = parser.parse_args()
    
    if args.query:
        transpile_query(args.query)
        sys.exit(0)
    
    # Spawn the background daemon silently
    daemon_process = multiprocessing.Process(target=start_daemon_process, daemon=True)
    daemon_process.start()

    uvloop.install()
    try:
        asyncio.run(run_cli())
    except KeyboardInterrupt:
        pass
