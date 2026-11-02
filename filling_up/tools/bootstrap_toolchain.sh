#!/usr/bin/env bash
# Reproduce the locked toolchain into filling_up/.toolchain and filling_up/.venv (see toolchain.lock.json).
set -euo pipefail
cd "$(dirname "$0")/.."
cargo install --locked --root .toolchain rojo --version 7.5.1
cargo install --locked --root .toolchain lune --version 0.10.1
cargo install --locked --root .toolchain stylua --version 2.1.0 --features luau
cargo install --locked --root .toolchain selene --version 0.28.0 --no-default-features --features roblox
python3 -m venv .venv
.venv/bin/pip install bpy==5.2.3
python3 tools/preflight.py
