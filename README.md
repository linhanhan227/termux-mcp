# Python MCP Toolkit Server

一个基于 Python 编写的可扩展 MCP 工具服务器，使用官方 MCP Python SDK 的 `FastMCP` 作为服务入口，内置常用工具，并支持通过插件模块继续扩展工具集。

## 功能特性

- `web_search` 联网搜索：有 `TAVILY_API_KEY` 时使用 Tavily，否则使用 DuckDuckGo HTML 搜索
- `file_operation` 文件操作：在一个工具内完成列表、读取、查找、grep、写入、替换、复制、移动和删除
- `agent` 轻量任务状态工具：记录任务目标、步骤、进展和完成结果
- 插件式工具扩展，支持按模块加载自定义工具
- 支持 `stdio`、`sse` 和 `streamable-http` 三种 MCP 传输方式
- 支持 `.env` 自动加载、命令行参数覆盖和远程请求头授权
- 提供 `/healthz` 健康检查端点，便于远程部署验证
- 默认安全边界：文件访问限制在 `MCP_WORKSPACE`，写入、复制、移动和删除默认关闭

## 文档

- [项目说明](docs/project-description.zh-CN.md)
- [详细使用与扩展手册](docs/user-guide.zh-CN.md)
- [离线版构建与安装](docs/offline-install.zh-CN.md)
- [工具开发说明](docs/tool-development.md)

## 安装

本项目按系统级 Python 运行和安装。Termux 中系统 Python 通常是 `/data/data/com.termux/files/usr/bin/python`。先确认 `python` 指向系统 Python，然后安装到该 Python 环境：

```sh
python -c "import sys; print(sys.executable)"
python -m pip install -e .
```

在 Termux 或 Android Python 环境中，如果 `pydantic-core` 等原生依赖从源码编译并出现 `Text file busy`，使用单线程 Cargo 构建重试：

```sh
CARGO_BUILD_JOBS=1 python -m pip install -e .
```

离线环境可直接使用 `mcp-toolkit-server-offline-pip.tar.gz`：

```sh
mkdir -p mcp-toolkit-server-offline-pip
tar -xzf mcp-toolkit-server-offline-pip.tar.gz -C mcp-toolkit-server-offline-pip
cd mcp-toolkit-server-offline-pip
./install.sh
```

也可以使用 `wheelhouse` 格式安装：

```sh
./install-wheelhouse-offline.sh mcp-toolkit-server==0.1.0
```

在 Termux 中，如果希望脚本自动检查 Python、离线安装 pip 包、提示填写运行环境变量并启动服务，可以使用：

```sh
./termux-install.sh
```

脚本会把输入的运行环境变量默认保存到 `.termux-mcp.env`，下次运行自动加载。只安装不运行时使用：

```sh
./termux-install.sh --no-run
```

完整流程见 [离线版构建与安装](docs/offline-install.zh-CN.md)。

## 配置

不要把真实 API Key 写入源码。启动前通过环境变量配置工作区；`TAVILY_API_KEY` 可选，未设置时 `web_search` 会使用 DuckDuckGo HTML 搜索：

```sh
export TAVILY_API_KEY='your-tavily-key'
export MCP_WORKSPACE=/data/data/com.termux/files/home/mcp
```

启动时会自动读取当前目录的 `.env` 文件；已有环境变量优先级更高，不会被 `.env` 覆盖。也可以通过 `MCP_ENV_FILE=/path/to/.env` 指定配置文件。

常用可选配置：

```sh
export MCP_ENV_FILE=.env
export MCP_SERVER_NAME=python-mcp-toolkit
export MCP_TRANSPORT=stdio
export MCP_HOST=127.0.0.1
export MCP_PORT=8000
export MCP_STATELESS_HTTP=true
export MCP_AUTH_TOKEN=
export MCP_AUTH_HEADER=X-MCP-Auth-Token
export MCP_ALLOW_WRITE=false
export MCP_MAX_FILE_BYTES=2097152
export MCP_REQUEST_TIMEOUT=20
export MCP_TOOLKIT_PLUGINS=examples.custom_tools
```

关键环境变量说明：

| 变量名 | 默认值 | 说明 |
| --- | --- | --- |
| `TAVILY_API_KEY` | 空 | Tavily API Key。为空时 `web_search` 使用 DuckDuckGo HTML 搜索。 |
| `TAVILY_API_URL` | `https://api.tavily.com/search` | Tavily 搜索接口地址。 |
| `MCP_ENV_FILE` | `.env` | 启动时自动读取的环境变量文件。设为空可禁用自动加载。 |
| `MCP_TRANSPORT` | `stdio` | MCP 传输方式：`stdio`、`sse` 或 `streamable-http`。 |
| `MCP_HOST` | `127.0.0.1` | HTTP/SSE 监听地址，远程访问通常设为 `0.0.0.0`。 |
| `MCP_PORT` | `8000` | HTTP/SSE 监听端口。 |
| `MCP_STATELESS_HTTP` | `true` | `streamable-http` 默认不要求客户端维护 `mcp-session-id`。设为 `false` 可切回有状态 session 模式。 |
| `MCP_WORKSPACE` | `.` | `file_operation` 允许访问的工作区根目录。 |
| `MCP_AUTH_TOKEN` | 空 | HTTP/SSE 请求头授权码。为空时不启用请求头鉴权。 |
| `MCP_AUTH_HEADER` | `X-MCP-Auth-Token` | 读取授权码的请求头名。设为 `Authorization` 时也支持 `Bearer <token>`。 |
| `MCP_ALLOW_WRITE` | `false` | 是否允许 `file_operation` 执行写入、替换、复制、移动和删除。 |
| `MCP_MAX_FILE_BYTES` | `2097152` | 单个可读取文件大小上限，默认 `2 MiB`。 |
| `MCP_REQUEST_TIMEOUT` | `20` | HTTP 请求超时时间，单位秒。 |
| `MCP_TOOLKIT_PLUGINS` | 空 | 逗号分隔的插件模块列表。 |

## 启动

安装后运行：

```sh
mcp-toolkit
```

也可以通过系统 Python 模块入口启动：

```sh
python -m mcp_toolkit.server
```

命令行参数会覆盖环境变量，常用示例：

```sh
mcp-toolkit \
  --transport streamable-http \
  --host 0.0.0.0 \
  --port 8000 \
  --workspace /data/data/com.termux/files/home/mcp
```

查看当前解析后的非敏感配置：

```sh
mcp-toolkit --show-config
```

常用命令行参数：

| 参数 | 说明 |
| --- | --- |
| `--env-file PATH` | 指定启动时读取的 `.env` 文件。 |
| `--transport stdio|sse|streamable-http` | 覆盖 `MCP_TRANSPORT`。 |
| `--host HOST` | 覆盖 HTTP/SSE 监听地址。 |
| `--port PORT` | 覆盖 HTTP/SSE 监听端口。 |
| `--workspace PATH` | 覆盖 `MCP_WORKSPACE`。 |
| `--auth-token TOKEN` | 设置 HTTP/SSE 请求头授权码。 |
| `--auth-header NAME` | 设置读取授权码的请求头名。 |
| `--stateless-http` / `--stateful-http` | 覆盖 `streamable-http` 是否要求客户端维护 MCP session header。 |
| `--plugin MODULE` | 加载插件模块，可重复使用，也可逗号分隔。 |
| `--allow-write` / `--disable-write` | 覆盖 `file_operation` 写入、复制、移动和删除开关。 |
| `--show-config` | 打印非敏感配置后退出。 |

远程运行推荐使用 `streamable-http`。默认不需要请求头 token，也不要求客户端手动维护 `mcp-session-id`：

```sh
export MCP_TRANSPORT=streamable-http
export MCP_HOST=0.0.0.0
export MCP_PORT=8000
mcp-toolkit
```

远程地址：

```text
http://服务器IP:8000/mcp
```

如需启用请求头鉴权，再额外设置：

```sh
export MCP_AUTH_TOKEN='change-this-token'
```

客户端请求需要带上：

```text
X-MCP-Auth-Token: change-this-token
```

健康检查地址：

```text
http://服务器IP:8000/healthz
```

启用 `MCP_AUTH_TOKEN` 后，健康检查同样需要带授权请求头。

## MCP 客户端配置示例

```json
{
  "mcpServers": {
    "python-mcp-toolkit": {
      "command": "/data/data/com.termux/files/usr/bin/python",
      "args": ["-m", "mcp_toolkit.server"],
      "env": {
        "TAVILY_API_KEY": "your-tavily-key",
        "MCP_WORKSPACE": "/data/data/com.termux/files/home/mcp",
        "MCP_ALLOW_WRITE": "false"
      }
    }
  }
}
```

示例中的 `command` 使用 Termux 系统 Python 路径；其他系统请替换为对应的系统 Python 可执行文件。插件模块需要能被系统 Python 导入；推荐把插件作为包安装到系统 Python，或从插件父目录启动客户端。

远程 `streamable-http` 客户端示例：

```json
{
  "mcpServers": {
    "python-mcp-toolkit-remote": {
      "type": "streamable-http",
      "url": "http://服务器IP:8000/mcp"
    }
  }
}
```

## 内置工具

| 工具名 | 说明 |
| --- | --- |
| `web_search` | 联网搜索公开网页，优先使用 Tavily，未配置 Key 时使用 DuckDuckGo HTML 搜索。 |
| `file_operation` | 在 `MCP_WORKSPACE` 内执行文件操作；写入、替换、复制、移动、删除需要 `MCP_ALLOW_WRITE=true`。 |
| `agent` | 管理轻量 agent 任务状态，记录目标、步骤、进展和完成结果。 |

## 扩展工具

新增工具推荐使用插件模块。插件需要暴露 `register(registry, settings)` 函数：

```python
from mcp_toolkit.core.config import Settings
from mcp_toolkit.core.registry import ToolRegistry


def register(registry: ToolRegistry, settings: Settings) -> None:
    @registry.tool()
    def echo(text: str) -> dict[str, str]:
        """Return the input text."""
        return {"text": text}
```

启用插件：

```sh
export MCP_TOOLKIT_PLUGINS=examples.custom_tools
mcp-toolkit
```

多个插件用英文逗号分隔：

```sh
export MCP_TOOLKIT_PLUGINS=examples.custom_tools,examples.math_tools,examples.workspace_stats
```

更多扩展示例见 `examples/` 目录和 [详细使用与扩展手册](docs/user-guide.zh-CN.md)。

## 验证

编译检查：

```sh
python -m compileall src examples tests
```

运行单元测试：

```sh
python -m unittest discover -s tests
```

列出已注册工具：

```sh
python - <<'PY'
import asyncio
from mcp_toolkit.server import create_server


async def main():
    server = create_server()
    tools = await server.list_tools()
    for tool in tools:
        print(tool.name)


asyncio.run(main())
PY
```

验证插件加载：

```sh
MCP_TOOLKIT_PLUGINS=examples.custom_tools python - <<'PY'
import asyncio
from mcp_toolkit.server import create_server


async def main():
    server = create_server()
    tools = await server.list_tools()
    print(any(tool.name == "echo" for tool in tools))


asyncio.run(main())
PY
```

## 安全说明

- `TAVILY_API_KEY` 只应通过环境变量传入，不应提交到仓库。
- 远程 HTTP/SSE 模式建议设置 `MCP_AUTH_TOKEN`，并在公网环境前置 HTTPS 反向代理。
- `file_operation` 只能访问 `MCP_WORKSPACE` 内路径。
- 文件写入、替换、复制、移动和删除能力默认关闭，需要显式设置 `MCP_ALLOW_WRITE=true`。
- 建议为不同项目配置不同的 `MCP_WORKSPACE`。
