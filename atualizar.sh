#!/usr/bin/env bash
# Atualiza o painel do Tekto Calc (lê o repo privado via gh api e publica data.json).
set -euo pipefail
cd "$(dirname "$0")"
git pull --quiet --rebase origin main 2>/dev/null || true
python3 gerar_dados.py "$@"
