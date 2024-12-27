# Web Reader Architecture

The Web Reader is a screen reader application that combines LLMs, browser automation, and natural language processing to provide an accessible web browsing experience. This document outlines the core architectural components and their interactions.

## High-Level Architecture

```
┌─────────────────┐     ┌──────────────┐     ┌─────────────┐
│  LLM Interface  │────▶│ Action Graph │────▶│   Browser   │
│  (LangChain)    │     │ (LangGraph)  │     │ (Selenium)  │
└─────────────────┘     └──────────────┘     └─────────────┘
        ▲                      ▲                    ▲
        │                      │                    │
        └──────────────────────┴────────────────────┘
                    State Management
```

## Core Components

### 1. LLM Interface (LangChain)

- Uses Ollama for local LLM processing
- Handles natural language understanding
- Converts user commands into structured actions
- Provides JSON-formatted responses with:
  - Action type
  - Confidence score
  - Context information

### 2. Action Graph (LangGraph)

The action graph manages the flow of operations using a state machine approach:

```
┌──────────────┐     ┌──────────────┐     ┌──────────────┐
│  Determine   │────▶│   Execute    │────▶│   Continue   │
│    Action    │     │   Action     │     │    Check     │
└──────────────┘     └──────────────┘     └──────────────┘
        ▲                                        │
        └────────────────────────────────────────┘
```

#### State Management
- Messages: Command history and responses
- Browser state: Current page, elements
- Navigation state: Current element, landmarks
- Action context: Command parameters

#### Action Types
1. Navigation Actions
   - NAVIGATE: Go to URLs
   - NEXT_ELEMENT/PREV_ELEMENT: Element navigation
   - GOTO_LANDMARK: Section navigation

2. Reading Actions
   - READ: Page content
   - READ_SECTION: Section content
   - LIST_HEADINGS: Page structure
   - LIST_LANDMARKS: Page sections

3. Interaction Actions
   - CLICK: Element interaction
   - TYPE: Form input
   - FIND: Text search
   - CHECK_ELEMENT: Element properties

### 3. Browser Interface (Selenium)

- Headless Chrome automation
- Page content extraction
- Element interaction
- ARIA landmark detection
- Focusable element management

## Key Features

### 1. Natural Language Understanding
- Command interpretation using LLM
- Context-aware action selection
- Confidence scoring for reliability

### 2. Accessibility Features
- ARIA landmark navigation
- Semantic structure analysis
- Focusable element tracking
- Content summarization

### 3. State Management
- Persistent browser state
- Navigation history
- Element context
- Action chaining

## Implementation Details

### 1. Action Processing Pipeline

```
User Input → LLM Analysis → Action Selection → Execution → State Update → Response
```

### 2. State Graph Nodes

- determine_action: Command interpretation
- clarify: Low confidence handling
- navigate: URL navigation
- read_page: Content extraction
- click_element: Interaction
- check_element: Property inspection
- list_headings: Structure analysis
- find_text: Content search
- next_element/prev_element: Navigation
- list_landmarks: Section discovery
- goto_landmark: Section navigation
- read_section: Content reading
- continue_check: Flow control

### 3. Error Handling

- LLM parsing fallbacks
- Browser automation retry logic
- State recovery mechanisms
- User feedback loops

## Future Improvements

1. Enhanced LLM Integration
   - Better context understanding
   - Multi-turn conversations
   - Command disambiguation

2. Accessibility Features
   - Custom ARIA role handling
   - Enhanced content summarization
   - Dynamic content tracking

3. Performance Optimizations
   - State caching
   - Parallel processing
   - Resource management

4. User Experience
   - Command suggestions
   - Error recovery
   - Learning from interactions

## Development Guidelines

1. State Management
   - Always update state atomically
   - Validate state transitions
   - Maintain state consistency

2. Error Handling
   - Provide clear error messages
   - Implement recovery mechanisms
   - Log errors for debugging

3. Testing
   - Unit test action handlers
   - Integration test flows
   - End-to-end test scenarios

4. Documentation
   - Document state transitions
   - Maintain API documentation
   - Update architecture docs
