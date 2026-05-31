# 离线版构建与安装

本文档说明如何把项目和依赖构建成离线安装包，并在无网络环境中从 `wheelhouse/` 安装。安装脚本默认使用系统级 Python，不安装到 `.venv` 等虚拟环境中。

## 目录约定

以下命令默认在项目根目录执行：

```sh
cd /data/data/com.termux/files/home/mcp
```

项目当前提供两种离线包格式。推荐普通离线安装使用 `pip` 格式；如果还需要继续追加或替换 wheel，使用 `wheelhouse` 格式。

`wheelhouse` 格式保留原始 wheelhouse 目录：

```text
mcp-toolkit-server-offline-wheelhouse.tar.gz
  wheelhouse/
    *.whl
  requirements-local.txt
  install-wheelhouse-offline.sh
  termux-install.sh
```

`pip` 格式也使用 `wheelhouse/` 目录，并提供最小 `requirements.txt` 和安装脚本：

```text
mcp-toolkit-server-offline-pip.tar.gz
  wheelhouse/
    *.whl
  requirements.txt
  install.sh
  termux-install.sh
```

两种格式都只从本地 wheel 安装，不访问 PyPI。安装脚本会优先选择系统 Python，Termux 默认路径为 `/data/data/com.termux/files/usr/bin/python`；如果检测到虚拟环境 Python，会拒绝安装。

## 在线环境构建 wheelhouse

先安装构建工具：

```sh
python -m pip install -U pip build
```

构建当前项目 wheel：

```sh
rm -rf dist wheelhouse
python -m build --wheel
mkdir -p wheelhouse
cp dist/*.whl wheelhouse/
```

下载项目依赖到 `wheelhouse/`：

```sh
python -m pip download -d wheelhouse dist/*.whl
```

如果已有 `requirements-local.txt`，也可以按该文件补齐依赖：

```sh
python -m pip download -d wheelhouse -r requirements-local.txt
```

## 打包离线安装包

生成 `wheelhouse` 格式：

```sh
tar -czf mcp-toolkit-server-offline-wheelhouse.tar.gz \
  wheelhouse requirements-local.txt install-wheelhouse-offline.sh termux-install.sh
```

生成 `pip` 格式：

```sh
rm -rf offline-pip-package
mkdir -p offline-pip-package/wheelhouse
cp wheelhouse/*.whl offline-pip-package/wheelhouse/
cat > offline-pip-package/requirements.txt <<'EOF'
--no-index
--find-links ./wheelhouse
mcp-toolkit-server==0.1.0
EOF
cat > offline-pip-package/install.sh <<'EOF'
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
EOF
chmod +x offline-pip-package/install.sh
cp termux-install.sh offline-pip-package/
tar -czf mcp-toolkit-server-offline-pip.tar.gz -C offline-pip-package .
```

生成的 `mcp-toolkit-server-offline-wheelhouse.tar.gz` 或 `mcp-toolkit-server-offline-pip.tar.gz` 都是单文件离线安装包。

## 离线环境安装

### Termux 一键安装、配置并运行

在 Termux 中推荐使用 `termux-install.sh`。该脚本会先检查 Termux 系统 Python；如果没有 Python，会调用 `pkg install -y python` 安装。随后从本地 `wheelhouse/` 或离线压缩包安装 pip 包，pip 阶段始终使用 `--no-index --find-links`，不会访问 PyPI。安装完成后，脚本会提示填写运行所需的环境变量，并启动服务。

在项目目录内直接运行：

```sh
chmod +x termux-install.sh
./termux-install.sh
```

如果只有离线压缩包，指定压缩包路径：

```sh
./termux-install.sh --archive ./mcp-toolkit-server-offline-pip.tar.gz
```

只安装，不运行服务：

```sh
./termux-install.sh --no-run
```

安装后运行指定命令：

```sh
./termux-install.sh --run "mcp-toolkit --show-config"
```

完全跳过交互式环境变量提示：

```sh
./termux-install.sh --no-env-prompt
```

如果离线机器已经安装好 Python，并且不希望脚本尝试调用 Termux `pkg`：

```sh
./termux-install.sh --skip-python-install
```

注意：脚本安装 Python 使用的是 Termux `pkg` 软件源，这一步需要 Termux 能访问软件源。真正离线的机器需要提前装好 Termux Python，或使用 `--skip-python-install` 并通过 `--python PATH` 指定可用 Python。pip 依赖安装仍然只使用本地 wheel。

脚本默认会提示并导出以下运行环境变量：

| 变量名 | 默认值 | 是否必填 | 说明 |
| --- | --- | --- | --- |
| `MCP_WORKSPACE` | 脚本所在目录 | 是 | `file_operation` 允许访问的工作区根目录。 |
| `MCP_TRANSPORT` | `streamable-http` | 是 | MCP 传输方式：`stdio`、`sse` 或 `streamable-http`。 |
| `MCP_HOST` | `0.0.0.0` | HTTP/SSE 时必填 | HTTP/SSE 监听地址。`stdio` 模式不会提示。 |
| `MCP_PORT` | `8000` | HTTP/SSE 时必填 | HTTP/SSE 监听端口。`stdio` 模式不会提示。 |
| `MCP_STATELESS_HTTP` | `true` | `streamable-http` 时必填 | 是否不要求客户端维护 `mcp-session-id`。 |
| `MCP_AUTH_TOKEN` | 空 | 否 | HTTP/SSE 请求头授权码。为空时不启用请求头鉴权。 |
| `MCP_AUTH_HEADER` | `X-MCP-Auth-Token` | 设置 token 时必填 | 读取授权码的请求头名。 |
| `MCP_ALLOW_WRITE` | `false` | 是 | 是否允许文件写入、替换、复制、移动和删除。 |
| `TAVILY_API_KEY` | 空 | 否 | Tavily API Key。为空时 `provider=auto` 使用 Bing；显式 `provider=tavily` 需要设置。 |
| `MCP_TOOLKIT_PLUGINS` | 空 | 否 | 逗号分隔的插件模块列表。 |

密钥类输入不会在终端回显。已有值时直接回车会保留原值；输入 `-` 会清空可选值。

脚本默认把用户输入保存到：

```text
.termux-mcp.env
```

下次运行会自动加载该文件。也可以指定保存位置：

```sh
./termux-install.sh --env-file /data/data/com.termux/files/home/.mcp.env
```

只在本次运行中使用输入值，不保存到文件：

```sh
./termux-install.sh --no-save-env
```

脚本也支持通过环境变量预置参数，例如：

```sh
MCP_WORKSPACE=/data/data/com.termux/files/home/mcp \
MCP_TRANSPORT=streamable-http \
MCP_HOST=0.0.0.0 \
MCP_PORT=8000 \
RUN_CMD="mcp-toolkit" \
./termux-install.sh
```

### 通用离线安装脚本

使用 `wheelhouse` 格式时：

```sh
tar -xzf mcp-toolkit-server-offline-wheelhouse.tar.gz
./install-wheelhouse-offline.sh
```

也可以只指定入口包，由 pip 从 `wheelhouse/` 解析依赖：

```sh
./install-wheelhouse-offline.sh mcp-toolkit-server==0.1.0
```

使用 `pip` 格式时：

```sh
mkdir -p mcp-toolkit-server-offline-pip
tar -xzf mcp-toolkit-server-offline-pip.tar.gz -C mcp-toolkit-server-offline-pip
cd mcp-toolkit-server-offline-pip
./install.sh
```

如果离线机器的系统 Python 不在默认位置，通过 `PYTHON` 指定系统 Python 可执行文件：

```sh
PYTHON=/path/to/system/python ./install-wheelhouse-offline.sh mcp-toolkit-server==0.1.0
PYTHON=/path/to/system/python ./install.sh
```

如果 `wheelhouse/` 不在脚本同目录，通过 `WHEELHOUSE` 指定：

```sh
WHEELHOUSE=/path/to/wheelhouse ./install-wheelhouse-offline.sh mcp-toolkit-server==0.1.0
```

## 验证安装

安装完成后检查命令是否可用：

```sh
mcp-toolkit
```

也可以检查 Python 包：

```sh
python -m pip show mcp-toolkit-server
```

查看解析后的非敏感配置：

```sh
mcp-toolkit --show-config
```

验证离线包依赖是否能只从本地 wheel 解析：

```sh
python -m pip install --dry-run --ignore-installed --no-index \
  --find-links ./wheelhouse -r requirements.txt
```

远程模式可验证健康检查：

```sh
mcp-toolkit --transport streamable-http --host 127.0.0.1 --port 8000
curl http://127.0.0.1:8000/healthz
```

## 注意事项

- 构建机和离线安装机的 Python 版本、系统和 CPU 架构应保持一致。
- 当前 wheelhouse 中包含平台相关 wheel，例如 `cryptography`、`cffi`、`pydantic_core`、`rpds_py`。
- 在 Android 或 Termux 环境构建出来的 wheel，通常不能直接用于 Linux x86_64、Windows 或 macOS。
- 离线安装脚本会拒绝虚拟环境 Python；需要安装到系统 Python 时，退出虚拟环境或显式设置 `PYTHON=/path/to/system/python`。
- 离线安装时必须使用 `--no-index`，否则 pip 可能尝试访问网络。
