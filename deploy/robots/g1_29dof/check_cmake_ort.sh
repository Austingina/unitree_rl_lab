#!/usr/bin/env bash
# Fail fast if CMakeLists.txt is an old copy (no aarch64 ONNX logic).
set -euo pipefail
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
CL="${SCRIPT_DIR}/CMakeLists.txt"
if [[ ! -f "$CL" ]]; then
  echo "ERROR: missing ${CL}"
  exit 1
fi
if ! grep -qF 'set(ONNXRUNTIME_ROOT "" CACHE PATH' "$CL" \
  || ! grep -qF 'ORT host cpu' "$CL"; then
  echo "ERROR: ${CL} is missing ONNX Runtime / aarch64 support."
  echo "Fix: update this file from your dev machine's unitree_rl_lab (same path), then run:"
  echo "  git pull   # or rsync/scp the file"
  echo "A correct configure prints: -- ORT host cpu: ... and -- ONNXRUNTIME_LIB=..."
  echo "If cmake warns 'ONNXRUNTIME_ROOT was not used', this file was not updated."
  exit 1
fi
echo "OK: ${CL} includes ONNX CACHE + ORT host detection."
