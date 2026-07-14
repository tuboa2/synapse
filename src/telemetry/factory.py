import logging
import platform
from .base import TelemetryProvider

logger = logging.getLogger(__name__)

def create_telemetry_provider() -> TelemetryProvider:
    """
    Domain-Driven Factory resolving the optimal Telemetry Provider based on host OS.
    The invoking daemon only ever interacts with the abstract TelemetryProvider interface.
    """
    system = platform.system().lower()
    
    if system == "linux":
        logger.info("Platform detected: Linux. Bootstrapping native eBPF Telemetry Engine.")
        from .linux_ebpf import LinuxEBPFProvider
        return LinuxEBPFProvider()
    elif system == "windows":
        logger.info("Platform detected: Windows. Bootstrapping WMI/psutil Telemetry Engine.")
        from .windows_wmi import WindowsWMIProvider
        return WindowsWMIProvider()
    elif system == "darwin":
        logger.info("Platform detected: macOS. Bootstrapping DTrace Telemetry Engine.")
        from .macos_dtrace import MacOSDTraceProvider
        return MacOSDTraceProvider()
    else:
        logger.warning(f"Platform unsupported: {system}. Defaulting to Windows compatibility fallback.")
        from .windows_wmi import WindowsWMIProvider
        return WindowsWMIProvider()
