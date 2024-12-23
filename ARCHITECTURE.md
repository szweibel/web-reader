# Web Reader Architecture

This document explains the purpose and structure of the web-reader project, which is an Electron-based accessibility application that helps blind users navigate web pages through voice feedback and LLM-enhanced descriptions. The app integrates a local LLM for enhanced content understanding and navigation assistance, with an MCP server for standardized tool access.

## Project Structure

```
web-reader/
├── src/                    # Core MCP server source code
│   ├── index.ts           # MCP server entry point
│   ├── server.ts          # MCP server setup and tools
│   ├── handlers.ts        # Core MCP functionality
│   ├── types.ts           # TypeScript type definitions
│   └── utils.ts           # Helper functions
├── web-reader-electron/   # Electron app source code
│   ├── src/
│   │   ├── main/         # Main process code
│   │   │   ├── index.ts  # Main entry point
│   │   │   ├── llm.ts    # LLM integration
│   │   │   └── ipc.ts    # IPC handlers
│   │   └── renderer/     # Renderer process code
│   ├── models/           # LLM model files
│   └── package.json      # Electron app dependencies
├── package.json           # MCP server dependencies
└── README.md             # Project documentation
```

## Core Components

### Electron App (web-reader-electron/)
The main application that provides:
- Desktop UI for accessibility settings
- Local LLM integration for enhanced understanding
- Browser automation through Puppeteer
- IPC system for component communication
- Model management and optimization

### MCP Server (src/)
A standardized interface that:
- Provides navigation and interaction tools
- Communicates with the LLM for enhancements
- Manages browser state and focus
- Handles voice feedback

### LLM Integration (web-reader-electron/src/main/llm.ts)
Local language model that provides:
- Enhanced content descriptions
- Navigation suggestions
- Context-aware assistance
- Privacy-focused processing

## Key Features

### Navigation
- LLM-enhanced page understanding
- Intelligent element selection
- Context-aware navigation
- Voice-guided browsing

### Accessibility
- Screen reader integration
- Keyboard navigation
- ARIA support
- Custom voice options

### Local Processing
- Offline-first approach
- Privacy protection
- Fast response times
- Resource optimization

## Development Guidelines

### Architecture Principles
- Keep LLM in Electron main process
- Use MCP for standardized tool access
- Maintain clear component boundaries
- Optimize for accessibility

### Performance
- Lazy model loading
- Efficient IPC communication
- Memory management
- Browser resource handling

### Error Handling
- Graceful degradation
- Clear error messages
- State recovery
- Resource cleanup

### Testing
- Component isolation
- Integration testing
- Accessibility validation
- Performance benchmarking

## Implementation Details

### Electron Main Process
```typescript
// web-reader-electron/src/main/index.ts
import { app, BrowserWindow } from 'electron';
import { LLMManager } from './llm';
import { setupIPC } from './ipc';

class WebReader {
  private window: BrowserWindow;
  private llm: LLMManager;

  async init() {
    this.llm = new LLMManager();
    await this.llm.init();
    setupIPC(this.llm);
    this.createWindow();
  }
}
```

### LLM Integration
```typescript
// web-reader-electron/src/main/llm.ts
export class LLMManager {
  async enhanceDescription(content: string): Promise<string> {
    // Process content through local LLM
    return enhancedDescription;
  }

  async suggestNavigation(content: string, intent: string): Promise<string> {
    // Generate navigation suggestions
    return suggestions;
  }
}
```

### MCP Tools
```typescript
// src/server.ts
export class WebReaderServer {
  async handleEnhanceDescription(content: string) {
    // Request enhancement from Electron's LLM
    return await ipcRenderer.invoke('enhance-description', content);
  }

  async handleSuggestNavigation(content: string, intent: string) {
    // Request navigation help from Electron's LLM
    return await ipcRenderer.invoke('suggest-navigation', { content, intent });
  }
}
```

## Future Development

### Short Term
- [ ] Performance optimization
- [ ] Additional language models
- [ ] Enhanced error recovery
- [ ] User preferences system

### Long Term
- [ ] Custom voice synthesis
- [ ] Plugin system
- [ ] Multi-language support
- [ ] Advanced navigation modes

This architecture provides a robust foundation for an accessible web browsing experience, combining the power of local AI with standardized accessibility tools.
