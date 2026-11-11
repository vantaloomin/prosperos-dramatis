#!/bin/bash
# macOS: double-click in Finder, or run from Terminal. For working on Dramatis: the server on 8815 and Vite with live reload on 5207.
exec /bin/bash "$(dirname "$0")/../Program/scripts/macos/dev.sh" "$@"
