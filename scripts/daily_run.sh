#!/usr/bin/env bash

# Orchestrates the daily update -> regenerate cycle:
#   update_prices_daily -> update_disclosure_daily -> update_index_data
#   -> run_daily_pipeline (which itself runs generate_features ->
#      generate_signals -> run_alpha_scoring [appends alpha_score_shadow_log.parquet,
#      v2 + shadow v1] -> ... -> run_meta_ranking -> build_cashflow_board,
#      regenerating the watchlist end to end).
#
# Best-effort, NOT fail-fast (no `set -e`): each step's own scripts are
# designed to be safe to run on stale/partial upstream data (soft-fail per
# symbol internally, see update_prices_daily.py/update_disclosure_daily.py),
# so a later step still has something useful to do even if an earlier one
# had problems -- this runner logs every step's outcome clearly instead of
# silently stopping, so a human reviewing logs/daily_run.log can see exactly
# what happened rather than an incomplete run with no explanation.
#
# Intended to run under a LaunchAgent (see PROJECT_STATE.md) or manually:
#   bash scripts/daily_run.sh

set -uo pipefail

PROJECT_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$PROJECT_ROOT"

# Absolute path, NOT a bare "python3" PATH lookup -- deliberate, do not
# revert. Confirmed root cause of the 2026-07-17 19:00 run (all 4 steps
# failed with ModuleNotFoundError for pandas/requests/yaml, see
# logs/daily_run.log): launchd's minimal environment does not inherit the
# interactive shell's PATH, so a bare "python3" resolved to the macOS
# system Python (/usr/bin/python3), which has none of this project's
# dependencies installed. Those are only installed in this anaconda3 base
# env (pinned exactly in requirements.txt: pandas==2.3.3, numpy==1.26.4,
# requests==2.32.3, PyYAML==6.0.2 -- verified matching this env, not the
# vnquant/vnstock-report envs, which have a different numpy). Hardcoding
# the absolute path makes this correct identically whether invoked via
# launchd (no inherited PATH) or an interactive shell (PATH order could
# vary) -- still overridable via PYTHON_BIN for local testing.
PYTHON_BIN="${PYTHON_BIN:-/opt/anaconda3/bin/python3}"
mkdir -p logs
LOG_FILE="logs/daily_run.log"
if [[ ! -x "$PYTHON_BIN" ]]; then
  echo "[$(date '+%Y-%m-%d %H:%M:%S')] ###### FAIL ###### PYTHON_BIN not found or not executable: $PYTHON_BIN -- see comment above this check in daily_run.sh" | tee -a "$LOG_FILE"
  exit 1
fi

_ts() { date '+%Y-%m-%d %H:%M:%S'; }

# Catch-up guard (NV2, LaunchAgent): the LaunchAgent plist sets both
# StartCalendarInterval (scheduled 19:00 weekdays) AND RunAtLoad=true (fires
# once whenever the agent loads, e.g. on login/boot). If the Mac was off/
# asleep through the scheduled time, RunAtLoad on the next login is what
# actually runs the catch-up -- but RunAtLoad also fires on every ordinary
# login even when today's scheduled run already completed fine, which would
# otherwise mean running twice a day. Guard: skip if today's date already
# has a "SUMMARY" line in the log (i.e. a run already finished today,
# success or fail) -- checking "the last mark in the log", not a separate
# state file, so the log stays the single source of truth. `--force`
# bypasses this for manual reruns/testing.
FORCE_RERUN=0
if [[ "${1:-}" == "--force" ]]; then
  FORCE_RERUN=1
fi
TODAY="$(date '+%Y-%m-%d')"
if [[ $FORCE_RERUN -eq 0 ]] && [[ -f "$LOG_FILE" ]] && grep -q "^\[$TODAY .*SUMMARY" "$LOG_FILE"; then
  echo "[$(_ts)] SKIP: a run already completed today ($TODAY) -- see logs/daily_run.log. Use --force to rerun anyway." | tee -a "$LOG_FILE"
  exit 0
fi

STEP_NAMES=()
STEP_STATUSES=()

run_step() {
  local name="$1"
  shift
  local start_ts end_ts dur exit_code out

  start_ts=$(date +%s)
  echo "[$(_ts)] START $name" | tee -a "$LOG_FILE"

  out="$("$@" 2>&1)"
  exit_code=$?

  end_ts=$(date +%s)
  dur=$((end_ts - start_ts))
  {
    echo "$out"
  } >> "$LOG_FILE"

  if [[ $exit_code -eq 0 ]]; then
    echo "[$(_ts)] OK   $name (${dur}s)" | tee -a "$LOG_FILE"
  else
    echo "[$(_ts)] ###### FAIL ###### $name (${dur}s, exit=$exit_code) -- see logs/daily_run.log for step output" | tee -a "$LOG_FILE"
  fi

  STEP_NAMES+=("$name")
  STEP_STATUSES+=("$exit_code")
}

{
  echo ""
  echo "======================================================================"
  echo "[$(_ts)] daily_run.sh starting"
} >> "$LOG_FILE"
echo "[$(_ts)] daily_run.sh starting (logs/daily_run.log)"

# Each step runs regardless of prior step outcomes -- see header comment.
run_step "update_prices_daily" "$PYTHON_BIN" scripts/update_prices_daily.py --universe
run_step "update_disclosure_daily" "$PYTHON_BIN" scripts/update_disclosure_daily.py --universe
run_step "update_index_data" "$PYTHON_BIN" scripts/update_index_data.py
run_step "run_daily_pipeline" "$PYTHON_BIN" scripts/run_daily_pipeline.py --offline

N_FAIL=0
FAILED_NAMES=()
for i in "${!STEP_NAMES[@]}"; do
  if [[ "${STEP_STATUSES[$i]}" -ne 0 ]]; then
    N_FAIL=$((N_FAIL + 1))
    FAILED_NAMES+=("${STEP_NAMES[$i]}")
  fi
done

if [[ $N_FAIL -eq 0 ]]; then
  echo "[$(_ts)] SUMMARY: ${#STEP_NAMES[@]}/${#STEP_NAMES[@]} steps OK" | tee -a "$LOG_FILE"
else
  echo "[$(_ts)] ###### SUMMARY: $N_FAIL/${#STEP_NAMES[@]} step(s) FAILED: ${FAILED_NAMES[*]} ######" | tee -a "$LOG_FILE"
fi

exit $N_FAIL
