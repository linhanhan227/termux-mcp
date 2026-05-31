#!/usr/bin/env sh
set -eu

SCRIPT_DIR=$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)

WHEELHOUSE=${WHEELHOUSE:-}
REQUIREMENTS=${REQUIREMENTS:-}
OFFLINE_ARCHIVE=${OFFLINE_ARCHIVE:-}
EXTRACT_DIR=${EXTRACT_DIR:-"$SCRIPT_DIR/.termux-offline-pip"}
PYTHON=${PYTHON:-}
RUN_CMD=${RUN_CMD:-}
RUN_MODULE=${RUN_MODULE:-mcp_toolkit.server}
SKIP_PYTHON_INSTALL=${SKIP_PYTHON_INSTALL:-0}
PKG_UPDATE=${PKG_UPDATE:-1}
ENV_FILE=${ENV_FILE:-${MCP_ENV_FILE:-"$SCRIPT_DIR/.termux-mcp.env"}}
NO_ENV_PROMPT=${NO_ENV_PROMPT:-0}
SAVE_ENV=${SAVE_ENV:-1}
NO_RUN=0
INSTALL_ALL_WHEELS=0

usage() {
  cat <<'EOF'
用法:
  ./termux-install.sh [选项]

功能:
  在 Termux 中安装 Python，从本地 wheelhouse 离线安装 pip 包，
  提示填写运行环境变量，然后启动程序。

选项:
  --wheelhouse DIR          指定包含 *.whl 文件的本地目录。
  --requirements FILE      指定离线安装用的 requirements 文件。
  --archive FILE           指定离线 tar.gz 包；没有 wheelhouse 时会解压它。
  --extract-dir DIR        指定 --archive 的解压目录。
  --python PATH            指定 Python 可执行文件。
  --run "COMMAND"          安装完成后运行指定命令。
  --run-module MODULE      安装完成后运行指定 Python 模块。
  --env-file FILE          指定运行环境变量的读取/保存文件。
  --no-env-prompt          不提示填写运行环境变量。
  --no-save-env            不把填写的变量保存到 --env-file。
  --install-all-wheels     安装 wheelhouse 中的所有 wheel，而不是按 requirements 安装。
  --no-run                 只安装，不运行程序。
  --skip-python-install    找不到 Python 时直接失败，不调用 pkg install。
  --no-pkg-update          安装 Python 前跳过 pkg update。
  -h, --help               显示帮助。

可通过环境变量覆盖:
  WHEELHOUSE, REQUIREMENTS, OFFLINE_ARCHIVE, EXTRACT_DIR, PYTHON, RUN_CMD,
  RUN_MODULE, ENV_FILE, NO_ENV_PROMPT, SAVE_ENV, SKIP_PYTHON_INSTALL,
  PKG_UPDATE.

示例:
  ./termux-install.sh
  ./termux-install.sh --run "mcp-toolkit --show-config"
  ./termux-install.sh --env-file /data/data/com.termux/files/home/.mcp.env
  ./termux-install.sh --archive ./mcp-toolkit-server-offline-pip.tar.gz
  RUN_CMD="mcp-toolkit --transport streamable-http --host 0.0.0.0 --port 8000" \
    ./termux-install.sh
EOF
}

log() {
  printf '%s\n' "==> $*" >&2
}

fail() {
  printf '%s\n' "错误：$*" >&2
  exit 1
}

abs_path() {
  case "$1" in
    /*) printf '%s\n' "$1" ;;
    *) printf '%s\n' "$PWD/$1" ;;
  esac
}

while [ "$#" -gt 0 ]; do
  case "$1" in
    --wheelhouse)
      [ "$#" -ge 2 ] || fail "--wheelhouse 需要一个目录参数"
      WHEELHOUSE=$(abs_path "$2")
      shift 2
      ;;
    --requirements)
      [ "$#" -ge 2 ] || fail "--requirements 需要一个文件参数"
      REQUIREMENTS=$(abs_path "$2")
      shift 2
      ;;
    --archive)
      [ "$#" -ge 2 ] || fail "--archive 需要一个文件参数"
      OFFLINE_ARCHIVE=$(abs_path "$2")
      shift 2
      ;;
    --extract-dir)
      [ "$#" -ge 2 ] || fail "--extract-dir 需要一个目录参数"
      EXTRACT_DIR=$(abs_path "$2")
      shift 2
      ;;
    --python)
      [ "$#" -ge 2 ] || fail "--python 需要一个可执行文件参数"
      PYTHON=$2
      shift 2
      ;;
    --run)
      [ "$#" -ge 2 ] || fail "--run 需要一个命令参数"
      RUN_CMD=$2
      shift 2
      ;;
    --run-module)
      [ "$#" -ge 2 ] || fail "--run-module 需要一个模块名参数"
      RUN_MODULE=$2
      shift 2
      ;;
    --env-file)
      [ "$#" -ge 2 ] || fail "--env-file 需要一个文件参数"
      ENV_FILE=$(abs_path "$2")
      shift 2
      ;;
    --no-env-prompt)
      NO_ENV_PROMPT=1
      shift
      ;;
    --no-save-env)
      SAVE_ENV=0
      shift
      ;;
    --install-all-wheels)
      INSTALL_ALL_WHEELS=1
      shift
      ;;
    --no-run)
      NO_RUN=1
      shift
      ;;
    --skip-python-install)
      SKIP_PYTHON_INSTALL=1
      shift
      ;;
    --no-pkg-update)
      PKG_UPDATE=0
      shift
      ;;
    -h|--help)
      usage
      exit 0
      ;;
    --)
      shift
      [ "$#" -gt 0 ] || fail "-- 后面需要跟要运行的命令"
      RUN_CMD=$*
      break
      ;;
    *)
      fail "未知选项：$1"
      ;;
  esac
done

find_python() {
  if [ -n "$PYTHON" ]; then
    if [ -x "$PYTHON" ]; then
      printf '%s\n' "$PYTHON"
      return 0
    fi
    if command -v "$PYTHON" >/dev/null 2>&1; then
      command -v "$PYTHON"
      return 0
    fi
    return 1
  fi

  if [ -n "${PREFIX:-}" ] && [ -x "$PREFIX/bin/python" ]; then
    printf '%s\n' "$PREFIX/bin/python"
    return 0
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
      return 0
    fi
  done

  if command -v python3 >/dev/null 2>&1; then
    command -v python3
    return 0
  fi
  if command -v python >/dev/null 2>&1; then
    command -v python
    return 0
  fi

  return 1
}

install_termux_python() {
  if find_python >/dev/null 2>&1; then
    return 0
  fi

  [ "$SKIP_PYTHON_INSTALL" != "1" ] || fail "未找到 Python，并且已设置 --skip-python-install"
  command -v pkg >/dev/null 2>&1 || fail "未找到 Python，且当前环境没有可用的 Termux pkg 命令"

  log "未找到 Python，正在安装 Termux python 包"
  if [ "$PKG_UPDATE" != "0" ]; then
    pkg update -y || log "pkg update 失败，继续执行 pkg install python"
  fi
  pkg install -y python
}

ensure_pip() {
  if "$PYTHON_BIN" -m pip --version >/dev/null 2>&1; then
    return 0
  fi

  log "未找到 pip，尝试执行 python -m ensurepip"
  "$PYTHON_BIN" -m ensurepip --upgrade >/dev/null 2>&1 || true

  "$PYTHON_BIN" -m pip --version >/dev/null 2>&1 || \
    fail "$PYTHON_BIN 无法使用 pip；请重新安装 Termux python，或通过 --python 指定其他 Python"
}

refuse_virtualenv() {
  ALLOW_VENV=${ALLOW_VENV:-0} "$PYTHON_BIN" - <<'PY'
import os
import sys

in_venv = sys.prefix != sys.base_prefix or hasattr(sys, "real_prefix")
if in_venv and os.environ.get("ALLOW_VENV") != "1":
    raise SystemExit(
        "拒绝安装到虚拟环境；请把 PYTHON 设置为 Termux 系统 Python，"
        "或设置 ALLOW_VENV=1"
    )
PY
}

extract_archive_if_needed() {
  if [ -z "$OFFLINE_ARCHIVE" ] && [ -z "$WHEELHOUSE" ]; then
    if [ ! -d "$SCRIPT_DIR/wheelhouse" ] && [ ! -d "$SCRIPT_DIR/offline-pip-package/wheelhouse" ]; then
      for candidate in \
        "$SCRIPT_DIR"/*offline-pip*.tar.gz \
        "$SCRIPT_DIR"/*offline-wheelhouse*.tar.gz
      do
        if [ -f "$candidate" ]; then
          OFFLINE_ARCHIVE=$candidate
          break
        fi
      done
    fi
  fi

  if [ -n "$OFFLINE_ARCHIVE" ]; then
    [ -f "$OFFLINE_ARCHIVE" ] || fail "未找到离线压缩包：$OFFLINE_ARCHIVE"
    mkdir -p "$EXTRACT_DIR"
    log "正在解压离线包：$OFFLINE_ARCHIVE"
    tar -xzf "$OFFLINE_ARCHIVE" -C "$EXTRACT_DIR"
  fi
}

pick_wheelhouse() {
  if [ -n "$WHEELHOUSE" ]; then
    WHEELHOUSE=$(abs_path "$WHEELHOUSE")
  elif [ -d "$SCRIPT_DIR/wheelhouse" ]; then
    WHEELHOUSE=$SCRIPT_DIR/wheelhouse
  elif [ -d "$SCRIPT_DIR/offline-pip-package/wheelhouse" ]; then
    WHEELHOUSE=$SCRIPT_DIR/offline-pip-package/wheelhouse
  elif [ -d "$EXTRACT_DIR/wheelhouse" ]; then
    WHEELHOUSE=$EXTRACT_DIR/wheelhouse
  elif [ -d "$EXTRACT_DIR/offline-pip-package/wheelhouse" ]; then
    WHEELHOUSE=$EXTRACT_DIR/offline-pip-package/wheelhouse
  else
    fail "未找到 wheelhouse；请传入 --wheelhouse DIR 或 --archive FILE"
  fi

  [ -d "$WHEELHOUSE" ] || fail "未找到 wheelhouse：$WHEELHOUSE"

  first_whl=$(find "$WHEELHOUSE" -maxdepth 1 -type f -name '*.whl' | sed -n '1p')
  [ -n "$first_whl" ] || fail "该目录中没有 .whl 文件：$WHEELHOUSE"
}

pick_requirements() {
  if [ -n "$REQUIREMENTS" ]; then
    REQUIREMENTS=$(abs_path "$REQUIREMENTS")
  elif [ -f "$SCRIPT_DIR/requirements.txt" ]; then
    REQUIREMENTS=$SCRIPT_DIR/requirements.txt
  elif [ -f "$SCRIPT_DIR/requirements-local.txt" ]; then
    REQUIREMENTS=$SCRIPT_DIR/requirements-local.txt
  elif [ -f "$SCRIPT_DIR/offline-pip-package/requirements.txt" ]; then
    REQUIREMENTS=$SCRIPT_DIR/offline-pip-package/requirements.txt
  elif [ -f "$EXTRACT_DIR/requirements.txt" ]; then
    REQUIREMENTS=$EXTRACT_DIR/requirements.txt
  elif [ -f "$EXTRACT_DIR/requirements-local.txt" ]; then
    REQUIREMENTS=$EXTRACT_DIR/requirements-local.txt
  else
    REQUIREMENTS=
  fi

  if [ -n "$REQUIREMENTS" ]; then
    [ -f "$REQUIREMENTS" ] || fail "未找到 requirements 文件：$REQUIREMENTS"
  fi
}

install_offline_pip_packages() {
  log "使用 Python：$PYTHON_BIN"
  log "使用 wheelhouse：$WHEELHOUSE"

  if [ "$INSTALL_ALL_WHEELS" = "1" ] || [ -z "$REQUIREMENTS" ]; then
    set -- "$WHEELHOUSE"/*.whl
    [ -f "$1" ] || fail "该目录中没有 .whl 文件：$WHEELHOUSE"
    log "正在离线安装所有 wheel"
    "$PYTHON_BIN" -m pip install --no-index --find-links "$WHEELHOUSE" "$@"
    return 0
  fi

  req_dir=$(CDPATH= cd -- "$(dirname -- "$REQUIREMENTS")" && pwd)
  req_file=$(basename -- "$REQUIREMENTS")
  log "使用 requirements：$REQUIREMENTS"
  log "正在按 requirements 离线安装"
  (
    cd "$req_dir"
    "$PYTHON_BIN" -m pip install --no-index --find-links "$WHEELHOUSE" -r "$req_file"
  )
}

load_runtime_env_file() {
  if [ -f "$ENV_FILE" ]; then
    log "正在加载运行环境变量文件：$ENV_FILE"
    . "$ENV_FILE"
    export "MCP_ENV_FILE=$ENV_FILE"
  fi
}

valid_transport() {
  case "$1" in
    stdio|sse|streamable-http) return 0 ;;
    *) return 1 ;;
  esac
}

valid_port() {
  case "$1" in
    ''|*[!0-9]*) return 1 ;;
    *) [ "$1" -ge 1 ] 2>/dev/null && [ "$1" -le 65535 ] 2>/dev/null ;;
  esac
}

normalize_bool() {
  case "$1" in
    1|true|TRUE|True|yes|YES|Yes|y|Y|on|ON|On)
      printf '%s\n' true
      ;;
    0|false|FALSE|False|no|NO|No|n|N|off|OFF|Off)
      printf '%s\n' false
      ;;
    *)
      return 1
      ;;
  esac
}

prompt_env_value() {
  var_name=$1
  prompt_text=$2
  default_value=$3
  required=$4
  secret=$5
  validator=$6

  eval "current_value=\${$var_name:-}"
  if [ -n "$current_value" ]; then
    default_value=$current_value
  fi

  while :; do
    if [ "$secret" = "1" ]; then
      if [ -n "$default_value" ]; then
        printf '%s [已设置，回车保留，输入 - 清空]: ' "$prompt_text" >&2
      else
        printf '%s [可选，回车跳过]: ' "$prompt_text" >&2
      fi
    elif [ -n "$default_value" ]; then
      printf '%s [%s]: ' "$prompt_text" "$default_value" >&2
    else
      printf '%s: ' "$prompt_text" >&2
    fi

    if [ "$secret" = "1" ] && [ -t 0 ]; then
      stty -echo 2>/dev/null || true
      IFS= read -r answer || answer=
      stty echo 2>/dev/null || true
      printf '\n' >&2
    else
      IFS= read -r answer || answer=
    fi

    if [ -z "$answer" ]; then
      answer=$default_value
    elif [ "$required" != "1" ] && [ "$answer" = "-" ]; then
      answer=
    fi

    if [ "$required" = "1" ] && [ -z "$answer" ]; then
      log "该项不能为空。"
      continue
    fi

    case "$validator" in
      transport)
        valid_transport "$answer" || {
          log "请输入 stdio、sse 或 streamable-http。"
          continue
        }
        ;;
      port)
        valid_port "$answer" || {
          log "请输入 1 到 65535 之间的端口。"
          continue
        }
        ;;
      bool)
        if normalized=$(normalize_bool "$answer"); then
          answer=$normalized
        else
          log "请输入 true/false、yes/no、on/off 或 1/0。"
          continue
        fi
        ;;
      none)
        ;;
      *)
        fail "未知校验器：$validator"
        ;;
    esac

    export "$var_name=$answer"
    return 0
  done
}

quote_env_value() {
  printf "'"
  printf '%s' "$1" | sed "s/'/'\\\\''/g"
  printf "'"
}

write_runtime_env_file() {
  [ "$SAVE_ENV" = "1" ] || return 0

  env_parent=$(dirname -- "$ENV_FILE")
  mkdir -p "$env_parent"
  env_dir=$(CDPATH= cd -- "$env_parent" && pwd)
  ENV_FILE=$env_dir/$(basename -- "$ENV_FILE")
  tmp_file=$ENV_FILE.tmp.$$

  umask 077
  {
    printf '%s\n' "# 由 termux-install.sh 生成"
    printf 'export MCP_SERVER_NAME=%s\n' "$(quote_env_value "${MCP_SERVER_NAME:-python-mcp-toolkit}")"
    printf 'export MCP_TRANSPORT=%s\n' "$(quote_env_value "${MCP_TRANSPORT:-streamable-http}")"
    printf 'export MCP_HOST=%s\n' "$(quote_env_value "${MCP_HOST:-0.0.0.0}")"
    printf 'export MCP_PORT=%s\n' "$(quote_env_value "${MCP_PORT:-8000}")"
    printf 'export MCP_STATELESS_HTTP=%s\n' "$(quote_env_value "${MCP_STATELESS_HTTP:-true}")"
    printf 'export MCP_WORKSPACE=%s\n' "$(quote_env_value "${MCP_WORKSPACE:-$SCRIPT_DIR}")"
    printf 'export MCP_ALLOW_WRITE=%s\n' "$(quote_env_value "${MCP_ALLOW_WRITE:-false}")"
    printf 'export MCP_AUTH_TOKEN=%s\n' "$(quote_env_value "${MCP_AUTH_TOKEN:-}")"
    printf 'export MCP_AUTH_HEADER=%s\n' "$(quote_env_value "${MCP_AUTH_HEADER:-X-MCP-Auth-Token}")"
    printf 'export TAVILY_API_KEY=%s\n' "$(quote_env_value "${TAVILY_API_KEY:-}")"
    printf 'export MCP_TOOLKIT_PLUGINS=%s\n' "$(quote_env_value "${MCP_TOOLKIT_PLUGINS:-}")"
  } > "$tmp_file"

  mv "$tmp_file" "$ENV_FILE"
  chmod 600 "$ENV_FILE" 2>/dev/null || true
  export "MCP_ENV_FILE=$ENV_FILE"
  log "已保存运行环境变量文件：$ENV_FILE"
}

prompt_runtime_env() {
  if [ "$NO_RUN" = "1" ]; then
    return 0
  fi
  if [ "$NO_ENV_PROMPT" = "1" ]; then
    return 0
  fi
  if [ ! -t 0 ]; then
    log "标准输入不是交互终端，跳过运行环境变量提示"
    return 0
  fi

  log "配置运行环境变量。直接回车使用默认值。"

  prompt_env_value MCP_WORKSPACE "工作目录 MCP_WORKSPACE" "${MCP_WORKSPACE:-$SCRIPT_DIR}" 1 0 none
  prompt_env_value MCP_TRANSPORT "传输方式 MCP_TRANSPORT (stdio/sse/streamable-http)" "${MCP_TRANSPORT:-streamable-http}" 1 0 transport

  if [ "$MCP_TRANSPORT" = "stdio" ]; then
    export "MCP_HOST=${MCP_HOST:-127.0.0.1}"
    export "MCP_PORT=${MCP_PORT:-8000}"
    export "MCP_STATELESS_HTTP=${MCP_STATELESS_HTTP:-true}"
  else
    prompt_env_value MCP_HOST "监听地址 MCP_HOST" "${MCP_HOST:-0.0.0.0}" 1 0 none
    prompt_env_value MCP_PORT "监听端口 MCP_PORT" "${MCP_PORT:-8000}" 1 0 port
    if [ "$MCP_TRANSPORT" = "streamable-http" ]; then
      prompt_env_value MCP_STATELESS_HTTP "无状态 HTTP MCP_STATELESS_HTTP" "${MCP_STATELESS_HTTP:-true}" 1 0 bool
    else
      export "MCP_STATELESS_HTTP=${MCP_STATELESS_HTTP:-true}"
    fi
    prompt_env_value MCP_AUTH_TOKEN "认证令牌 MCP_AUTH_TOKEN" "${MCP_AUTH_TOKEN:-}" 0 1 none
    if [ -n "${MCP_AUTH_TOKEN:-}" ]; then
      prompt_env_value MCP_AUTH_HEADER "认证请求头 MCP_AUTH_HEADER" "${MCP_AUTH_HEADER:-X-MCP-Auth-Token}" 1 0 none
    else
      export "MCP_AUTH_HEADER=${MCP_AUTH_HEADER:-X-MCP-Auth-Token}"
    fi
  fi

  prompt_env_value MCP_ALLOW_WRITE "允许写文件 MCP_ALLOW_WRITE" "${MCP_ALLOW_WRITE:-false}" 1 0 bool
  prompt_env_value TAVILY_API_KEY "Tavily API Key TAVILY_API_KEY" "${TAVILY_API_KEY:-}" 0 1 none
  prompt_env_value MCP_TOOLKIT_PLUGINS "插件模块 MCP_TOOLKIT_PLUGINS" "${MCP_TOOLKIT_PLUGINS:-}" 0 0 none

  write_runtime_env_file
}

prepare_runtime_env() {
  if [ "$NO_RUN" = "1" ]; then
    return 0
  fi

  load_runtime_env_file
  prompt_runtime_env
}

run_program() {
  if [ "$NO_RUN" = "1" ]; then
    log "安装已完成；因为设置了 --no-run，跳过启动"
    return 0
  fi

  if [ -n "$RUN_CMD" ]; then
    log "正在运行命令：$RUN_CMD"
    exec sh -c "$RUN_CMD"
  fi

  [ -n "$RUN_MODULE" ] || fail "RUN_MODULE 为空；请传入 --run 或 --no-run"
  log "正在运行模块：$RUN_MODULE"
  exec "$PYTHON_BIN" -m "$RUN_MODULE"
}

install_termux_python
PYTHON_BIN=$(find_python) || fail "未找到 Python"
ensure_pip
refuse_virtualenv
extract_archive_if_needed
pick_wheelhouse
pick_requirements
install_offline_pip_packages
prepare_runtime_env
run_program
