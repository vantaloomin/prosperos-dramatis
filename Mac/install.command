#!/bin/bash
# macOS: double-click in Finder, or run from Terminal. Finds or installs Python 3.12+ and Node.js 22.13+, installs the locked dependencies and builds the screen.
exec /bin/bash "$(dirname "$0")/../Program/scripts/macos/install.sh" "$@"
