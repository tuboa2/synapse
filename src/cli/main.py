import os
import sys
import json
import logging
import asyncio
import multiprocessing
import argparse
from typing import Any, Dict, Optional, List

from ipc.unix_socket import UnixSocketClient
from ipc.zero_copy import ZeroCopyTelemetryClient
from daemon.main import run_daemon
import uvloop

logger = logging.getLogger("synapse.cli")
# Disable standard logging output since we'll be taking over the screen
logging.getLogger().setLevel(logging.ERROR)

def start_daemon_process():
    """Run the daemon in a background process and log to a file."""
    log_file = open("synapse_daemon.log", "a")
    sys.stdout = log_file
    sys.stderr = log_file
    
    root_logger = logging.getLogger()
    for handler in root_logger.handlers[:]:
        root_logger.removeHandler(handler)
    
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
        stream=log_file
    )
    
    run_daemon()


class IPCWorker:
    def __init__(self, socket_path: str = "/tmp/synapse.sock") -> None:
        self.socket_path = socket_path
        self.client = UnixSocketClient(self.socket_path)
        self.shm_client = ZeroCopyTelemetryClient()

    def fetch_telemetry(self) -> List[Dict[str, Any]]:
        data_list = self.shm_client.read_telemetry()
        results = []
        for data in data_list:
            results.append({
                "pid": data.pid,
                "name": data.name,
                "cpu_usage_percent": data.cpu_usage_percent,
                "memory_usage_mb": data.memory_usage_mb,
                "io_wait_ms": data.io_wait_ms,
                "gil_contention_ms": data.gil_contention_ms
            })
        return results

    async def send_command(self, cmd_str: str) -> dict:
        try:
            await self.client.connect()
            await self.client.send_message({"command": cmd_str})
            response = await self.client.receive_message()
            await self.client.disconnect()
            return response
        except Exception as e:
            return {"status": "error", "message": str(e)}

async def run_cli() -> None:
    worker = IPCWorker()
    
    # Hide cursor and clear screen
    sys.stdout.write('\033[?25l\033[2J')
    sys.stdout.flush()
    
    try:
        while True:
            telemetry_list = worker.fetch_telemetry()
            
            # Home cursor
            sys.stdout.write('\033[H')
            
            if telemetry_list:
                output = f"\033[1;36mSYNAPSE TELEMETRY\033[0m  [Tracking {len(telemetry_list)} Python Processes]\n"
                output += f"{'-'*95}\n"
                output += f"{'PID':<8} | {'Name':<15} | {'CPU %':<10} | {'Memory (MB)':<12} | {'I/O Wait (ms)':<15} | {'GIL (ms)':<10}\n"
                output += f"{'-'*95}\n"
                
                # Sort by CPU usage descending
                telemetry_list.sort(key=lambda x: x["cpu_usage_percent"], reverse=True)
                
                for tel in telemetry_list:
                    output += (
                        f"{tel['pid']:<8} | "
                        f"{tel['name']:<15} | "
                        f"\033[1;32m{tel['cpu_usage_percent']:>7.1f} %\033[0m | "
                        f"\033[1;33m{tel['memory_usage_mb']:>9.1f} MB\033[0m | "
                        f"\033[1;31m{tel['io_wait_ms']:>10} ms\033[0m | "
                        f"\033[1;35m{tel['gil_contention_ms']:>6} ms\033[0m\n"
                    )
                
                output += f"{'-'*95}\n"
                output += f"Press Ctrl+C to exit.\n"
            else:
                output = "\033[1;33mWaiting for telemetry from Daemon...\033[0m\n\nPress Ctrl+C to exit.\n"
            
            # Clear to end of screen to avoid trailing characters
            output += "\033[J"
            
            sys.stdout.write(output)
            sys.stdout.flush()
            
            await asyncio.sleep(0.5)
            
    except asyncio.CancelledError:
        pass
    finally:
        # Show cursor and clear formatting
        sys.stdout.write('\033[?25h\033[0m\n')
        sys.stdout.flush()

if __name__ == "__main__":
    multiprocessing.freeze_support()
    
    # Spawn the background daemon silently
    daemon_process = multiprocessing.Process(target=start_daemon_process, daemon=True)
    daemon_process.start()

    uvloop.install()
    try:
        asyncio.run(run_cli())
    except KeyboardInterrupt:
        # Handle clean exit on Ctrl+C
        pass
