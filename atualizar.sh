#!/usr/bin/env bash
# Atualiza o Painel Tekto (lê os repos privados via gh api e publica data.json).
set -euo pipefail
cd "$(dirname "$0")"
# Sincroniza com origin antes de gerar. data.json é gerado, então pode ser descartado.
git fetch --quiet origin main
git checkout --quiet -- data.json 2>/dev/null || true
if ! git rebase --quiet origin/main; then
  echo "ERRO: não foi possível sincronizar com origin/main (alterações locais?)." >&2
  git rebase --abort 2>/dev/null || true
  exit 1
fi
python3 gerar_dados.py "$@"
