#!/usr/bin/env bash
# Runs once, the first time the container is created, as the `vscode` user.
set -euo pipefail

echo "==> Fixing cache volume ownership"
# The named volume is owned by root on first mount; chown so uv can write.
sudo chown -R "$(id -u):$(id -g)" "$HOME/.cache/uv" 2>/dev/null || true
sudo chown -R "$(id -u):$(id -g)" "$HOME/.cache/uv" /usr/local/uv 2>/dev/null || true

echo "==> Trusting the workspace for git"
# Docker Desktop's bind-mount layer can make the workspace look owned by a
# different uid than git expects, even though it isn't -- git then refuses to
# operate on it as "dubious ownership". Single-user container, so trust it all.
git config --global --add safe.directory '*'

if [ -f pyproject.toml ]; then
    echo "==> Syncing project dependencies"
    uv sync
else
    echo "==> No pyproject.toml found, skipping uv sync"
fi

echo "==> Installing dcode (Deep Agents Code) with Fireworks integration"
DEEPAGENTS_CODE_EXTRAS="fireworks" curl -LsSf https://langch.in/dcode | bash

echo "==> Done."
