#!/usr/bin/env bash
# ==============================================================================
# Synapse AOT Compilation Pipeline (Nuitka)
# Description: Compiles the Python source into a lean, self-contained native 
#              executable using Nuitka for maximum performance and minimum size.
# Author: Antigravity Architect
# Target: Linux (Native), macOS (Scaffold), Windows (Scaffold)
# ==============================================================================

# Strict Bash Pro patterns
set -Eeuo pipefail
trap 'echo "[ERROR] Compilation failed at line $LINENO: exit $?" >&2' ERR

# Define constants
SCRIPT_DIR="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd -P)"
PROJECT_ROOT="${SCRIPT_DIR}"
SRC_DIR="${PROJECT_ROOT}/src"
OUT_DIR="${PROJECT_ROOT}/dist"
MAIN_ENTRY="${PROJECT_ROOT}/run.py" # Use top-level run script to avoid module conflict

# Helper function for logging
log_info() {
  printf "\e[1;34m[INFO]\e[0m %s\n" "$*"
}

log_success() {
  printf "\e[1;32m[SUCCESS]\e[0m %s\n" "$*"
}

# Ensure we're in the project root
cd "$PROJECT_ROOT"

# Pre-flight checks
if [[ ! -f "$MAIN_ENTRY" ]]; then
  echo "[ERROR] Entry point $MAIN_ENTRY not found." >&2
  exit 1
fi

if ! command -v uv &> /dev/null; then
  echo "[ERROR] uv package manager is not installed." >&2
  exit 1
fi

# Detect platform for cross-platform scaffolding
OS="$(uname -s)"
OUTPUT_NAME="synapse"
NUITKA_PLATFORM_FLAGS=()

case "$OS" in
  Linux*)
    log_info "Configuring build for Linux Native..."
    # On Linux, standalone bundles .so files. 
    # Onefile can also be used if a single binary is desired, but standalone is better for size debugging.
    NUITKA_PLATFORM_FLAGS=(
      "--clang"
      "--include-package=uvloop"
    )
    ;;
  Darwin*)
    log_info "Configuring build for macOS (.app bundle)..."
    OUTPUT_NAME="Synapse"
    NUITKA_PLATFORM_FLAGS=(
      "--clang"
      "--macos-create-app-bundle"
      "--macos-app-name=Synapse"
      "--macos-app-mode=gui"
      "--include-package=uvloop"
    )
    ;;
  CYGWIN*|MINGW32*|MSYS*|MINGW*)
    log_info "Configuring build for Windows (.exe)..."
    OUTPUT_NAME="Synapse.exe"
    NUITKA_PLATFORM_FLAGS=(
      "--windows-console-mode=disable"
    )
    ;;
  *)
    echo "[ERROR] Unsupported OS: $OS" >&2
    exit 1
    ;;
esac

log_info "Cleaning previous build..."
rm -rf "$OUT_DIR"

log_info "Initializing Nuitka Compilation..."

# Execute Nuitka via uv to ensure we use the virtual environment's dependencies
# Rationale for flags:
# --standalone: Creates a self-contained directory with the executable and all shared libraries (no system python required).
# --lto=no: Link-Time Optimization is disabled for BRUTAL build speed. (Change to 'yes' only for final production releases).
# --clang: Forces the use of the Clang compiler, which compiles Nuitka's generated C code significantly faster than GCC/MSVC.
# --jobs: Maximizes parallel compilation using all available logical CPU cores.
# --nofollow-import-to: Aggressive static tree-shaking to prevent bloating the binary with unused standard libraries.
# --remove-output: Cleans up the massive C++ build cache after successful compilation to save disk space.
# --output-dir: Routes output cleanly to the dist/ folder.

# Dynamically get CPU core count for maximum parallelization
if command -v python3 &> /dev/null; then
  CORES=$(python3 -c 'import os; print(os.cpu_count() or 4)')
else
  CORES=4
fi

# BARE-METAL OPTIMIZATION: Extreme hardware-specific C-level optimization.
# -march=native: Unlock CPU specific extensions (AVX, BMI).
# -O3: Maximum performance.
if [[ "$OS" == "Linux"* ]]; then
  export CFLAGS="-march=native -O3 -fno-math-errno -fno-trapping-math -fomit-frame-pointer -pipe"
  export LDFLAGS="-fuse-ld=mold -Wl,-O3 -Wl,--as-needed -Wl,--gc-sections -s"
elif [[ "$OS" == "Darwin"* ]]; then
  export CFLAGS="-O3"
fi

uv run nuitka \
  --onefile \
  --lto=no \
  --jobs="$CORES" \
  --nofollow-import-to=tkinter \
  --nofollow-import-to=unittest \
  --nofollow-import-to=http \
  --nofollow-import-to=xmlrpc \
  --output-dir="$OUT_DIR" \
  --output-filename="$OUTPUT_NAME" \
  "${NUITKA_PLATFORM_FLAGS[@]}" \
  "$MAIN_ENTRY"

log_success "Compilation completed successfully!"
log_info "Binary is located in: $OUT_DIR/"
