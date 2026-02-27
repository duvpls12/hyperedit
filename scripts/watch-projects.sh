#!/bin/bash
# Watch for new brief.json files in hyperedit-studio projects
# Triggers Claude CLI processing when a new project appears
# Usage:
#   Run directly:       bash scripts/watch-projects.sh
#   Background daemon:  launchctl load ~/Library/LaunchAgents/com.worldclass.hyperedit-watcher.plist

WATCH_DIR="/Volumes/Charlie/hyperedit-studio/projects"
LOG_FILE="$HOME/Library/Logs/hyperedit-watcher.log"

log() {
  echo "[$(date '+%Y-%m-%d %H:%M:%S')] $*" | tee -a "$LOG_FILE"
}

if [ ! -d "$WATCH_DIR" ]; then
  log "ERROR: Watch directory not found: $WATCH_DIR"
  log "Is the Charlie drive mounted?"
  exit 1
fi

if ! command -v fswatch &>/dev/null; then
  log "ERROR: fswatch not installed. Run: brew install fswatch"
  exit 1
fi

log "HyperEdit project watcher started. Monitoring: $WATCH_DIR"

fswatch -0 --event Created "$WATCH_DIR" | while IFS= read -r -d '' file; do
  if [[ "$file" == */brief.json ]]; then
    PROJECT_DIR=$(dirname "$file")
    LEDGER="$PROJECT_DIR/run-ledger.json"

    if [ -f "$LEDGER" ]; then
      log "Skipping already-processed project: $PROJECT_DIR"
      continue
    fi

    log "New project detected: $PROJECT_DIR"
    log "Triggering Claude pipeline..."

    claude -p "Process the HyperEdit project at $PROJECT_DIR. Run /hyperedit-orchestrator to start the pipeline." \
      >> "$LOG_FILE" 2>&1 &

    log "Claude pipeline launched (PID $!)"
  fi
done
