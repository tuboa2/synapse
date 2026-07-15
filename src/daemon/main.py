import asyncio
import logging
import signal
from typing import Any, Dict

from domain.database import TelemetryDatabase
from ipc.unix_socket import UnixSocketServer
from telemetry.factory import create_telemetry_provider
from ipc.zero_copy import ZeroCopyTelemetryServer, TelemetryData, SHM_NAME
import time
import uvloop

logging.basicConfig(
    level=logging.INFO, 
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger("synapse.daemon")

class Daemon:
    """
    Background Daemon orchestrating telemetry collection and IPC handling.
    Runs completely decoupled from the UI.
    """
    def __init__(self, socket_path: str = "/tmp/synapse.sock") -> None:
        self.socket_path = socket_path
        self.db = TelemetryDatabase()
        self.telemetry_engine = create_telemetry_provider()
        self.server = UnixSocketServer(socket_path, self.handle_ipc_message)
        self.shm_server = ZeroCopyTelemetryServer()
        self._running = False
        self._telemetry_task: asyncio.Task[None] | None = None
        
    async def handle_ipc_message(self, message: Dict[str, Any]) -> Dict[str, Any]:
        """Process incoming IPC messages from the UI Controller."""
        command = message.get("command")
        logger.debug(f"Received IPC command: {command}")
        
        if command == "ping":
            return {"status": "ok", "message": "pong"}
        elif command == "get_telemetry":
            return {"status": "ok", "shm_name": SHM_NAME}
                
        return {"status": "error", "message": "unknown command"}

    async def _telemetry_loop(self) -> None:
        """
        Continuous aggregation loop.
        Strictly utilizes asyncio.sleep to yield execution and prevent busy-waiting.
        """
        logger.info("Starting telemetry aggregation loop")
        self.telemetry_engine.initialize()
        self.shm_server.initialize()
        try:
            while self._running:
                # Target PID 1 (init/systemd) as an example target, normally received via IPC/Config
                target_pid = 1 
                metrics = self.telemetry_engine.get_metrics(target_pid)
                
                if metrics:
                    shm_data = TelemetryData(
                        timestamp=time.time(),
                        pid=metrics.pid,
                        cpu_usage_percent=metrics.cpu_usage_percent,
                        memory_usage_mb=metrics.memory_usage_mb,
                        io_wait_ms=getattr(metrics, 'io_wait_ms', 0),
                        gil_contention_ms=getattr(metrics, 'gil_contention_ms', 0)
                    )
                    self.shm_server.write_telemetry(shm_data)

                    await self.db.insert_telemetry(
                        pid=metrics.pid, 
                        cpu=metrics.cpu_usage_percent, 
                        memory=metrics.memory_usage_mb
                    )
                
                # Yield control to event loop; prevents CPU hogging
                await asyncio.sleep(1.0)
        except asyncio.CancelledError:
            logger.info("Telemetry loop cancelled")
        finally:
            self.telemetry_engine.cleanup()
            self.shm_server.cleanup()

    async def start(self) -> None:
        """Initialize server and begin telemetry aggregation."""
        self._running = True
        await self.server.start()
        
        # Setup graceful shutdown handlers
        loop = asyncio.get_running_loop()
        for sig in (signal.SIGINT, signal.SIGTERM):
            try:
                loop.add_signal_handler(sig, lambda s=sig: asyncio.create_task(self.stop()))
            except NotImplementedError:
                pass # Windows fallback ignores signal handler limitation

        logger.info("Daemon started successfully")
        
        # Launch non-blocking telemetry loop
        self._telemetry_task = asyncio.create_task(self._telemetry_loop())
        
        try:
            # Keep the main daemon task alive
            while self._running:
                await asyncio.sleep(3600)
        except asyncio.CancelledError:
            pass
        finally:
            await self.stop()

    async def stop(self) -> None:
        """Gracefully terminate background tasks and resources."""
        if not self._running:
            return
        
        logger.info("Initiating daemon shutdown...")
        self._running = False
        
        if self._telemetry_task:
            self._telemetry_task.cancel()
            
        await self.server.stop()
        self.db.close()
        logger.info("Daemon shutdown complete")


def run_daemon() -> None:
    uvloop.install()
    daemon = Daemon()
    try:
        asyncio.run(daemon.start())
    except KeyboardInterrupt:
        logger.info("Daemon interrupted by user via KeyboardInterrupt")

if __name__ == "__main__":
    run_daemon()
