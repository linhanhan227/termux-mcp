# Python MCP Toolkit Server 项目说明

## 项目概述

Python MCP Toolkit Server 是一个基于 Python 编写的标准 MCP 工具服务器。项目使用官方 MCP Python SDK 的 `FastMCP` 作为服务入口，内置常用工具，并提供统一的工具注册机制，方便后续按模块扩展更多 MCP 工具。

项目当前只内置 3 个工具：`web_search`、`file_operation`、`agent`。`web_search` 有 `TAVILY_API_KEY` 时使用 Tavily，没有 Key 时使用 DuckDuckGo HTML 搜索；`file_operation` 的所有路径都限制在 `MCP_WORKSPACE` 内；`agent` 用于记录轻量任务状态。项目运行和离线安装都默认使用系统级 Python。

更详细的环境变量设置、MCP 客户端配置、开发扩展说明和完整示例见 [详细使用与扩展手册](user-guide.zh-CN.md)。

## 设计目标

- 提供一个可以直接接入 MCP 客户端的 Python MCP server。
- 内置工具保持精简，只暴露联网搜索、文件操作和 agent 三个入口。
- 将工具开发和 MCP server 启动逻辑解耦，方便后续扩展工具集。
- 默认采用保守权限：文件访问限制在 `MCP_WORKSPACE`，写入、替换、复制、移动和删除默认关闭。
- 所有敏感配置使用环境变量注入，避免把密钥提交到代码仓库。

## 功能清单

| 工具名 | 说明 |
| --- | --- |
| `web_search` | 联网搜索公开网页，优先使用 Tavily，未配置 Key 时使用 DuckDuckGo HTML 搜索。 |
| `file_operation` | 在 `MCP_WORKSPACE` 内执行文件操作。支持 `list`、`info`、`read`、`read_lines`、`write`、`append`、`replace`、`mkdir`、`copy`、`move`、`delete`、`find`、`grep`。写入类操作需要 `MCP_ALLOW_WRITE=true`。 |
| `agent` | 管理轻量 agent 任务状态，记录目标、步骤、进展和完成结果。 |

## 项目结构

```text
.
├── pyproject.toml
├── README.md
├── docs/
│   ├── project-description.zh-CN.md
│   └── tool-development.md
├── examples/
│   └── custom_tools.py
└── src/
    └── mcp_toolkit/
        ├── server.py
        ├── core/
        │   ├── config.py
        │   ├── registry.py
        │   └── security.py
        └── tools/
            ├── agent.py
            ├── files.py
            └── web.py
```

核心模块说明：

- `src/mcp_toolkit/server.py`：创建并启动 `FastMCP` server。
- `src/mcp_toolkit/core/config.py`：从环境变量读取项目配置。
- `src/mcp_toolkit/core/registry.py`：统一管理工具注册和插件加载。
- `src/mcp_toolkit/core/security.py`：处理工作区路径校验，防止访问工作区外文件。
- `src/mcp_toolkit/tools/`：内置工具实现。
- `examples/custom_tools.py`：自定义工具扩展示例。

## 安装

本项目按系统级 Python 运行和安装。Termux 中系统 Python 通常是 `/data/data/com.termux/files/usr/bin/python`。先确认 `python` 指向系统 Python，然后安装到该 Python 环境：

```sh
python -c "import sys; print(sys.executable)"
python -m pip install -e .
```

在 Termux 或 Android Python 环境中，如果原生依赖从源码编译并出现 `Text file busy`，可以使用单线程 Cargo 构建重试：

```sh
CARGO_BUILD_JOBS=1 python -m pip install -e .
```

如果需要无网络安装，可以使用 `mcp-toolkit-server-offline-pip.tar.gz`：

```sh
mkdir -p mcp-toolkit-server-offline-pip
tar -xzf mcp-toolkit-server-offline-pip.tar.gz -C mcp-toolkit-server-offline-pip
cd mcp-toolkit-server-offline-pip
./install.sh
```

也可以使用 `wheelhouse` 格式：

```sh
./install-wheelhouse-offline.sh mcp-toolkit-server==0.1.0
```

完整步骤见 [离线版构建与安装](offline-install.zh-CN.md)。

## 配置

启动前至少配置 Tavily API Key：

```sh
export TAVILY_API_KEY='your-tavily-key'
export MCP_WORKSPACE=/data/data/com.termux/files/home/mcp
```

可用环境变量：

| 变量名 | 默认值 | 说明 |
| --- | --- | --- |
| `MCP_SERVER_NAME` | `python-mcp-toolkit` | MCP server 名称。 |
| `MCP_TRANSPORT` | `stdio` | MCP 传输方式：`stdio`、`sse` 或 `streamable-http`。 |
| `MCP_HOST` | `127.0.0.1` | HTTP/SSE 监听地址，远程访问通常设为 `0.0.0.0`。 |
| `MCP_PORT` | `8000` | HTTP/SSE 监听端口。 |
| `MCP_STATELESS_HTTP` | `true` | `streamable-http` 默认不要求客户端维护 `mcp-session-id`。设为 `false` 可切回有状态 session 模式。 |
| `MCP_WORKSPACE` | `.` | `file_operation` 允许访问的工作区。 |
| `TAVILY_API_KEY` | 空 | Tavily API Key。为空时 `web_search` 使用 DuckDuckGo HTML 搜索。 |
| `TAVILY_API_URL` | `https://api.tavily.com/search` | Tavily 搜索接口地址。 |
| `MCP_AUTH_TOKEN` | 空 | HTTP/SSE 请求头授权码。为空时不启用请求头鉴权。 |
| `MCP_AUTH_HEADER` | `X-MCP-Auth-Token` | 读取授权码的请求头名。设为 `Authorization` 时也支持 `Bearer <token>`。 |
| `MCP_ALLOW_WRITE` | `false` | 是否允许 `file_operation` 执行写入、替换、复制、移动和删除。 |
| `MCP_MAX_FILE_BYTES` | `2097152` | 单个可读取文件大小上限，单位字节。 |
| `MCP_REQUEST_TIMEOUT` | `20` | HTTP 请求超时时间，单位秒。 |
| `MCP_TOOLKIT_PLUGINS` | 空 | 逗号分隔的插件模块名列表。 |

## 启动

安装后直接运行：

```sh
mcp-toolkit
```

也可以通过系统 Python 模块入口启动：

```sh
python -m mcp_toolkit.server
```

命令行参数可以覆盖环境变量：

```sh
mcp-toolkit --transport streamable-http --host 0.0.0.0 --port 8000
```

可以通过以下命令查看当前解析后的非敏感配置：

```sh
mcp-toolkit --show-config
```

远程运行时使用 HTTP 传输。默认不需要请求头 token，也不要求客户端手动维护 `mcp-session-id`：

```sh
export MCP_TRANSPORT=streamable-http
export MCP_HOST=0.0.0.0
export MCP_PORT=8000
mcp-toolkit
```

远程地址为 `http://服务器IP:8000/mcp`。
如需启用请求头鉴权，设置 `MCP_AUTH_TOKEN`，客户端请求再携带 `X-MCP-Auth-Token: change-this-token`。
健康检查地址为 `http://服务器IP:8000/healthz`，启用请求头授权后同样需要带授权请求头。

## MCP 客户端配置示例

示例中的 `command` 使用 Termux 系统 Python 路径；其他系统请替换为对应的系统 Python 可执行文件。

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

## 工具扩展方式

新增工具时，不需要修改 server 启动逻辑。创建一个 Python 模块，暴露 `register(registry, settings)` 函数即可。

示例：

```python
from mcp_toolkit.core.config import Settings
from mcp_toolkit.core.registry import ToolRegistry


def register(registry: ToolRegistry, settings: Settings) -> None:
    @registry.tool()
    def add(a: int, b: int) -> int:
        """Add two integers."""
        return a + b
```

启用插件：

```sh
export MCP_TOOLKIT_PLUGINS=examples.custom_tools
mcp-toolkit
```

多个插件用英文逗号分隔：

```sh
export MCP_TOOLKIT_PLUGINS=my_tools.search,my_tools.database,my_tools.devops
```

工具开发建议：

- 每个参数都写类型注解，返回值也写类型注解。
- 用简短 docstring 描述工具行为，MCP 客户端会把它作为工具说明。
- 文件类工具应使用 `resolve_workspace_path`，避免访问工作区外路径。
- 网络类工具应设置超时，并把 HTTP 错误转换成清晰的异常信息。
- 涉及写入、删除、执行命令、调用外部服务的工具，应显式配置权限开关。

## 安全说明

项目默认使用以下安全边界：

- `TAVILY_API_KEY` 只从环境变量读取，不应写入仓库文件。
- `file_operation` 只能访问 `MCP_WORKSPACE` 内路径。
- 文件写入、替换、复制、移动和删除能力默认关闭，需要 `MCP_ALLOW_WRITE=true`。
- 读取文件有大小限制，默认最大 `2 MiB`。

如果把该 server 接入长期运行的 MCP 客户端，建议为不同项目配置不同的 `MCP_WORKSPACE`，并只在确实需要时开启写入权限。

## 验证

常用检查命令：

```sh
python -m compileall src examples
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

## 常见问题

### web_search 使用 Tavily 提示缺少 API Key

`web_search` 的 `provider` 参数为 `tavily` 时，需要在启动 MCP server 的同一个环境中设置：

```sh
export TAVILY_API_KEY='your-tavily-key'
```

如果不想配置 Tavily，可以使用默认 `provider=auto`，未设置 Key 时会走 DuckDuckGo HTML 搜索。

### web_search 连接失败

如果错误类似 `All connection attempts failed`，通常是当前运行环境无法连接搜索提供方。先检查网络、代理、DNS 和防火墙配置。

### 写文件工具不可用

默认禁止写入。需要显式开启：

```sh
export MCP_ALLOW_WRITE=true
```

### 文件路径被拒绝

文件工具只能访问 `MCP_WORKSPACE` 内路径。检查传入路径是否通过 `..`、符号链接或绝对路径跳出了工作区。
