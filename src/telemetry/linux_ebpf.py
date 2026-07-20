import logging
import asyncio
import json
import os
import ctypes as ct
from typing import Any, Optional
from .base import ProcessMetrics, TelemetryProvider
import sqlglot

from transpiler.validator import ASTValidator
from transpiler.mapper import ASTMapper
from transpiler.emitter import QueryEmitter

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
        self._custom_metrics: dict = {}
        self._loop = None
        self._fd = None

    def initialize(self, query: Optional[str] = None) -> None:
        if BPF is None:
            logger.warning("BCC not installed or missing permissions. eBPF Telemetry will simulate fallback data.")
            return

        bpf_text = BPF_PROGRAM
        
        if query:
            logger.info("Custom query provided. Transpiling to eBPF...")
            try:
                base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
                schema_path = os.path.join(base_dir, "schema_registry.json")
                matrix_path = os.path.join(base_dir, "tracepoint_matrix.json")
                
                with open(schema_path, "r") as f:
                    schema = json.load(f)
                with open(matrix_path, "r") as f:
                    matrix = json.load(f)
                
                ast = sqlglot.parse_one(query, dialect="duckdb")
                ASTValidator(schema).validate(ast)
                mapped_query = ASTMapper(matrix, platform="linux").map(ast)
                bpf_text = QueryEmitter().emit(mapped_query)
                logger.info("Transpilation successful.")
            except Exception as e:
                logger.error(f"Transpilation failed: {e}. Falling back to default program.")

        logger.info("Compiling and injecting eBPF program into Linux Kernel...")
        try:
            self.bpf = BPF(text=bpf_text)
            logger.info("eBPF tracepoints attached successfully.")
            
            if query and "events" in self.bpf:
                # Custom query transpiler uses BPF_PERF_OUTPUT("events")
                self.bpf["events"].open_perf_buffer(self._handle_perf_event)
                self._fd = self.bpf.perf_buffer_poll_fd()
                self._loop = asyncio.get_running_loop()
                self._loop.add_reader(self._fd, self._poll_perf_buffers)
        except Exception as e:
            logger.error(f"Failed to compile or attach BPF program: {e}")
            self.bpf = None

    def _handle_perf_event(self, cpu: int, data: Any, size: int) -> None:
        # Assuming event_t struct matches the transpiler's layout
        # struct event_t { u64 pid; char comm[64]; u64 latency_us; };
        class Event(ct.Structure):
            _fields_ = [
                ("pid", ct.c_uint64),
                ("comm", ct.c_char * 64),
                ("latency_us", ct.c_uint64)
            ]
        event = ct.cast(data, ct.POINTER(Event)).contents
        pid = int(event.pid)
        self._custom_metrics[pid] = {
            "comm": event.comm.decode('utf-8', 'replace'),
            "latency_us": float(event.latency_us)
        }

    def _poll_perf_buffers(self) -> None:
        if self.bpf:
            self.bpf.perf_buffer_poll(timeout=0)

    def cleanup(self) -> None:
        if self._loop and self._fd:
            self._loop.remove_reader(self._fd)
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
            # Check if we have custom metrics from the transpiler's perf buffer
            custom = self._custom_metrics.pop(pid, None)
            io_ns = 0
            if custom:
                # Use custom latency from perf buffer if available
                io_ns = custom["latency_us"] * 1000.0  # Convert to ns for consistency
            else:
                # Extract high-resolution io wait delta directly from Kernel BPF hash map
                try:
                    io_wait_table = self.bpf.get_table("io_wait_time")
                    pid_c_uint = self.bpf.lib.c_uint(pid)
                    io_ns = io_wait_table[pid_c_uint].value if pid_c_uint in io_wait_table else 0
                except KeyError:
                    pass # Custom program might not have io_wait_time map
            
            # Fast POSIX path for physical memory usage (RSS)
            with open(f"/proc/{pid}/statm", "r") as f:
                rss_pages = int(f.read().split()[1])
                memory_mb = (rss_pages * 4096) / (1024 * 1024)

            return ProcessMetrics(
                pid=pid,
                name=custom["comm"] if custom else "",
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
