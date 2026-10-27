# ROS 2 MCP Server

A Model Context Protocol (MCP) server for ROS 2, enabling AI assistants like GitHub Copilot to introspect and interact with ROS 2 systems.

[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)
[![Python 3.8+](https://img.shields.io/badge/python-3.8+-blue.svg)](https://www.python.org/downloads/)

## Features

The ROS 2 MCP Server provides 30+ tools for comprehensive ROS 2 system interaction:

- **Node Management**: List and inspect running nodes
- **Topic Operations**: List, echo, publish, and get topic information
- **Service Operations**: List services, inspect types, and call services
- **Parameter Management**: List, get, and set node parameters
- **Action Operations**: List actions, get info, and send goals
- **Bag Operations**: Record, play, and inspect bag files
- **Interface Inspection**: List and show message/service/action definitions
- **Package Management**: List packages, executables, and manifests
- **Launch Operations**: List and execute launch files with parameters
- **Lifecycle Management**: Control lifecycle nodes and transitions
- **Diagnostics**: Run system health checks with `ros2 doctor`

## Installation

### Quick Install

```bash
git clone https://github.com/ranch-hand-robotics/rde-mcp-ros-2.git
cd rde-mcp-ros-2
./install.sh
```

For detailed installation instructions including platform-specific configuration, see **[INSTALLATION.md](INSTALLATION.md)**.

### Requirements

- **ROS 2**: Humble, Iron, Jazzy, or later
- **Python**: 3.8 or later
- **Operating System**: Linux (Ubuntu recommended), macOS, or Windows with WSL2

## Installation

### Option 1: Install from Source (Development)

```bash
# Clone the repository
git clone https://github.com/ranch-hand-robotics/rde-mcp-ros-2.git
cd rde-mcp-ros-2

# Install in editable mode
pip install -e .
```

### Option 2: Install from GitHub (Coming Soon)

```bash
# Install via copilot CLI (planned)
gh copilot plugin install ranch-hand-robotics/rde-mcp-ros-2
```

### ROS 2 Environment Setup

The server requires ROS 2 to be sourced in your environment. Add to your `~/.bashrc`:

```bash
# Replace 'humble' with your ROS 2 distro
source /opt/ros/humble/setup.bash
```

Or source it before running:

```bash
source /opt/ros/<distro>/setup.bash
rde-mcp-ros2
```

## Usage

### Configuring Your AI Assistant

The MCP server uses **stdio (standard input/output)** transport, which means it's launched automatically by your AI tool when needed. No need to start a separate server!

The server works with:
- **VS Code + GitHub Copilot** - See [examples/README.md](examples/README.md)
- **GitHub Copilot CLI** - See [INSTALLATION.md](INSTALLATION.md#option-2-github-copilot-cli)
- **Claude Desktop** - See [INSTALLATION.md](INSTALLATION.md#option-3-claude-desktop)

Quick config for VS Code (`.vscode/mcp.json`):
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

The server will be automatically started by the AI assistant when you ask ROS 2 questions!

### Optional: Running in SSE Mode

If you need to run the server as a standalone HTTP server (for remote access or debugging):

```bash
# Start in SSE mode
rde-mcp-ros2 --transport sse --port 3002

# Or use the wrapper
./run-server.sh --transport sse
```

Then configure your client to use SSE:
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

### Example Interactions

Once configured, ask your AI assistant:

- "What ROS 2 nodes are currently running?"
- "Show me the topics being published"
- "What's the current value of the /robot/speed parameter?"
- "Call the /reset_simulation service"
- "Record a bag file of all sensor topics for 30 seconds"
- "What packages are installed in my ROS 2 workspace?"

For more detailed examples, see [examples/USAGE_EXAMPLES.md](examples/USAGE_EXAMPLES.md).

## Documentation

- **[INSTALLATION.md](INSTALLATION.md)** - Detailed installation and configuration guide
- **[examples/README.md](examples/README.md)** - Configuration examples for different platforms  
- **[examples/USAGE_EXAMPLES.md](examples/USAGE_EXAMPLES.md)** - Real-world usage scenarios
- **[mcp-manifest.yaml](mcp-manifest.yaml)** - Full server capabilities manifest

## Development

### Setting Up Development Environment

```bash
# Clone and enter directory
git clone https://github.com/ranch-hand-robotics/rde-mcp-ros-2.git
cd rde-mcp-ros-2

# Install with dev dependencies
pip install -e ".[dev]"

# Run tests (when available)
pytest

# Format code
black src/
ruff check src/
```

### Debugging

Use SSE mode for easier debugging:

1. Run the server directly:
```bash
source /opt/ros/<distro>/setup.bash
python src/rde_mcp_ros2/server.py
```

2. Configure VS Code to connect via SSE (see `.vscode/mcp.json` above)

3. Watch logs in the terminal where the server is running

## Project Structure

```
rde-mcp-ros-2/
├── src/
│   └── rde_mcp_ros2/
│       ├── __init__.py
│       └── server.py          # Main MCP server implementation
├── pyproject.toml             # Package configuration
├── requirements.txt           # Python dependencies
├── README.md
└── LICENSE
```

## Contributing

Contributions are welcome! Please:

1. Fork the repository
2. Create a feature branch (`git checkout -b feature/amazing-feature`)
3. Commit your changes (`git commit -m 'Add amazing feature'`)
4. Push to the branch (`git push origin feature/amazing-feature`)
5. Open a Pull Request

## License

This project is licensed under the MIT License - see the [LICENSE](LICENSE) file for details.

## Credits

Developed by **Ranch Hand Robotics**

## Links

- [GitHub Repository](https://github.com/ranch-hand-robotics/rde-mcp-ros-2)
- [Model Context Protocol Documentation](https://modelcontextprotocol.io/)
- [ROS 2 Documentation](https://docs.ros.org/)




