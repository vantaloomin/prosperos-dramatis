#!/bin/bash
# For working on Dramatis: the server on 8815 in the background, and Vite with live reload on 5207 in front.
# Ctrl+C stops both. Option: --no-browser.
. "$(dirname "${BASH_SOURCE[0]}")/common.sh"
cd "$DRAMATIS_ROOT" || exit 1

fail() {
    say_error "Dev mode failed: $*"
    exit 1
}

python="$DRAMATIS_ROOT/.venv/bin/python"
[ -x "$python" ] || fail 'Dramatis is not installed yet. Double-click install.command first.'
[ -d node_modules ] || fail 'The screen packages are missing. Double-click install.command first.'
command -v npm >/dev/null 2>&1 || fail 'npm was not found. Double-click install.command first.'
[ -z "$(port_owner 5207)" ] || fail 'Port 5207 is in use, probably by another dev window. Close it and retry.'

backend=''
vite=''
cleanup() {
    [ -n "$vite" ] && stop_tree "$vite" 2>/dev/null
    if [ -n "$backend" ] && kill -0 "$backend" 2>/dev/null; then
        stop_tree "$backend"
        echo 'Stopped the Dramatis server.'
    fi
}
trap cleanup EXIT
trap 'exit 130' INT TERM HUP

dramatis_state "$DRAMATIS_PORT"
if [ "$STATE" = foreign ]; then
    fail "Port $DRAMATIS_PORT belongs to another program (process $STATE_PID). Nothing was stopped."
elif [ "$STATE" = running ]; then
    echo "Using the Dramatis server already running on $DRAMATIS_PORT."
else
    "$python" -m dramatis --no-browser &
    backend=$!
    wait_for_state running "$DRAMATIS_PORT" || fail "The server did not answer on $DRAMATIS_PORT; see above."
    echo "Server running on http://127.0.0.1:$DRAMATIS_PORT (process $backend); its log is in this window."
fi
echo 'Screen: http://127.0.0.1:5207 (reloads as you edit src/). Press Ctrl+C to stop.'
say_warn 'Dev mode uses your real library. python -m dramatis --stub gives a throwaway one with a stand-in model.'
# Vite runs in the background so a signal reaches this script's trap at once.
if [ "$1" = '--no-browser' ]; then npm run dev & else npm run dev -- --open & fi
vite=$!
wait "$vite"
