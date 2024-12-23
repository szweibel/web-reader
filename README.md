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

### Natural Voice Commands

The web reader understands natural language commands for web navigation. Here are some examples:

#### Basic Navigation
- "Go to [website]" or "Open [url]" - Navigate to a webpage
- "Read this" or "What's this?" - Read the current element
- "Next" or "Move forward" - Go to next element
- "Back" or "Previous" - Go to previous element
- "Stop" - Stop current speech

#### Page Structure
- "Show headings" or "List headings" - List all headings on page
- "Go to landmarks" - Switch to landmark navigation (main content, navigation, etc.)
- "Show landmarks" - List all landmarks on page

#### Heading Navigation
- "Go to headings" - Switch to heading navigation
- "Level [1-6]" - Filter headings by level
- "Higher level" or "Level up" - Move to higher heading level
- "Lower level" or "Level down" - Move to lower heading level

#### Search
- "Find [text]" or "Search for [text]" - Search for text on page
- "Where am I?" - Get current location context

The web reader will provide voice feedback for all actions and help you navigate the page structure efficiently. You can use these commands naturally in conversation with Claude, for example:
- "Can you go to wikipedia.org and read the main content?"
- "Find the navigation menu on this page"
- "What headings are on this page?"
- "Take me to the next heading"

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

## Development

### Project Structure

The project uses TypeScript and follows a modular architecture:

- `src/`
  - `index.ts` - Main entry point and MCP server setup
  - `server.ts` - Web reader server implementation
  - `handlers.ts` - Tool handlers for navigation and reading
  - `utils.ts` - Utility functions for speech and element handling
  - `types.ts` - TypeScript type definitions
  - `__tests__/` - Test files

### Testing

The project uses Jest with comprehensive test coverage across multiple test environments:

1. Server Tests (`server.test.ts`)
   - MCP server functionality and tool registration
   - Request/response handling and validation
   - Server lifecycle management
   - Error handling and recovery

2. Browser Tests (`handlers.test.ts`)
   - Page navigation and content extraction
   - Dynamic content handling
   - Live region updates
   - Error scenarios and retries
   - Accessibility descriptions
   - Element selection and focus management

3. Utility Tests (`utils.test.ts`)
   - Speech synthesis and queue management
   - Priority-based message handling
   - Element description generation
   - Dependency checks and system integration
   - Error handling and recovery

Current test coverage:
- Statements: 75.45%
- Branches: 76%
- Functions: 85%
- Lines: 74.03%

Testing tools and libraries:
- Jest: Test runner and assertion library
- Puppeteer: Headless browser automation
- jest-puppeteer: Browser testing integration
- pptr-testing-library: Accessibility testing utilities

The testing suite focuses on:
1. Accessibility Features
   - ARIA attribute handling
   - Screen reader compatibility
   - Keyboard navigation
   - Focus management

2. Error Handling
   - Network failures
   - Invalid states
   - Resource cleanup
   - Queue management

3. Edge Cases
   - Empty/malformed content
   - Concurrent operations
   - Resource limitations
   - Timeout scenarios

To run tests:
```bash
# Run all tests with coverage
npm test

# Run tests in watch mode
npm run test:watch

# Run specific test file
npm test src/__tests__/utils.test.ts
```

Test files are organized by functionality:
- `server.test.ts`: MCP server and tool tests
- `handlers.test.ts`: Browser automation and accessibility tests
- `utils.test.ts`: Speech synthesis and utility tests
- `setup.ts`: Mock implementations and test helpers

Each test file follows accessibility-first testing practices and includes comprehensive error handling and edge case coverage.

### Test Configuration

The project uses separate Jest configurations for server and browser tests:

1. Server Tests:
   - Uses `ts-jest` preset
   - Node test environment
   - Mocks MCP server interactions

2. Browser Tests:
   - Uses `jest-puppeteer` preset
   - Headless browser environment
   - Real browser interactions

Configuration files:
- `jest.config.cjs` - Main Jest configuration
- `jest-puppeteer.config.cjs` - Puppeteer-specific settings

## Contributing

Feel free to submit issues and enhancement requests! When contributing code:

1. Fork the repository
2. Create a feature branch
3. Write tests for new functionality
4. Ensure all tests pass
5. Submit a pull request
