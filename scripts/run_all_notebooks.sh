#!/usr/bin/env bash

# Executes every active notebook in order (00_archive excluded).
# Notebook paths are resolved by glob so folder reorganizations cannot
# silently turn this runner into a no-op again (audit J1).

set -euo pipefail

PROJECT_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$PROJECT_ROOT"

TIMEOUT_SECONDS="${NOTEBOOK_TIMEOUT_SECONDS:-1800}"

# Resolve active notebooks: numbered folders except 00_archive, sorted by path.
# (while-read instead of mapfile: macOS ships bash 3.2)
NOTEBOOKS=()
while IFS= read -r nb; do
  NOTEBOOKS+=("$nb")
done < <(find notebooks -mindepth 2 -name "*.ipynb" \
  -not -path "notebooks/00_archive/*" \
  -not -path "*/.ipynb_checkpoints/*" | sort)

if [[ "${1:-}" == "--list" ]]; then
  printf '%s\n' "${NOTEBOOKS[@]}"
  exit 0
fi

if [[ ${#NOTEBOOKS[@]} -eq 0 ]]; then
  echo "[ERROR] No notebooks resolved under notebooks/ — check the repository layout." >&2
  exit 1
fi

run_notebook() {
  local notebook="$1"
  if [[ ! -f "$notebook" ]]; then
    echo "[ERROR] Missing notebook: $notebook" >&2
    exit 1
  fi

  echo
  echo "============================================================"
  echo "[RUN] $notebook"
  echo "============================================================"

  jupyter nbconvert \
    --to notebook \
    --execute "$notebook" \
    --inplace \
    --ExecutePreprocessor.timeout="$TIMEOUT_SECONDS"

  echo "[OK] $notebook"
}

RAN=0
if [[ $# -gt 0 ]]; then
  for notebook in "$@"; do
    run_notebook "$notebook"
    RAN=$((RAN + 1))
  done
else
  for notebook in "${NOTEBOOKS[@]}"; do
    run_notebook "$notebook"
    RAN=$((RAN + 1))
  done
fi

echo
echo "Executed $RAN notebook(s) successfully."
