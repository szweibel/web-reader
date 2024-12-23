# Web Reader Electron App

## Overview

The Web Reader Electron app enhances web accessibility by combining:
1. A local LLM (llama-2) for private, offline AI assistance
2. LangChain for AI agent capabilities
3. The web-reader MCP server's accessibility tools
4. An Electron-based desktop interface

## Architecture

### Components

1. **Local LLM**
   - Uses llama-2 for offline processing
   - Runs directly on user's computer
   - Ensures privacy of browsing data
   - Provides AI capabilities without cloud dependency

2. **Web Reader MCP Server**
   - Core accessibility features for blind users
   - Navigation tools (headings, landmarks, elements)
   - Content reading and interaction
   - Running as a separate process

3. **Electron App**
   - Desktop UI for blind users
   - Manages local LLM and LangChain agent
   - Handles text-to-speech
   - Communicates with MCP server

4. **LangChain Integration**
   - Creates AI agent using local LLM
   - Uses mcp-langchain-ts-client to access MCP tools
   - Provides intelligent navigation assistance
   - Enhances content understanding

### How It Works

1. The Electron app starts up and:
   - Creates a window with accessibility features
   - Initializes the local LLM
   - Creates LangChain agent with local LLM
   - Connects to web-reader MCP server via mcp-langchain-ts-client

2. When a user wants to browse:
   - The LangChain agent (powered by local LLM) gets access to MCP tools
   - Uses these tools to help navigate and understand content
   - Provides enhanced descriptions and suggestions
   - All processing happens locally for privacy

3. The web-reader MCP server:
   - Handles actual web page interaction
   - Provides accessibility tools
   - Returns content in screen-reader friendly format

## Development Process

1. **Project Setup**
   ```bash
   # Clone and install dependencies
   git clone [repository-url]
   cd web-reader-electron
   npm install

   # Build and run
   npm run build
   npm start
   ```

2. **Project Structure**
   ```
   web-reader-electron/
   ├── src/
   │   ├── main/
   │   │   ├── index.ts     # Main process entry
   │   │   ├── llm.ts       # LLM integration
   │   │   ├── ipc.ts       # IPC handlers
   │   │   └── download-model.ts  # Model management
   │   ├── renderer/
   │   │   └── index.html   # UI implementation
   │   └── preload.ts       # IPC bridge
   └── build/               # Compiled output
   ```

3. **Key Components**

   a. **Main Process** (src/main/index.ts)
   - Window management
   - IPC setup
   - LLM initialization
   - Error handling

   b. **LLM Integration** (src/main/llm.ts)
   - Local model initialization
   - LangChain agent setup
   - MCP toolkit integration
   - Error handling

   c. **IPC System** (src/main/ipc.ts, preload.ts)
   - URL processing
   - Text-to-speech
   - Error handling
   - Context isolation

   d. **UI** (src/renderer/index.html)
   - URL input
   - Content display
   - ARIA support
   - Keyboard navigation

4. **Current Implementation**

   a. **LLM Features**
   - Local llama-2 model
   - Basic prompt templates
   - Error handling
   - Model download management

   b. **Accessibility**
   - Screen reader support
   - Keyboard navigation
   - ARIA live regions
   - Text-to-speech

   c. **MCP Integration**
   - Web navigation tools
   - Content reading
   - Error handling
   - Tool routing

5. **Development Workflow**
   ```bash
   # Start in development mode
   npm run dev

   # Build for production
   npm run build
   npm start
   ```

6. **Testing**
   - Test URL navigation
   - Verify screen reader compatibility
   - Check keyboard navigation
   - Test LLM enhancements

## Testing

1. First test basic Electron features:
   - Window creation
   - Text-to-speech
   - Basic navigation

2. Then test MCP integration:
   - Connection to web-reader server
   - Basic tool functionality
   - Navigation and reading

3. Finally test LLM features:
   - Local LLM initialization
   - AI agent functionality
   - Enhanced descriptions
   - Navigation assistance

## Privacy & Performance

- All AI processing happens locally using llama-2
- No data sent to external services
- Performance depends on local hardware
- Model can be optimized for different hardware capabilities
