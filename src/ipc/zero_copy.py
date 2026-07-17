import struct
from multiprocessing import shared_memory
from typing import Optional, NamedTuple, List
import logging

logger = logging.getLogger(__name__)

# Struct layout for a single process:
# double timestamp (8 bytes)
# uint32 pid (4 bytes)
# char[] name (32 bytes)
# float cpu_usage_percent (4 bytes)
# float memory_usage_mb (4 bytes)
# uint32 io_wait_ms (4 bytes)
# uint32 gil_contention_ms (4 bytes)
# Total size: 60 bytes

MAX_PROCESSES = 64
HEADER_FORMAT = 'I' # uint32 count
ITEM_FORMAT = 'dI32sffII'

HEADER_SIZE = struct.calcsize(HEADER_FORMAT)
ITEM_SIZE = struct.calcsize(ITEM_FORMAT)
STRUCT_SIZE = HEADER_SIZE + (MAX_PROCESSES * ITEM_SIZE)
SHM_NAME = "synapse_telemetry_shm"

class TelemetryData(NamedTuple):
    timestamp: float
    pid: int
    name: str
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

    def write_telemetry(self, data_list: List[TelemetryData]) -> None:
        if not self.shm:
            return
        
        # Cap to MAX_PROCESSES
        data_list = data_list[:MAX_PROCESSES]
        count = len(data_list)
        
        # Pack header (count)
        self.shm.buf[:HEADER_SIZE] = struct.pack(HEADER_FORMAT, count)
        
        # Pack items
        offset = HEADER_SIZE
        for data in data_list:
            name_encoded = data.name.encode('utf-8')[:31].ljust(32, b'\x00')
            packed_data = struct.pack(
                ITEM_FORMAT,
                data.timestamp,
                data.pid,
                name_encoded,
                data.cpu_usage_percent,
                data.memory_usage_mb,
                data.io_wait_ms,
                data.gil_contention_ms
            )
            self.shm.buf[offset:offset+ITEM_SIZE] = packed_data
            offset += ITEM_SIZE

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

    def read_telemetry(self) -> List[TelemetryData]:
        if not self.shm:
            if not self.connect():
                return []
        
        try:
            raw_header = self.shm.buf[:HEADER_SIZE]
            count = struct.unpack(HEADER_FORMAT, raw_header)[0]
            
            # Sanity check count
            if count > MAX_PROCESSES or count < 0:
                return []
                
            results = []
            offset = HEADER_SIZE
            for _ in range(count):
                raw_item = self.shm.buf[offset:offset+ITEM_SIZE]
                unpacked = struct.unpack(ITEM_FORMAT, raw_item)
                
                name_str = unpacked[2].decode('utf-8', errors='ignore').rstrip('\x00')
                results.append(TelemetryData(
                    timestamp=unpacked[0],
                    pid=unpacked[1],
                    name=name_str,
                    cpu_usage_percent=unpacked[3],
                    memory_usage_mb=unpacked[4],
                    io_wait_ms=unpacked[5],
                    gil_contention_ms=unpacked[6]
                ))
                offset += ITEM_SIZE
                
            return results
        except struct.error:
            logger.error("Failed to unpack struct from shared memory")
            return []

    def disconnect(self) -> None:
        if self.shm:
            self.shm.close()
            self.shm = None
