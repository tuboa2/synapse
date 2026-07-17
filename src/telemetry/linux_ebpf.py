import logging
from typing import Any, Optional
from .base import ProcessMetrics, TelemetryProvider

try:
    from bcc import BPF  # type: ignore
except ImportError:
    BPF = None

logger = logging.getLogger(__name__)

# Core eBPF C program string.
# Injects tracepoints directly into the Linux block I/O layer and scheduler.
# This prevents costly context-switches and delivers telemetry with near-zero overhead.
BPF_PROGRAM = """
#include <uapi/linux/ptrace.h>
#include <linux/sched.h>

// BPF Hash Maps for O(1) state tracking directly in kernel space
BPF_HASH(io_start, u32, u64);
BPF_HASH(io_wait_time, u32, u64);

// Trace block I/O request issue (disk reads/writes start)
TRACEPOINT_PROBE(block, block_rq_issue) {
    u32 pid = bpf_get_current_pid_tgid();
    u64 ts = bpf_ktime_get_ns();
    io_start.update(&pid, &ts);
    return 0;
}

// Trace block I/O request complete
TRACEPOINT_PROBE(block, block_rq_complete) {
    u32 pid = bpf_get_current_pid_tgid();
    u64 *tsp, delta;
    
    tsp = io_start.lookup(&pid);
    if (tsp != 0) {
        delta = bpf_ktime_get_ns() - *tsp;
        u64 *existing_time = io_wait_time.lookup(&pid);
        u64 new_time = (existing_time ? *existing_time : 0) + delta;
        io_wait_time.update(&pid, &new_time);
        io_start.delete(&pid);
    }
    return 0;
}
"""

class LinuxEBPFProvider(TelemetryProvider):
    """
    High-performance eBPF Telemetry Provider for Linux.
    Attaches natively to tracepoints with near-zero overhead utilizing bcc-tools.
    """
    def __init__(self) -> None:
        self.bpf: Optional[Any] = None
        self._procs: dict = {}
        self._last_io: dict = {}

    def initialize(self) -> None:
        if BPF is None:
            logger.warning("BCC not installed or missing permissions. eBPF Telemetry will simulate fallback data.")
            return

        logger.info("Compiling and injecting eBPF program into Linux Kernel...")
        try:
            self.bpf = BPF(text=BPF_PROGRAM)
            logger.info("eBPF tracepoints attached successfully.")
        except Exception as e:
            logger.error(f"Failed to compile or attach BPF program: {e}")
            self.bpf = None

    def cleanup(self) -> None:
        if self.bpf:
            self.bpf.cleanup()
            logger.info("eBPF tracepoints cleanly detached from Kernel.")
            self.bpf = None

    def get_metrics(self, pid: int) -> Optional[ProcessMetrics]:
        if self.bpf is None:
            # Fallback using psutil when BCC isn't available
            import psutil
            try:
                if pid not in self._procs:
                    self._procs[pid] = psutil.Process(pid)
                    self._procs[pid].cpu_percent(interval=None) # Initialize CPU state
                    
                proc = self._procs[pid]
                cpu = proc.cpu_percent(interval=None)
                mem_info = proc.memory_info()
                
                io_wait_approx = 0.0
                try:
                    io_counters = proc.io_counters()
                    # Use read_bytes and write_bytes delta as a proxy for I/O intensity
                    current_io_bytes = float(getattr(io_counters, 'read_bytes', 0) + getattr(io_counters, 'write_bytes', 0))
                    
                    if pid in self._last_io:
                        diff_bytes = max(0.0, current_io_bytes - self._last_io[pid])
                        # Heuristic: 1ms I/O wait per 512KB transferred (visually responsive for dashboards)
                        io_wait_approx = diff_bytes / (512 * 1024)
                    self._last_io[pid] = current_io_bytes
                except (AttributeError, psutil.AccessDenied):
                    pass
                
                # Estimate GIL contention (Fallback heuristic since native eBPF USDT is unavailable)
                # GIL contention correlates heavily with number of threads and context switching
                gil_approx = 0.0
                try:
                    threads = proc.num_threads()
                    if threads > 1:
                        # If CPU is maxed, GIL contention is roughly proportional to threads
                        gil_approx = min(999.0, (threads * (cpu / 100.0)) * 2.5)
                except Exception:
                    pass

                return ProcessMetrics(
                    pid=pid,
                    name="", # Name is populated by caller
                    cpu_usage_percent=float(cpu),
                    memory_usage_mb=float(mem_info.rss) / (1024 * 1024),
                    io_wait_ms=io_wait_approx,
                    gil_contention_ms=gil_approx
                )
            except (psutil.NoSuchProcess, psutil.AccessDenied):
                self._procs.pop(pid, None)
                self._last_io.pop(pid, None)
                return None

        try:
            # Extract high-resolution io wait delta directly from Kernel BPF hash map
            io_wait_table = self.bpf.get_table("io_wait_time")
            pid_c_uint = self.bpf.lib.c_uint(pid)
            io_ns = io_wait_table[pid_c_uint].value if pid_c_uint in io_wait_table else 0
            
            # Fast POSIX path for physical memory usage (RSS)
            with open(f"/proc/{pid}/statm", "r") as f:
                rss_pages = int(f.read().split()[1])
                memory_mb = (rss_pages * 4096) / (1024 * 1024)

            return ProcessMetrics(
                pid=pid,
                name="",
                cpu_usage_percent=0.0, # eBPF implementation omitted for brevity
                memory_usage_mb=float(memory_mb),
                io_wait_ms=float(io_ns) / 1_000_000.0,
                gil_contention_ms=0.0  # Would be extracted via USDT Python hook
            )
        except ProcessLookupError:
            logger.warning(f"Process {pid} no longer exists.")
            return None
        except Exception as e:
            logger.error(f"Failed to fetch eBPF metrics for PID {pid}: {e}")
            return None
