# Synapse Documentation

> A comprehensive technical overview of the Synapse extreme-performance Python daemon.

---

## 1. Executive Summary

Synapse is a local-first, zero-overhead performance telemetry application designed specifically for live Python environments. It provides real-time visibility into process behavior—such as CPU usage, memory consumption, block I/O wait times, and GIL contention—without the performance penalty associated with traditional monitoring tools. 

Synapse achieves extreme performance by injecting custom C structures directly into the OS kernel (via eBPF on Linux) and orchestrating telemetry aggregation completely decoupled from the terminal UI. It is distributed as a heavily tree-shaken, standalone native C++ executable via Nuitka AOT compilation.

---

## 2. Core Architecture

Synapse's architecture relies on strict process isolation. The system is split into two primary asynchronous components that communicate over a non-blocking IPC layer.

### 2.1 Decoupled Process Model

*   **CLI Process (`src/cli/`)**: A lightweight, `asyncio`-driven frontend terminal UI. It connects to the daemon via IPC, fetching aggregated telemetry metrics and rendering them in under 50ms without graphical overhead.
*   **Daemon Process (`src/daemon/`)**: A background orchestrator that continuously discovers Python processes, aggregates telemetry data via kernel-level or fallback sensors, and maintains an in-memory SQL datastore.
*   **IPC Layer (`src/ipc/`)**: Communication between the CLI and Daemon is handled through two distinct channels:
    *   **Unix Domain Socket (`unix_socket.py`)**: Handles command-and-control messages (e.g., `ping`, `get_telemetry`).
    *   **Zero-Copy Shared Memory (`zero_copy.py`)**: Uses Python's `multiprocessing.shared_memory` to stream structured telemetry structures instantly between processes without serialization overhead.

### 2.2 In-Memory Datastore

Synapse utilizes **DuckDB** (`src/domain/database.py`) as an embedded, analytical datastore for telemetry aggregation and historical time-series analytics. To ensure DuckDB does not block the daemon's asynchronous event loop, all database queries and inserts are executed asynchronously within a `ThreadPoolExecutor` (`max_workers=1`).

---

## 3. Telemetry Engine

The telemetry engine (`src/telemetry/`) abstracts platform-specific monitoring capabilities, defaulting to the highest-performance instrumentation available.

### 3.1 Linux eBPF (`linux_ebpf.py`)
On Linux, Synapse provides true near-zero overhead by injecting eBPF C programs via `bcc-tools`. 
*   **Block I/O Tracing**: It hooks directly into the Linux block I/O layer (`block_rq_issue` and `block_rq_complete` tracepoints). 
*   **Kernel Hash Maps**: I/O wait times are calculated entirely in kernel-space using BPF hash maps (`io_start`, `io_wait_time`), extracting high-resolution metrics to user-space in O(1) time without context-switch penalties.

### 3.2 Fallback Heuristics
If eBPF or root permissions are unavailable, Synapse safely falls back to a simulated approximation using `psutil`. It calculates I/O intensity by mapping disk read/write byte deltas, and approximates GIL contention using CPU saturation relative to the process thread count.

### 3.3 macOS and Windows
Synapse defines interfaces for macOS (`DTrace`) and Windows (`WMI`/`psutil`), allowing native telemetry adapters to be injected based on the detected operating system.

---

## 4. Declarative SQL-to-Tracepoint Transpiler

One of Synapse's most powerful features is its ability to transpile declarative SQL queries (in the DuckDB dialect) directly into low-level kernel configurations (eBPF C code, DTrace scripts).

The transpilation engine (`src/transpiler/`) runs a strict 4-stage pipeline in under 15ms:

1.  **Parse (`sqlglot`)**: The SQL query is parsed into an Abstract Syntax Tree (AST) using `sqlglot`.
2.  **Validate (`validator.py`)**: The AST is validated against `schema_registry.json`. This schema enforces data types and whitelist aggregation functions (e.g., `COUNT`, `SUM`, `AVG`, `MIN`, `MAX`) for target tables like `syscalls` and `tcp_events`.
3.  **Map (`mapper.py`)**: The validated AST is cross-referenced with `tracepoint_matrix.json`. The matrix maps logical table columns to physical OS-level tracepoints (e.g., `raw_syscalls:sys_enter`), physical C-struct fields (e.g., `bpf_get_current_pid_tgid()`), and specific probe types based on the platform (`linux`, `macos`).
4.  **Emit (`emitter.py`)**: Finally, the code emitter translates the mapped query into an executable string using a platform-specific CodeGenerator (e.g., `eBPFGenerator`, `DTraceGenerator`).

> **Example**: You can test the transpiler directly via the CLI:
> `python -m cli.main --query "SELECT pid, comm, MAX(latency_us) FROM syscalls WHERE pid = 123"`

---

## 5. Directory & Module Reference

```text
src/
├── cli/             # Terminal-based CLI UI
│   └── main.py      # Entry point for the frontend; handles rendering and CLI arguments.
├── daemon/          # Background daemon and asyncio event loop orchestration
│   ├── main.py      # Daemon event loop, telemetry aggregation, and IPC server.
│   └── discovery.py # Python process discovery utilities.
├── domain/          # DuckDB datastores and immutable domain data models
│   └── database.py  # DuckDB ThreadPool wrapper for async non-blocking operations.
├── ipc/             # Decoupled Unix socket servers and clients
│   ├── base.py      # IPC interfaces.
│   ├── unix_socket.py # JSON-over-socket implementation for commands.
│   └── zero_copy.py # Shared memory telemetry struct implementation.
├── telemetry/       # Abstracted OS telemetry instrumentation
│   ├── base.py      # Telemetry interfaces and ProcessMetrics dataclass.
│   ├── factory.py   # Factory to provision the correct OS telemetry provider.
│   ├── linux_ebpf.py # BCC eBPF implementation utilizing kernel tracepoints.
│   ├── macos_dtrace.py # DTrace adapter stub.
│   └── windows_wmi.py # Windows WMI adapter stub.
├── transpiler/      # 4-stage SQL-to-eBPF transpilation engine
│   ├── codegen/     # Code emitters for eBPF, DTrace, and Windows.
│   ├── mapper.py    # Maps SQL AST to physical tracepoint structures.
│   ├── validator.py # Schema validation using schema_registry.json.
│   └── emitter.py   # Code generation orchestrator.
├── schema_registry.json   # SQL logical schema definition (tables, fields, functions).
└── tracepoint_matrix.json # OS tracepoint mapping matrix for the mapper pipeline.
```

---

## 6. AOT Compilation

Synapse uses **Nuitka** to compile the Python source code into an Ahead-Of-Time (AOT) C++ executable. This pipeline drops the Python interpreter footprint, resulting in a highly optimized binary with near-instant startup times. 

The build pipeline is automated via `build.sh`, depositing the finalized native binary into the `dist/` directory.

---

## 7. Development and CI/CD

Synapse employs modern Python tooling and enforces strict checks during development:
*   **Package Manager**: `uv` is used for ultra-fast dependency resolution and virtual environments.
*   **Linting & Formatting**: `ruff` guarantees consistent code style and catches common errors.
*   **Type Checking**: `mypy` is aggressively utilized for static analysis to ensure memory and type safety across the IPC and Transpiler layers.
