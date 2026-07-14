import logging
from typing import Callable, Dict
try:
    from pynput import keyboard
except ImportError:
    keyboard = None

logger = logging.getLogger(__name__)

class GlobalHotkeyManager:
    """
    Robust, non-blocking global hotkey registration for Linux (X11/XFCE) and cross-platform compatibility.
    Runs entirely within a background daemon thread, preventing UI loop interruption.
    """
    def __init__(self) -> None:
        self.listener = None
        self.hotkeys: Dict[str, Callable[[], None]] = {}

    def register(self, combination: str, callback: Callable[[], None]) -> None:
        self.hotkeys[combination] = callback
        logger.info(f"Registered global hotkey: {combination}")

    def start(self) -> None:
        if keyboard is None:
            logger.warning("pynput not installed. Global hotkeys disabled. (Please install pynput)")
            return

        # pynput keyboard.GlobalHotKeys runs its event interception in a dedicated thread
        self.listener = keyboard.GlobalHotKeys(self.hotkeys)
        self.listener.start()
        logger.info("Global hotkey listener started successfully.")

    def stop(self) -> None:
        if self.listener:
            self.listener.stop()
