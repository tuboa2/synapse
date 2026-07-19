# Synapse ⚡

[![Python 3.12+](https://img.shields.io/badge/python-3.12+-blue.svg)](https://www.python.org/downloads/release/python-3120/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)
[![Code style: Ruff](https://img.shields.io/badge/code%20style-ruff-000000.svg)](https://github.com/astral-sh/ruff)
[![Type Checking: mypy](https://img.shields.io/badge/type%20checking-mypy-blue.svg)](https://mypy.readthedocs.io/en/stable/)
[![Build: Nuitka AOT](https://img.shields.io/badge/Build-Nuitka%20AOT-brightgreen.svg)](https://nuitka.net/)

> A cross-platform, extreme-performance Python daemon for local process telemetry.

Synapse is a local-first, zero-overhead performance telemetry application designed specifically for live Python environments. 

> [!IMPORTANT]
> **Beta Release Coming Soon:** I am currently stabilizing the core engine and AOT pipeline. Expect a comprehensive beta release in the near future!

---

## ✨ Architectural Highlights

- **Near-Zero Overhead Telemetry**: Implements an OS-aware abstract factory. On Linux, it injects custom C structures into Kernel **eBPF tracepoints** via `bcc-tools` to intercept block I/O without costly context switching. Fallbacks utilize `psutil` (Windows) and `DTrace` (macOS).
- **Declarative SQL-to-Tracepoint Transpiler**: Write DuckDB-dialect SQL queries to declaratively extract telemetry. Synapse parses, validates, and transpiles the SQL directly into secure eBPF C-code hook configurations in a <15ms 4-stage pipeline.
- **Sub-50ms Terminal UI**: The frontend is a lightweight asyncio-driven CLI that renders instantly without graphical overhead.
- **Asynchronous IPC**: The CLI and the background daemon run in entirely separate processes. They communicate via a strictly non-blocking Unix Domain Socket (`asyncio`), ensuring responsiveness regardless of backend load.
- **Embedded Analytical Datastore**: Leverages **DuckDB** for lightning-fast, SQL-driven telemetry aggregation and historical time-series analytics within the daemon.
- **AOT Native Compilation**: Distributed not as a Python script, but as a heavily tree-shaken, standalone native C++ executable via **Nuitka**.

---

## 🏗️ System Architecture

```mermaid
graph TD
    subgraph CLI Process
        CLI[Terminal UI]
        CLI <-->|Asyncio loop| IPC_W[IPC Worker]
    end

    subgraph IPC Layer
        IPC_W <-->|JSON over Unix Socket| UDS((Unix Domain Socket))
    end

    subgraph Daemon Process
        UDS <-->|Async Event Loop| D[Daemon Loop]
        D -->|Store| DB[(DuckDB)]
        
        subgraph Transpiler Pipeline
            D -->|SQL Query| Parser[AST Parser]
            Parser --> Validator[Schema Validator]
            Validator --> Mapper[AST Mapper]
            Mapper --> Emitter[Code Emitter]
        end
        
        subgraph Telemetry Interface
            Emitter -->|Generated Code| TF[Telemetry Factory]
            TF -->|Linux| eBPF[eBPF / BCC]
            TF -->|macOS| DTrace[DTrace]
            TF -->|Windows| WMI[WMI / psutil]
        end
    end
    
    style CLI fill:#2d3436,stroke:#00b894,stroke-width:2px,color:#fff
    style D fill:#2d3436,stroke:#0984e3,stroke-width:2px,color:#fff
    style UDS fill:#b2bec3,stroke:#636e72,stroke-width:2px
```

## 📂 Domain Structure

```text
src/
├── cli/             # Terminal-based CLI UI
├── daemon/          # Background daemon and asyncio event loop orchestration
├── transpiler/      # 4-stage SQL-to-eBPF transpilation engine
├── telemetry/       # Abstracted OS telemetry instrumentation (eBPF, WMI, DTrace)
├── ipc/             # Decoupled Unix socket servers and clients
└── domain/          # DuckDB datastores and immutable domain data models
```

---

## 🚀 Getting Started

### Prerequisites

- **Python 3.12+**
- **[uv](https://github.com/astral-sh/uv)** (Extremely fast Python package installer and resolver)

### Local Development Setup

1. **Clone & Initialize**
   ```bash
   git clone https://github.com/tuboa2/synapse.git
   cd synapse
   uv venv
   source .venv/bin/activate
   ```

2. **Install Dependencies**
   ```bash
   uv sync
   ```

3. **Code Quality & Validation**
   Synapse enforces rigorous CI/CD constraints locally:
   ```bash
   uv run ruff check src     # Linting
   uv run ruff format src    # Formatting
   uv run mypy src           # Strict Static Type Checking
   ```

---

## 🔨 AOT Compilation (Nuitka)

To showcase extreme technical optimization, Synapse abandons standard Python distribution in favor of an **Ahead-Of-Time (AOT) C++ compilation pipeline**. 

This strips the Python interpreter and unused standard libraries entirely, producing a lean, standalone native binary.

1. Review the defensive compilation script:
   ```bash
   cat build.sh
   ```
2. Execute the build pipeline:
   ```bash
   ./build.sh
   ```
3. Locate your compiled binary in the `dist/` directory.

---

## 📜 License

This project is licensed under the MIT License - see the LICENSE file for details. Built strictly as a technical portfolio demonstration.
