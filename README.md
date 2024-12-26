# Web Reader

A natural language screen reader that helps users navigate and understand web content through conversation, powered by local LLMs and browser automation.

## Features

- Natural language commands for web navigation and interaction
- Smart content analysis and page type detection
- Structural navigation with headings and landmarks
- News article headline detection and reading
- Element navigation and interaction
- Accessibility-focused design with ARIA support
- Local LLM processing for privacy and speed

## Installation

1. Ensure you have Python 3.10 or later installed
2. Install Ollama and the llama3.2 model:
   ```bash
   # Install Ollama (instructions vary by OS)
   curl -fsSL https://ollama.com/install.sh | sh
   
   # Pull the model
   ollama pull llama3.2
   ```

3. Install the package:
   ```bash
   pip install -e .
   ```

## Usage

Start the screen reader:
```bash
web-reader
```

### Available Commands

- **Navigation**
  - "Go to example.com"
  - "Open website.com"
  - "Visit page.com"

- **Reading**
  - "Read the page"
  - "Read this section"
  - "List headlines" (for news sites)
  - "List headings" (for page structure)

- **Element Navigation**
  - "Next element"
  - "Previous element"
  - "Go to main content"
  - "List landmarks"

- **Interaction**
  - "Click the login button"
  - "Click the menu"
  - "Find text about pricing"

### Examples

```
What would you like me to do? go to nytimes.com
Navigated to https://nytimes.com. This appears to be a news page. News website homepage

What would you like me to do? list headlines
Found these news headlines:
• Biden Seeks Solace in Meeting with Pope Francis
• Trump's Clean Energy Policy Raises Investor Concerns
...

What would you like me to do? list headings
Found these headings:
H1: New York Times - Top Stories
H2: Top Stories
H2: Sections
...

What would you like me to do? click wirecutter
Clicked element: 'Wirecutter'. Would you like me to read the updated content?
```

## Architecture

The application uses a modular architecture with these key components:

- **LLM Integration**: Local language model for command understanding and content analysis
- **Action System**: Modular command handlers for navigation, reading, and interaction
- **State Management**: Tracks navigation state and page context
- **Browser Control**: Automated browser interaction with accessibility support

For more details, see [ARCHITECTURE.md](ARCHITECTURE.md).

## Development

### Project Structure

```
web-reader/
├── src/
│   ├── actions/          # Command handlers
│   │   ├── __init__.py
│   │   ├── navigation.py # URL and element navigation
│   │   ├── reading.py    # Content reading and analysis
│   │   ├── interaction.py # Element interaction
│   │   └── landmarks.py  # Landmark navigation
│   ├── utils/
│   │   ├── errors.py     # Error handling
│   │   └── logging.py    # Logging setup
│   ├── browser.py        # Browser automation
│   ├── config.py         # Configuration
│   ├── main.py          # Entry point
│   └── state.py         # State management
├── setup.py
└── README.md
```

### Adding New Actions

1. Create a new action function in the appropriate module under `src/actions/`
2. Use the `@register_action` decorator to register it
3. Add the action name to `VALID_ACTIONS` in `config.py`
4. Update the LLM prefix in `config.py` to help the model understand when to use the action

Example:
```python
from ..state import State
from . import register_action
from langgraph.graph import END

@register_action("my_action")
def my_action(state: State) -> dict:
    """Implement your action here"""
    return {
        "messages": [{"role": "assistant", "content": "Action result"}],
        "next": END
    }
```

## Contributing

Contributions are welcome! Please feel free to submit a Pull Request.

## License

This project is licensed under the MIT License - see the LICENSE file for details.
