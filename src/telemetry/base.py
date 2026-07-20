import abc
from dataclasses import dataclass
from typing import Optional

@dataclass
class ProcessMetrics:
    """
    Domain-Driven Immutable Data Object representing instant process telemetry.
    Ensures rigorous type-safety and consistency across all OS implementations.
    """
    pid: int
    name: str
    cpu_usage_percent: float
    memory_usage_mb: float
    io_wait_ms: float
    gil_contention_ms: float

class TelemetryProvider(abc.ABC):
    """
    Domain-Driven Design Abstract Interface for Telemetry gathering.
    The Main Daemon depends entirely on this abstraction, ensuring zero
    coupling to the underlying OS-specific gathering methods (eBPF, DTrace, WMI).
    """
    
    @abc.abstractmethod
    def initialize(self, query: Optional[str] = None) -> None:
        """Initialize any system-level probes, memory maps, or hooks required."""
        pass

    @abc.abstractmethod
    def cleanup(self) -> None:
        """Safely detach and cleanup probes, releasing kernel resources."""
        pass

    @abc.abstractmethod
    def get_metrics(self, pid: int) -> Optional[ProcessMetrics]:
        """Fetch instantaneous telemetry for a given Process ID."""
        pass
