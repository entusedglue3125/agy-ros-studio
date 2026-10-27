# Example MCP Configurations

This directory contains example configurations for using the ROS 2 MCP Server with different platforms.

The server uses **stdio (standard input/output)** transport by default, which is the recommended mode for MCP servers.

## Important: Environment Requirements

Unlike pure Python MCP servers that can use `uvx` or `pipx run`, the ROS 2 MCP Server requires the **ROS 2 environment to be sourced**. This means you should use the **wrapper script** (`run-server.sh`) instead of calling the Python package directly.

### Why the Wrapper Script?

The wrapper script:
- ✅ Automatically detects and sources ROS 2 environment
- ✅ Sets up PATH correctly
- ✅ Provides helpful error messages if ROS not found
- ✅ Works across all platforms

## VS Code / GitHub Copilot

Copy to your project's `.vscode/mcp.json`:

```json
{
  "servers": {
    "ros2": {
      "command": "${workspaceFolder}/run-server.sh",
      "args": []
    }
  }
}
```

**Note:** `${workspaceFolder}` automatically expands to your project directory in VS Code.

If the repo is cloned elsewhere, use full path:

```json
{
  "servers": {
    "ros2": {
      "command": "/home/user/rde-mcp-ros-2/run-server.sh",
      "args": []
    }
  }
}
```

## GitHub Copilot CLI

Add to `~/.copilot/mcp-config.json`:

```json
{
  "mcpServers": {
    "ros2": {
      "command": "/home/user/rde-mcp-ros-2/run-server.sh",
      "args": []
    }
  }
}
```

**Replace `/home/user/rde-mcp-ros-2`** with your actual installation path.

Or use the CLI command:
```bash
copilot
/mcp add ros2
# Command: /full/path/to/rde-mcp-ros-2/run-server.sh
# Args: (leave empty)
```

## Claude Desktop

### macOS
Edit `~/Library/Application Support/Claude/claude_desktop_config.json`:

```json
{
  "mcpServers": {
    "ros2": {
      "command": "/Users/yourname/rde-mcp-ros-2/run-server.sh",
      "args": []
    }
  }
}
```

### Linux
Edit `~/.config/claude/claude_desktop_config.json`:

```json
{
  "mcpServers": {
    "ros2": {
      "command": "/home/yourname/rde-mcp-ros-2/run-server.sh",
      "args": []
    }
  }
}
```

### Windows
Edit `%APPDATA%\Claude\claude_desktop_config.json`:

```json
{
  "mcpServers": {
    "ros2": {
      "command": "C:\\path\\to\\rde-mcp-ros-2\\run-server.sh",
      "args": []
    }
  }
}
```

## Alternative: ROS in Shell Profile

If you've added ROS to your shell profile (`~/.bashrc` or `~/.zshrc`):

```bash
source /opt/ros/humble/setup.bash
export PATH="$HOME/.local/bin:$PATH"
```

Then you can use the simpler configuration:

```json
{
  "servers": {
    "ros2": {
      "command": "rde-mcp-ros2",
      "args": []
    }
  }
}
```

**Caveat:** This only works if your AI tool inherits your shell environment. The wrapper script is more reliable.

## Using SSE Mode (Optional)

If you prefer to run the server as an HTTP server with Server-Sent Events:

1. Start the server in SSE mode:
   ```bash
   ./run-server.sh --transport sse --port 3002
   ```

2. Configure your client for SSE:
   ```json
   {
     "servers": {
       "ros2": {
         "type": "sse",
         "url": "http://localhost:3002/sse"
       }
     }
   }
   ```

**Note:** stdio mode (default) is simpler and more reliable for local development. Use SSE only if you need remote access or have specific requirements.

## Environment Variables

If you need to set ROS-specific environment variables:

```json
{
  "servers": {
    "ros2": {
      "command": "/path/to/rde-mcp-ros-2/run-server.sh",
      "args": [],
      "env": {
        "ROS_DOMAIN_ID": "42",
        "RMW_IMPLEMENTATION": "rmw_cyclonedds_cpp"
      }
    }
  }
}
```

## Finding Your Installation Path

```bash
cd rde-mcp-ros-2
pwd
# Use this path in your MCP configuration
```

## Why Not Use `uvx` or `pipx run`?

For pure Python MCP servers, you can use:
```json
{
  "command": "uvx",
  "args": ["some-mcp-server"]
}
```

However, **this doesn't work for ROS 2 MCP Server** because:
- `rclpy` is not available on PyPI
- ROS 2 environment must be sourced first
- See [MCP_INSTALLATION_OPTIONS.md](../MCP_INSTALLATION_OPTIONS.md) for details

## Repository-Specific Configuration

For team projects, commit `.vscode/mcp.json` to your repository with:

```json
{
  "servers": {
    "ros2": {
      "command": "${workspaceFolder}/../rde-mcp-ros-2/run-server.sh",
      "args": []
    }
  }
}
```

Just make sure all team members clone `rde-mcp-ros-2` to the same relative location.
