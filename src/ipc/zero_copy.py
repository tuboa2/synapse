import struct
from multiprocessing import shared_memory
from typing import Optional, NamedTuple
import logging

logger = logging.getLogger(__name__)

# Struct layout: 
# double timestamp (8 bytes)
# uint32 pid (4 bytes)
# float cpu_usage_percent (4 bytes)
# float memory_usage_mb (4 bytes)
# uint32 io_wait_ms (4 bytes)
# uint32 gil_contention_ms (4 bytes)
# Total size: 28 bytes
STRUCT_FORMAT = 'dIffII'
STRUCT_SIZE = struct.calcsize(STRUCT_FORMAT)
SHM_NAME = "synapse_telemetry_shm"

class TelemetryData(NamedTuple):
    timestamp: float
    pid: int
    cpu_usage_percent: float
    memory_usage_mb: float
    io_wait_ms: int
    gil_contention_ms: int

class ZeroCopyTelemetryServer:
    """Manages the shared memory block on the daemon side for writing telemetry."""
    def __init__(self, name: str = SHM_NAME):
        self.name = name
        self.shm: Optional[shared_memory.SharedMemory] = None

    def initialize(self) -> None:
        try:
            self.shm = shared_memory.SharedMemory(name=self.name, create=True, size=STRUCT_SIZE)
            logger.info(f"Zero-copy telemetry shared memory initialized: {self.name}")
        except FileExistsError:
            logger.warning(f"Shared memory {self.name} already exists. Unlinking and recreating.")
            old_shm = shared_memory.SharedMemory(name=self.name)
            old_shm.unlink()
            old_shm.close()
            self.shm = shared_memory.SharedMemory(name=self.name, create=True, size=STRUCT_SIZE)

    def write_telemetry(self, data: TelemetryData) -> None:
        if not self.shm:
            return
        
        packed_data = struct.pack(
            STRUCT_FORMAT,
            data.timestamp,
            data.pid,
            data.cpu_usage_percent,
            data.memory_usage_mb,
            data.io_wait_ms,
            data.gil_contention_ms
        )
        self.shm.buf[:STRUCT_SIZE] = packed_data

    def cleanup(self) -> None:
        if self.shm:
            self.shm.close()
            try:
                self.shm.unlink()
            except FileNotFoundError:
                pass
            self.shm = None

class ZeroCopyTelemetryClient:
    """Reads the shared memory block on the UI side."""
    def __init__(self, name: str = SHM_NAME):
        self.name = name
        self.shm: Optional[shared_memory.SharedMemory] = None

    def connect(self) -> bool:
        if self.shm is not None:
            return True
        try:
            self.shm = shared_memory.SharedMemory(name=self.name, create=False)
            return True
        except FileNotFoundError:
            return False

    def read_telemetry(self) -> Optional[TelemetryData]:
        if not self.shm:
            if not self.connect():
                return None
        
        try:
            raw_data = self.shm.buf[:STRUCT_SIZE]
            unpacked = struct.unpack(STRUCT_FORMAT, raw_data)
            return TelemetryData(*unpacked)
        except struct.error:
            logger.error("Failed to unpack struct from shared memory")
            return None

    def disconnect(self) -> None:
        if self.shm:
            self.shm.close()
            self.shm = None
