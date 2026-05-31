# Python MCP Toolkit Server 使用手册

## 概览

Python MCP Toolkit Server 是一个基于官方 MCP Python SDK `FastMCP` 的可扩展工具服务器。当前内置工具保持精简，只暴露三个入口：

| 工具名 | 说明 |
| --- | --- |
| `web_search` | 联网搜索公开网页。`provider=auto` 时优先使用 Tavily；未配置 `TAVILY_API_KEY` 时使用 DuckDuckGo HTML 搜索。 |
| `file_operation` | 在 `MCP_WORKSPACE` 内执行文件操作，支持列表、信息、读取、写入、追加、替换、创建目录、复制、移动、删除、查找和 grep。 |
| `agent` | 管理轻量 agent 任务状态，记录任务目标、步骤、进展和完成结果。 |

额外能力建议通过插件扩展，不再作为内置工具分散注册。

## 安装

本项目按系统级 Python 运行和安装。Termux 中系统 Python 通常是 `/data/data/com.termux/files/usr/bin/python`。

```sh
python -c "import sys; print(sys.executable)"
python -m pip install -e .
```

离线安装请参考 [离线版构建与安装](offline-install.zh-CN.md)。

## 配置

常用环境变量：

| 变量名 | 默认值 | 说明 |
| --- | --- | --- |
| `MCP_ENV_FILE` | `.env` | 启动时自动读取的环境变量文件；设为空可禁用。 |
| `MCP_SERVER_NAME` | `python-mcp-toolkit` | MCP server 显示名称。 |
| `MCP_TRANSPORT` | `stdio` | MCP 传输方式：`stdio`、`sse` 或 `streamable-http`。 |
| `MCP_HOST` | `127.0.0.1` | HTTP/SSE 监听地址。 |
| `MCP_PORT` | `8000` | HTTP/SSE 监听端口。 |
| `MCP_STATELESS_HTTP` | `true` | `streamable-http` 是否不要求客户端维护 `mcp-session-id`。 |
| `MCP_WORKSPACE` | `.` | `file_operation` 允许访问的工作区根目录。 |
| `TAVILY_API_KEY` | 空 | Tavily API Key。为空时 `web_search` 使用 DuckDuckGo HTML 搜索。 |
| `TAVILY_API_URL` | `https://api.tavily.com/search` | Tavily 搜索接口地址。 |
| `MCP_AUTH_TOKEN` | 空 | HTTP/SSE 请求头授权码；为空时不启用。 |
| `MCP_AUTH_HEADER` | `X-MCP-Auth-Token` | 读取授权码的请求头名；设为 `Authorization` 时支持 `Bearer <token>`。 |
| `MCP_ALLOW_WRITE` | `false` | 是否允许 `file_operation` 执行写入、替换、复制、移动和删除。 |
| `MCP_MAX_FILE_BYTES` | `2097152` | 单个可读取文件大小上限，默认 `2 MiB`。 |
| `MCP_REQUEST_TIMEOUT` | `20` | HTTP 请求超时时间，单位秒。 |
| `MCP_TOOLKIT_PLUGINS` | 空 | 逗号分隔的插件模块列表。 |

示例：

```sh
export MCP_WORKSPACE=/data/data/com.termux/files/home/mcp
export MCP_ALLOW_WRITE=false
export MCP_TRANSPORT=stdio
mcp-toolkit
```

如果需要 `file_operation` 写文件、替换内容、复制、移动或删除：

```sh
export MCP_ALLOW_WRITE=true
```

## 命令行参数

命令行参数会覆盖环境变量：

| 参数 | 说明 |
| --- | --- |
| `--env-file PATH` | 指定启动时读取的 `.env` 文件。 |
| `--transport stdio|sse|streamable-http` | 覆盖 MCP 传输方式。 |
| `--host HOST` | 覆盖 HTTP/SSE 监听地址。 |
| `--port PORT` | 覆盖 HTTP/SSE 监听端口。 |
| `--workspace PATH` | 覆盖 `MCP_WORKSPACE`。 |
| `--auth-token TOKEN` | 设置 HTTP/SSE 请求头授权码。 |
| `--auth-header NAME` | 设置读取授权码的请求头名。 |
| `--stateless-http` / `--stateful-http` | 覆盖 `streamable-http` session 行为。 |
| `--plugin MODULE` | 加载插件模块，可重复使用，也可逗号分隔。 |
| `--allow-write` / `--disable-write` | 覆盖文件写入、复制、移动和删除开关。 |
| `--show-config` | 打印非敏感配置后退出。 |

## 客户端配置

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

`TAVILY_API_KEY` 可以省略；省略后 `web_search` 自动使用 DuckDuckGo HTML 搜索。

## 内置工具调用示例

以下示例通过 `FastMCP.call_tool()` 本地调用工具，接入 MCP 客户端后由客户端通过 MCP 协议调用。

### 列出工具

```sh
python - <<'PY'
import asyncio
from mcp_toolkit.server import create_server


async def main():
    server = create_server()
    for tool in await server.list_tools():
        print(tool.name)


asyncio.run(main())
PY
```

输出应只有：

```text
web_search
file_operation
agent
```

### 联网搜索

```sh
python - <<'PY'
import asyncio
from mcp_toolkit.server import create_server


async def main():
    server = create_server()
    result = await server.call_tool(
        "web_search",
        {"query": "Model Context Protocol Python SDK", "max_results": 3},
    )
    print(result)


asyncio.run(main())
PY
```

### 读取文件

```sh
MCP_WORKSPACE=/data/data/com.termux/files/home/mcp python - <<'PY'
import asyncio
from mcp_toolkit.server import create_server


async def main():
    server = create_server()
    result = await server.call_tool(
        "file_operation",
        {"action": "read", "path": "README.md", "max_chars": 2000},
    )
    print(result)


asyncio.run(main())
PY
```

### 写入文件

```sh
MCP_WORKSPACE=/data/data/com.termux/files/home/mcp \
MCP_ALLOW_WRITE=true \
python - <<'PY'
import asyncio
from mcp_toolkit.server import create_server


async def main():
    server = create_server()
    result = await server.call_tool(
        "file_operation",
        {
            "action": "write",
            "path": "tmp/demo.txt",
            "content": "hello from mcp\n",
            "overwrite": True
        },
    )
    print(result)


asyncio.run(main())
PY
```

### 文件查找和 grep

```sh
python - <<'PY'
import asyncio
from mcp_toolkit.server import create_server


async def main():
    server = create_server()
    print(await server.call_tool("file_operation", {"action": "find", "path": ".", "pattern": "*.md"}))
    print(await server.call_tool("file_operation", {"action": "grep", "path": ".", "pattern": "*.md", "query": "MCP"}))


asyncio.run(main())
PY
```

### agent 状态

```sh
python - <<'PY'
import asyncio
from mcp_toolkit.server import create_server


async def main():
    server = create_server()
    print(await server.call_tool("agent", {"action": "start", "task": "整理 README"}))
    print(await server.call_tool("agent", {"action": "update", "note": "已完成检查"}))
    print(await server.call_tool("agent", {"action": "finish", "note": "完成"}))


asyncio.run(main())
PY
```

## 插件扩展

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
export MCP_TOOLKIT_PLUGINS=examples.custom_tools,examples.math_tools
```

## 安全说明

- `file_operation` 只能访问 `MCP_WORKSPACE` 内路径。
- 写入、追加、替换、创建目录、复制、移动和删除默认关闭，需要 `MCP_ALLOW_WRITE=true`。
- 单个可读取文件受 `MCP_MAX_FILE_BYTES` 限制。
- 远程 HTTP/SSE 模式建议设置 `MCP_AUTH_TOKEN`，公网环境建议前置 HTTPS 反向代理。
- 不要把真实 API Key、token、密码写入源码或文档示例。

## 常见问题

### 只看到 3 个内置工具是否正常？

正常。当前内置工具只保留 `web_search`、`file_operation`、`agent`。更多能力通过插件扩展。

### web_search 使用 Tavily 提示缺少 API Key

当 `provider=tavily` 时必须设置：

```sh
export TAVILY_API_KEY='your-tavily-key'
```

默认 `provider=auto` 会在未配置 Key 时使用 DuckDuckGo HTML 搜索。

### file_operation 写入失败

默认禁止写入、替换、复制、移动和删除。需要显式开启：

```sh
export MCP_ALLOW_WRITE=true
```

### 文件路径被拒绝

传入路径越过了 `MCP_WORKSPACE` 边界。检查参数中是否包含 `..`、指向工作区外的符号链接或工作区外绝对路径。
