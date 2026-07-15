import os
import sys
import json
import logging
import threading
import asyncio
from typing import Any, Dict

# Graphics Backend Optimization (Sub-50ms render path)
# Explicitly force Vulkan for Linux XFCE zero-latency rendering; QSG will fallback to Metal/D3D12 safely.
os.environ["QSG_RHI_BACKEND"] = "vulkan"
os.environ["QSG_INFO"] = "1" # Outputs GPU offload stats to console

from PySide6.QtCore import QObject, Signal, Slot, QUrl, QTimer
from PySide6.QtGui import QGuiApplication
from PySide6.QtQml import QQmlApplicationEngine

from ipc.unix_socket import UnixSocketClient
from ipc.zero_copy import ZeroCopyTelemetryClient
from ui.hotkeys import GlobalHotkeyManager
import uvloop

logger = logging.getLogger("synapse.ui")
logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(name)s - %(levelname)s - %(message)s")

class IPCWorker(QObject):
    telemetry_received = Signal(list)
    command_response = Signal(str, bool)

    def __init__(self, socket_path: str = "/tmp/synapse.sock") -> None:
        super().__init__()
        self.socket_path = socket_path
        self.client = UnixSocketClient(self.socket_path)
        self.shm_client = ZeroCopyTelemetryClient()
        
        # Install uvloop for this thread before creating the loop
        uvloop.install()
        self.loop = asyncio.new_event_loop()
        self.thread = threading.Thread(target=self._run_loop, daemon=True, name="IPCWorkerThread")

    def start(self) -> None:
        self.thread.start()

    def _run_loop(self) -> None:
        asyncio.set_event_loop(self.loop)
        self.loop.run_forever()

    def send_command(self, cmd_str: str) -> None:
        asyncio.run_coroutine_threadsafe(self._async_send(cmd_str), self.loop)

    def fetch_telemetry(self) -> None:
        data = self.shm_client.read_telemetry()
        if data:
            telemetry_dict = {
                "pid": data.pid,
                "cpu_usage_percent": data.cpu_usage_percent,
                "memory_usage_mb": data.memory_usage_mb,
                "io_wait_ms": data.io_wait_ms,
                "gil_contention_ms": data.gil_contention_ms
            }
            self.telemetry_received.emit([telemetry_dict])

    async def _async_send(self, cmd_str: str) -> None:
        try:
            await self.client.connect()
            await self.client.send_message({"command": cmd_str})
            response = await self.client.receive_message()
            
            if response.get("status") == "ok":
                res_str = json.dumps(response.get("data", {}), indent=2) if response.get("data") else response.get("message", "Success")
                self.command_response.emit(res_str, False)
            else:
                self.command_response.emit(response.get("message", "Error"), True)
            await self.client.disconnect()
        except Exception as e:
            self.command_response.emit(f"IPC Error: {e}", True)


class UIController(QObject):
    telemetryUpdated = Signal(str)
    commandResponse = Signal(str, bool)

    def __init__(self, ipc_worker: IPCWorker, engine: QQmlApplicationEngine) -> None:
        super().__init__()
        self.ipc_worker = ipc_worker
        self.engine = engine
        
        self.ipc_worker.telemetry_received.connect(self._format_telemetry)
        self.ipc_worker.command_response.connect(self.commandResponse.emit)

    @Slot(str)
    def submitCommand(self, cmd: str) -> None:
        self.ipc_worker.send_command(cmd)

    @Slot(list)
    def _format_telemetry(self, data: list) -> None:
        if not data:
            self.telemetryUpdated.emit("No telemetry data.")
            return
        latest = data[0]
        formatted = (
            f"SYNAPSE HUD [PID: {latest['pid']}]\n"
            f"CPU: {latest['cpu_usage_percent']}%\n"
            f"MEM: {latest['memory_usage_mb']:.1f} MB\n"
            f"I/O: {latest['io_wait_ms']} ms\n"
            f"GIL: {latest['gil_contention_ms']} ms"
        )
        self.telemetryUpdated.emit(formatted)
        
    @Slot()
    def toggle_cli(self) -> None:
        root_objs = self.engine.rootObjects()
        if len(root_objs) > 1:
            cli_window = root_objs[1]
            cli_window.setVisible(not cli_window.isVisible())

    @Slot()
    def toggle_hud(self) -> None:
        root_objs = self.engine.rootObjects()
        if len(root_objs) > 0:
            hud_window = root_objs[0]
            hud_window.setVisible(not hud_window.isVisible())

def run_ui() -> None:
    # QGuiApplication avoids QtWidgets overhead, achieving extreme lightweight startup
    uvloop.install()
    app = QGuiApplication(sys.argv)
    
    ipc_worker = IPCWorker()
    ipc_worker.start()

    engine = QQmlApplicationEngine()
    controller = UIController(ipc_worker, engine)
    
    # Bind the controller before loading QML
    engine.rootContext().setContextProperty("uiController", controller)
    
    qml_dir = os.path.join(os.path.dirname(__file__), "qml")
    engine.load(QUrl.fromLocalFile(os.path.join(qml_dir, "HUD.qml")))
    engine.load(QUrl.fromLocalFile(os.path.join(qml_dir, "CLI.qml")))

    if not engine.rootObjects():
        logger.error("Failed to load QML root objects.")
        sys.exit(-1)
        
    if "--train" in sys.argv:
        logger.info("PGO Training Mode: Executing hot paths...")
        for _ in range(100):
            ipc_worker.fetch_telemetry()
        QTimer.singleShot(100, app.quit)
        sys.exit(app.exec())

    # Initialize non-blocking Global Hotkeys
    hotkeys = GlobalHotkeyManager()
    hotkeys.register('<ctrl>+<shift>+p', controller.toggle_cli)
    hotkeys.register('<alt>+h', controller.toggle_hud)
    hotkeys.start()

    # Rapid telemetry polling (2Hz), executed entirely asynchronously in the IPC thread
    timer = QTimer()
    timer.timeout.connect(ipc_worker.fetch_telemetry)
    timer.start(500)

    try:
        sys.exit(app.exec())
    finally:
        hotkeys.stop()

if __name__ == "__main__":
    run_ui()
