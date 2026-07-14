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
MAIN_ENTRY="${SRC_DIR}/ui/main.py" # Or the combined entrypoint depending on target

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
      # "--linux-icon=assets/icon.png" # Scaffolded
    )
    ;;
  Darwin*)
    log_info "Configuring build for macOS (.app bundle)..."
    OUTPUT_NAME="Synapse"
    NUITKA_PLATFORM_FLAGS=(
      "--macos-create-app-bundle"
      "--macos-app-name=Synapse"
      "--macos-app-mode=gui"
    )
    ;;
  CYGWIN*|MINGW32*|MSYS*|MINGW*)
    log_info "Configuring build for Windows (.exe)..."
    OUTPUT_NAME="Synapse.exe"
    NUITKA_PLATFORM_FLAGS=(
      "--windows-console-mode=disable"
      "--windows-icon-from-ico=assets/icon.ico"
    )
    ;;
  *)
    echo "[ERROR] Unsupported OS: $OS" >&2
    exit 1
    ;;
esac

log_info "Initializing Nuitka Compilation..."

# Execute Nuitka via uv to ensure we use the virtual environment's dependencies
# Rationale for flags:
# --standalone: Creates a self-contained directory with the executable and all shared libraries (no system python required).
# --lto=yes: Link-Time Optimization. Crucial for C++ compilation, it allows the compiler to inline code across translation units, reducing binary size and increasing execution speed.
# --enable-plugin=pyside6: Specifically hooks into PySide6 to bundle Qt QML/C++ libraries correctly.
# --nofollow-import-to: Aggressive static tree-shaking to prevent bloating the binary with unused standard libraries (e.g., tkinter, unittest, email).
# --remove-output: Cleans up the massive C++ build cache after successful compilation to save disk space.
# --output-dir: Routes output cleanly to the dist/ folder.

uv run nuitka \
  --standalone \
  --lto=yes \
  --enable-plugin=pyside6 \
  --nofollow-import-to=tkinter \
  --nofollow-import-to=unittest \
  --nofollow-import-to=email \
  --nofollow-import-to=http \
  --nofollow-import-to=xmlrpc \
  --output-dir="$OUT_DIR" \
  --remove-output \
  --output-filename="$OUTPUT_NAME" \
  "${NUITKA_PLATFORM_FLAGS[@]}" \
  "$MAIN_ENTRY"

log_success "Compilation completed successfully!"
log_info "Binary is located in: $OUT_DIR/"
