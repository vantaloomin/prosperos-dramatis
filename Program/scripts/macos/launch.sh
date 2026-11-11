#!/bin/bash
# Starts Dramatis on http://127.0.0.1:8815 and opens it in the browser. Keep the window open; close it (or press
# Ctrl+C) to stop. Options: --port <n>, --no-browser.
. "$(dirname "${BASH_SOURCE[0]}")/common.sh"
cd "$DRAMATIS_ROOT" || exit 1

port="$DRAMATIS_PORT"
arguments=()
while [ $# -gt 0 ]; do
    case "$1" in
        --port) port="$2"; shift 2 ;;
        --no-browser) arguments+=(--no-browser); shift ;;
        *) say_error "Unknown option: $1"; exit 1 ;;
    esac
done
check_port "$port"

python="$DRAMATIS_ROOT/.venv/bin/python"
if [ ! -x "$python" ]; then say_error 'Dramatis is not installed yet. Double-click install.command first.'; exit 1; fi
if [ ! -f dist/index.html ]; then say_error 'The screen is not built. Double-click install.command first.'; exit 1; fi
dramatis_state "$port"
case "$STATE" in
    running)
        say_ok "Dramatis is already running on port $port."
        [ ${#arguments[@]} -eq 0 ] && open "http://127.0.0.1:$port/" 2>/dev/null
        exit 0 ;;
    foreign) say_error "Port $port belongs to another program (process $STATE_PID). Close it, or start Dramatis with --port."; exit 1 ;;
esac
exec "$python" -m dramatis --port "$port" ${arguments[@]+"${arguments[@]}"}
