#!/usr/bin/env sh
set -eu

DIR=$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)
cd "$DIR"

find_system_python() {
  if [ -n "${PYTHON:-}" ]; then
    printf '%s\n' "$PYTHON"
    return
  fi

  for candidate in \
    /data/data/com.termux/files/usr/bin/python \
    /usr/bin/python3 \
    /usr/local/bin/python3 \
    /usr/bin/python \
    /usr/local/bin/python
  do
    if [ -x "$candidate" ]; then
      printf '%s\n' "$candidate"
      return
    fi
  done

  if command -v python3 >/dev/null 2>&1; then
    command -v python3
    return
  fi
  if command -v python >/dev/null 2>&1; then
    command -v python
    return
  fi

  echo "system python not found" >&2
  exit 1
}

PYTHON=$(find_system_python)
"$PYTHON" - <<'PY'
import sys

if sys.prefix != sys.base_prefix or hasattr(sys, "real_prefix"):
    raise SystemExit("refusing to install into a virtual environment; set PYTHON to the system Python executable")
PY

"$PYTHON" -m pip install --no-index --find-links ./wheelhouse -r requirements.txt
