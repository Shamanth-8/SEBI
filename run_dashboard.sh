#!/usr/bin/env bash
# Runs the dashboard and records WHY it stopped, so a crash leaves evidence
# instead of just a closed terminal.
cd "$(dirname "$0")"
LOG="streamlit_crash.log"

echo "=== started $(date) ===" >> "$LOG"
free -m | head -2 >> "$LOG"

./venv/bin/streamlit run frontend/dashboard.py --server.port 8501 2>&1 | tee -a "$LOG"
code=${PIPESTATUS[0]}

echo "=== exited $(date) with code $code ===" >> "$LOG"
case $code in
  0)   echo "clean exit (you pressed Ctrl-C or closed it)" | tee -a "$LOG" ;;
  137) echo "KILLED (SIGKILL) — this is the OOM killer. Free memory." | tee -a "$LOG" ;;
  139) echo "SEGFAULT — a native library crashed. Send me streamlit_crash.log." | tee -a "$LOG" ;;
  143) echo "terminated (SIGTERM)" | tee -a "$LOG" ;;
  *)   echo "exited with code $code" | tee -a "$LOG" ;;
esac
free -m | head -2 >> "$LOG"
journalctl --since "2 min ago" 2>/dev/null | grep -iE "oom|killed process" | tail -3 >> "$LOG"
