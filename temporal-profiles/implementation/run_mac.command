#!/bin/sh
# Run the local demo with Python 3.8+; no installation or network access.

case "$0" in
    /*) PROFILE_LAUNCHER_PATH=$0 ;;
    *) PROFILE_LAUNCHER_PATH=$PWD/$0 ;;
esac
PROFILE_LAUNCHER_DIR=$(CDPATH= cd -P "$(dirname "$PROFILE_LAUNCHER_PATH")" && pwd)
if [ -z "$PROFILE_LAUNCHER_DIR" ] || ! cd "$PROFILE_LAUNCHER_DIR"; then
    printf '%s\n' 'Could not open the folder containing run_mac.command.' >&2
    exit 1
fi

PROFILE_EXIT_STATUS=0
if ! command -v python3 >/dev/null 2>&1; then
    printf '%s\n' 'Python 3.8 or newer is required. Install it, then run this launcher again.' >&2
    PROFILE_EXIT_STATUS=1
elif ! python3 -c 'import sys; raise SystemExit(0 if sys.version_info >= (3, 8) else 1)'; then
    printf '%s\n' 'The python3 command must run Python 3.8 or newer.' >&2
    PROFILE_EXIT_STATUS=1
else
    python3 demo.py
    PROFILE_EXIT_STATUS=$?
fi

if [ -t 0 ] && [ -t 1 ]; then
    printf '\nPress Return to close this window: '
    IFS= read -r PROFILE_LAUNCHER_REPLY || :
fi
exit "$PROFILE_EXIT_STATUS"
