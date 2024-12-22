# Web Reader MCP Server

A screen reader server that helps blind users navigate web pages through voice feedback.

## Prerequisites

- Node.js and npm
- Festival text-to-speech engine
- Chromium browser

## Installation

### 1. System Dependencies

First, install the required system dependencies:

```bash
# On Ubuntu/Debian:
sudo apt-get update
sudo apt-get install -y chromium-browser festival festvox-us-slt-hts
```

### 2. Install Web Reader

You have two options for installing the web reader:

#### Option A: Clone and Build
```bash
# Clone the repository
git clone /path/to/web-reader
cd web-reader

# Install dependencies and build
npm install
npm run build
```

#### Option B: Install from Local Package
If someone shared the package with you:
```bash
npm install /path/to/web-reader
```

### 3. Configure Claude

You need to add the web reader to your Claude configuration. The location depends on which Claude client you're using:

#### For VSCode Extension
Add to `.vscode-server/data/User/globalStorage/saoudrizwan.claude-dev/settings/cline_mcp_settings.json`:
```json
{
  "mcpServers": {
    "web-reader": {
      "command": "node",
      "args": ["/path/to/web-reader/build/index.js"],
      "env": {}
    }
  }
}
```

#### For Claude Desktop App
Add the same configuration to:
- macOS: `~/Library/Application Support/Claude/claude_desktop_config.json`
- Linux: `~/.config/Claude/claude_desktop_config.json`
- Windows: `%APPDATA%\\Claude\\claude_desktop_config.json`

## Usage

Once configured, you can interact with Claude using natural language commands. Here are some examples:

### Basic Navigation
```
You: Navigate to example.com
Claude: *navigates to the page and reads the title and summary*

You: List all headings on the page
Claude: *reads out all page headings*
```

### Finding Content
```
You: Find text "privacy policy"
Claude: *finds the text and reads the surrounding context*

You: Go to next element
Claude: *moves to and reads the next focusable element (link, button, etc.)*
```

### Available Commands
- **Navigation:**
  - "Navigate to [URL]" - Open a webpage
  - "Go to next element" - Move to next focusable item
  - "Go to previous element" - Move to previous focusable item
  - "Read current element" - Read the currently focused item

- **Page Analysis:**
  - "List all headings" - Get all page headings
  - "Find text [search term]" - Search for specific text

## Features

- Web page navigation with voice feedback
- Page heading navigation
- Text search functionality
- Focusable element navigation (links, buttons, inputs)
- Text-to-speech using Festival
- Works with both Claude VSCode extension and desktop app

## Troubleshooting

If you encounter any issues:

1. Check that Festival is working:
```bash
echo "Test" | festival --tts
```

2. Verify Chromium installation:
```bash
chromium-browser --version
```

3. Make sure the paths in your Claude configuration match your actual installation path

## Contributing

Feel free to submit issues and enhancement requests!
