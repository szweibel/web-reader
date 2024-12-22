# Web Reader Architecture

This document explains the purpose and structure of each file in the web-reader project, which is a Model Context Protocol (MCP) server that helps blind users navigate web pages through voice feedback. The server provides real-time navigation, interaction, and voice feedback capabilities to make web content accessible to blind users.

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

Key handlers:
- `handleNavigateTo`: Opens and analyzes web pages
- `handleReadCurrent`: Reads currently focused element
- `handleNextElement`/`handlePreviousElement`: Navigation
- `handleListHeadings`: Page structure analysis
- `handleFindText`: Text search functionality

### src/types.ts
TypeScript type definitions for:

#### State Management
- `NavigationState`: Tracks browser state and navigation
  ```typescript
  {
    currentUrl: string | null;
    browser: Browser | null;
    page: Page | null;
    currentIndex: number;
  }
  ```

#### Response Types
- `ToolResponse`: Unified response format for all tools
  ```typescript
  {
    message?: string;          // Status or error messages
    description?: string;      // Detailed descriptions
    title?: string;           // Page title
    heading?: string;         // Main heading
    elementCount?: number;    // Total interactive elements
    elementIndex?: number;    // Current element position
    totalElements?: number;   // Total elements count
    headingCount?: number;    // Total headings
    matchCount?: number;      // Search result count
    // ... and more specific fields
  }
  ```

#### Element Information
- `ElementInfo`: Accessibility properties for elements
  ```typescript
  {
    role?: string;            // ARIA role
    ariaLabel?: string;       // Accessible label
    ariaDescribedby?: string; // Extended descriptions
    type: string;             // Element type
    text: string;             // Text content
    // ... and more properties
  }
  ```

These types ensure consistent data handling and proper accessibility information throughout the application.

### src/utils.ts
Helper functions and utilities:
- Text-to-speech integration
- Element description generation
- System dependency checks
- Browser state management
- Accessibility helper functions

## Configuration Files

### package.json
Project configuration including:

#### Dependencies
- `@modelcontextprotocol/sdk` (^1.0.4): MCP server framework for tool definitions and communication
- `puppeteer` (v22): Headless browser automation for web page interaction and DOM manipulation
- `say` (^0.16.0): Cross-platform text-to-speech for voice feedback
- `node-html-parser` (^4.0.13): [Deprecated] HTML parsing library, being phased out in favor of Puppeteer's native DOM manipulation

#### Scripts
- `build`: Compiles TypeScript source to JavaScript
- `start`: Runs the compiled server

#### Binary
The package provides a binary executable:
```json
"bin": {
  "web-reader": "./build/index.js"
}
```

This allows the server to be run directly from the command line when installed globally.

### tsconfig.json
TypeScript configuration:
- Modern Node.js target
- Strict type checking
- Module resolution settings
- Build output configuration

## Key Features Implementation

### Navigation
- Uses Puppeteer for browser control
- Maintains focus state across elements
- Provides context about current location
- Supports keyboard-like navigation

### Accessibility Implementation

#### Element Description Generation
```typescript
// Builds accessible descriptions following this priority:
1. ARIA Label: Uses aria-label if present
2. Role + Type: Combines ARIA role with element type
3. Input Type: Special handling for form controls
4. Element Content: Falls back to text content
5. Extended Info: Includes aria-describedby content

// State Information
- Required/Optional state
- Enabled/Disabled state
- Expanded/Collapsed state
- Checked/Unchecked state

// Example Outputs:
"search button (disabled)"
"email input: user@example.com (required)"
"navigation menu (expanded)"
```

#### Focus Management
- Maintains single active element
- Visual highlighting with .screen-reader-highlight class
- Smooth scrolling to keep element in view
- Proper focus order following DOM structure

#### Element Selection
```typescript
// Focusable elements query
a[href]:not([aria-hidden="true"]),
button:not([disabled]):not([aria-hidden="true"]),
input:not([disabled]):not([aria-hidden="true"]),
select:not([disabled]):not([aria-hidden="true"]),
textarea:not([disabled]):not([aria-hidden="true"]),
[tabindex]:not([tabindex="-1"]):not([aria-hidden="true"]),
[role="button"]:not([aria-hidden="true"]),
[role="link"]:not([aria-hidden="true"]),
[role="menuitem"]:not([aria-hidden="true"]),
[role="option"]:not([aria-hidden="true"])
```

### Voice Feedback Implementation

#### Text-to-Speech Integration
```typescript
// Async speech function with promise wrapper
private async speak(text: string): Promise<void> {
  return new Promise((resolve, reject) => {
    say.speak(text, undefined, undefined, (err) => {
      if (err) reject(err);
      else resolve();
    });
  });
}
```

#### Feedback Categories
1. Navigation Feedback
   - Page load: "Loaded [title]. Main heading: [h1]. Found [n] interactive elements."
   - Element focus: "[role] [text] ([states])"
   - Boundaries: "Reached end of page", "At start of page"

2. Search Feedback
   - Results: "Found [n] matches for [text]. First match: [match]"
   - No results: "Text [text] not found on page"

3. Error Feedback
   - Load errors: "Failed to load page: [error]"
   - Navigation errors: "Error moving to next element: [error]"
   - Search errors: "Error searching text: [error]"

## State Management

The server maintains several types of state:
1. Browser State:
   - Current page
   - Active element
   - Navigation history

2. Accessibility State:
   - Focus position
   - Element descriptions
   - Page structure

3. Server State:
   - Tool availability
   - Error conditions
   - Resource management

## Integration Points

### Claude Integration
- Responds to natural language commands
- Provides context-aware responses
- Maintains conversation state
- Handles error recovery

### Browser Integration
- Puppeteer-based automation
- Event handling
- State synchronization
- Resource cleanup

### System Integration
- Text-to-speech engine
- Browser dependencies
- File system access
- Process management

## Testing and Quality Assurance

### Accessibility Testing
- Screen reader compatibility testing
- Keyboard navigation verification
- Focus management testing
- ARIA attribute verification

### Browser Testing
- Page load handling
- Dynamic content updates
- Navigation state management
- Error recovery scenarios

### Voice Feedback Testing
- Text-to-speech accuracy
- Context-appropriate descriptions
- Error message clarity
- Navigation feedback

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
