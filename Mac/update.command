#!/bin/bash
# macOS: double-click in Finder, or run from Terminal. Pulls the latest main (or downloads it, in a copy that came as a ZIP), then installs again.
exec /bin/bash "$(dirname "$0")/../Program/scripts/macos/update.sh" "$@"
