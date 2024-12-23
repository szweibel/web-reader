# Web Reader Architecture

This document explains the purpose and structure of the web-reader project, which is a Model Context Protocol (MCP) server that helps blind users navigate web pages through voice feedback. The server provides real-time navigation, interaction, and voice feedback capabilities to make web content accessible to blind users.

## Project Structure

```
web-reader/
├── src/                    # Source code directory
│   ├── index.ts           # Entry point and server initialization
│   ├── server.ts          # MCP server setup and tool definitions
│   ├── handlers.ts        # Core functionality implementations
│   ├── types.ts           # TypeScript type definitions
│   └── utils.ts           # Helper functions and utilities
├── package.json           # Project configuration and dependencies
├── tsconfig.json          # TypeScript configuration
└── README.md             # Project documentation
```

## Core Files

### src/index.ts
The entry point of the application that:
- Initializes the MCP server
- Sets up error handling
- Manages server lifecycle
- Handles cleanup on exit

### src/server.ts
Defines the MCP server configuration and tools:
- Sets up server capabilities
- Defines available tools and their schemas
- Routes tool requests to appropriate handlers
- Manages server state

### src/handlers.ts
Contains the core functionality implementations:
- Page navigation and analysis
- Element focus management
- Text-to-speech integration
- Accessibility feature implementations
- Browser interaction through Puppeteer

### src/types.ts
TypeScript type definitions for:
- Navigation state management
- Tool responses
- Element information
- Configuration options

### src/utils.ts
Helper functions and utilities:
- Text-to-speech integration
- Element description generation
- System dependency checks
- Browser state management

## Key Features

### Navigation
- Uses Puppeteer for browser control
- Maintains focus state across elements
- Provides context about current location
- Supports keyboard-like navigation

### Accessibility
- ARIA attribute handling
- Focus management
- Screen reader compatibility
- Keyboard navigation support

### Voice Feedback
- Text-to-speech integration
- Context-aware descriptions
- Priority-based speech queue
- Interrupt support

## Testing Architecture

The project employs a focused, incremental testing strategy using Jest and Puppeteer. The approach prioritizes reliability and maintainability while allowing for careful expansion of test coverage.

### Core Test Files

Located in `src/__tests__/`:

1. **browser.test.ts**
   - Tests real browser interactions
   - Uses example.com for consistency
   - Verifies core navigation
   - Tests element selection
   - Validates content extraction

2. **mcp.test.ts**
   - Tests handler functionality
   - Verifies error cases
   - Tests state management
   - Validates initialization

3. **setup.ts**
   - Provides shared test utilities
   - Implements mocks
   - Configures test environment

### Test Implementation Strategy

#### Browser Testing
```typescript
// Example of browser interaction test
it('should find heading', async () => {
  const h1 = await page.$('h1');
  expect(h1).toBeTruthy();
  
  const text = await page.evaluate(el => el?.textContent || '', h1);
  expect(text).toBe('Example Domain');
});
```

#### Handler Testing
```typescript
// Example of handler error test
it('should handle missing page', async () => {
  const handlers = new PageHandlers({
    currentUrl: null,
    browser: null,
    page: null,
    currentIndex: 0,
    currentElement: null,
    navigationType: 'all'
  });

  await expect(handlers.handleReadCurrent())
    .rejects.toThrow('No page is currently open');
});
```

### Test Categories

1. **Core Browser Tests**
   - Navigation
   - Element selection
   - Content extraction
   - Page structure

2. **Handler Tests**
   - Error handling
   - State management
   - Input validation
   - Initialization

### Future Test Expansion

When adding new tests:

1. **Start Simple**
   - Basic functionality first
   - Use stable test sites
   - Focus on core features
   - Clear test descriptions

2. **Add Complexity Gradually**
   - Error cases
   - Edge cases
   - Performance scenarios
   - Integration tests

3. **Consider Categories**
   - Navigation features
   - Accessibility features
   - Error scenarios
   - Performance aspects

4. **Maintain Quality**
   - Clear documentation
   - Proper cleanup
   - Reliable assertions
   - TypeScript safety

## Development Guidelines

### Accessibility Best Practices
- Follow WCAG guidelines
- Maintain proper focus management
- Provide clear audio feedback
- Support keyboard navigation

### Error Handling
- Graceful degradation
- Clear error messages
- State recovery
- Resource cleanup

### Performance
- Efficient DOM traversal
- Memory management
- Browser resource handling
- State management
