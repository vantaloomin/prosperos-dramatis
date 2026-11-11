#!/bin/bash
# Stops a running Dramatis, and only that: another program on the port is never touched. Option: --port <n>.
. "$(dirname "${BASH_SOURCE[0]}")/common.sh"
port="$DRAMATIS_PORT"
[ "$1" = '--port' ] && port="$2"
check_port "$port"
dramatis_state "$port"
case "$STATE" in
    stopped) echo 'Dramatis is not running. Nothing to stop.'; exit 0 ;;
    foreign) say_error "Stop failed: port $port belongs to another program (process $STATE_PID). Nothing was stopped."; exit 1 ;;
esac
if [ -z "$STATE_PID" ]; then
    say_error 'Stop failed: Dramatis answers, but its process could not be found. Close its window instead.'
    exit 1
fi
pid="$STATE_PID"
stop_tree "$pid"
# Every save is a whole file written at once, so a stop never leaves half a character; force it after ten seconds.
if ! wait_for_state stopped "$port" 40; then
    kill -9 "$pid" 2>/dev/null
    wait_for_state stopped "$port" 20 || { say_error "Stop failed: process $pid did not stop."; exit 1; }
fi
say_ok 'Stopped Dramatis. launch.command starts it again.'
