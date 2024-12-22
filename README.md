# Web Reader MCP Server

A screen reader server that helps blind users navigate web pages through voice feedback.

## Prerequisites

- Node.js and npm
- System text-to-speech support (built into macOS, Windows, and most Linux distributions)
- Chrome/Chromium (will be installed automatically by Puppeteer if needed)

## Installation

### 1. System Dependencies

The text-to-speech capabilities are handled automatically by your operating system:
- macOS: Uses built-in 'say' command (no installation needed)
- Windows: Uses built-in SAPI (no installation needed)
- Linux: Uses Festival (will be installed automatically if needed)

Puppeteer will download and manage its own Chrome binary, so you don't need to install Chrome/Chromium separately.

### 2. Install Web Reader

```bash
# Clone the repository
git clone /path/to/web-reader
cd web-reader

# Install dependencies and build
npm install
npm run build
```

### 3. Configure Claude

You need to add the web reader to your Claude configuration. The location depends on which Claude client you're using:

#### For VSCode Extension (Cline)
Add to `~/Library/Application Support/Code/User/globalStorage/saoudrizwan.claude-dev/settings/cline_mcp_settings.json`:
```json
{
  "mcpServers": {
    "web-reader": {
      "command": "node",
      "args": ["/absolute/path/to/web-reader/build/index.js"],
      "env": {}
    }
  }
}
```

#### For Claude Desktop App
Add to:
- macOS: `~/Library/Application Support/Claude/claude_desktop_config.json`
- Linux: `~/.config/Claude/claude_desktop_config.json`
- Windows: `%APPDATA%\\Claude\\claude_desktop_config.json`

```json
{
  "mcpServers": {
    "web-reader": {
      "command": "node",
      "args": ["/absolute/path/to/web-reader/build/index.js"],
      "env": {}
    }
  }
}
```

Make sure to replace `/absolute/path/to/web-reader` with the actual path where you cloned the repository.

## Usage

Once configured, you can interact with Claude using natural language commands. Here are some examples:

### Commands

The web reader provides voice feedback for web pages through these commands:

```
navigate_to [url]     - Load a webpage and read its title and main content
read_current         - Read the current element
next_element        - Move to and read the next focusable element
previous_element    - Move to and read the previous element
list_headings       - List all headings on the page
find_text [text]    - Search for specific text on the page
```

Note: The web reader operates in headless mode (no visible browser window). It extracts content from web pages and provides voice feedback through your system's text-to-speech capabilities.

## Features

- Headless web page content extraction
- Voice feedback using system text-to-speech
- Page structure analysis (headings, landmarks)
- Text search functionality
- Focusable element navigation
- Cross-platform support
- Works with both Claude VSCode extension and desktop app

## Troubleshooting

If you encounter issues with the web reader, try these steps:

1. Verify the server is built correctly:
```bash
cd web-reader
npm run build
# Should create build/index.js and other files
```

2. Check the configuration file:
- Make sure you're using absolute paths
- Double-check the path to build/index.js exists
- Ensure there are no syntax errors in the JSON

3. Test the server directly:
```bash
cd web-reader
node build/index.js
# Should show: "Web Reader MCP server running on stdio"
```

4. Common issues and solutions:

- **"MCP server disconnected" error:**
  - Restart Claude/VSCode after changing configuration
  - Check if the server process is running
  - Verify the path in your configuration is correct

- **No voice feedback:**
  - On macOS: No setup needed, uses system 'say' command
  - On Windows: No setup needed, uses system SAPI
  - On Linux: Install festival if needed

- **Content extraction fails:**
  - Let Puppeteer manage its own Chrome binary
  - Check network connectivity
  - Verify the URL is accessible

5. Still having issues?
- Check the terminal output where you ran the server
- Look for error messages in Claude's console
- Make sure all dependencies are installed: `npm install`

## Contributing

Feel free to submit issues and enhancement requests!
