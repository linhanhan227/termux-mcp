#!/usr/bin/env sh
set -eu

SCRIPT_DIR=$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)
WHEELHOUSE=${WHEELHOUSE:-"$SCRIPT_DIR/wheelhouse"}

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

if [ ! -d "$WHEELHOUSE" ]; then
  echo "wheelhouse not found: $WHEELHOUSE" >&2
  exit 1
fi

first_whl=$(find "$WHEELHOUSE" -maxdepth 1 -type f -name '*.whl' | sed -n '1p')
if [ -z "$first_whl" ]; then
  echo "no .whl files found in: $WHEELHOUSE" >&2
  exit 1
fi

if [ "$#" -gt 0 ]; then
  "$PYTHON" -m pip install --no-index --find-links "$WHEELHOUSE" "$@"
else
  find "$WHEELHOUSE" -maxdepth 1 -type f -name '*.whl' -print0 \
    | xargs -0 "$PYTHON" -m pip install --no-index --find-links "$WHEELHOUSE"
fi
