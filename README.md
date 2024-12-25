# Web Reader

A screen reader application that helps users navigate web pages through natural language commands and LLM-enhanced descriptions. Built with LangGraph for intelligent flow control and Selenium for web automation.

## Features

- Natural language command processing using local LLMs
- Intelligent navigation with LangGraph state management
- ARIA landmark and semantic structure analysis
- Focusable element navigation
- Content summarization and search
- Cross-platform support
- Privacy-focused (all processing happens locally)

## Prerequisites

- Python 3.10 or higher
- Chrome/Chromium (will be installed automatically by Selenium)
- Ollama for local LLM processing

## Installation

```bash
# Clone the repository
git clone /path/to/web-reader
cd web-reader

# Create and activate virtual environment
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate

# Install dependencies
pip install -r requirements.txt
```

## Usage

The web reader provides a natural language interface for web navigation and accessibility. Start the application:

```bash
python another.py
```

### Example Commands

#### Navigation
- "Go to example.com"
- "Next element"
- "Previous element"
- "Go to main content"

#### Reading
- "Read the page"
- "Read this section"
- "List headings"
- "List landmarks"

#### Interaction
- "Click the login button"
- "Type my email test@example.com into the email field"
- "Find text about pricing"
- "Is this a clickable element?"

## Architecture

The application uses a three-tier architecture:

1. **LLM Interface (LangChain)**
   - Natural language understanding
   - Command interpretation
   - Context management

2. **Action Graph (LangGraph)**
   - State machine for flow control
   - Action execution
   - Error handling

3. **Browser Interface (Selenium)**
   - Web page automation
   - Content extraction
   - Element interaction

For detailed architecture information, see [ARCHITECTURE.md](ARCHITECTURE.md).

## Development

### Project Structure

```
web-reader/
├── another.py          # Main application
├── ARCHITECTURE.md     # Architecture documentation
├── README.md          # Project documentation
├── requirements.txt   # Python dependencies
└── venv/             # Virtual environment
```

### Testing

Run the test suite:

```bash
pytest
```

### Contributing

1. Fork the repository
2. Create a feature branch
3. Write tests for new functionality
4. Ensure all tests pass
5. Submit a pull request

## Troubleshooting

### Common Issues

1. **LLM Issues**
   - Ensure Ollama is running
   - Check model availability
   - Verify JSON parsing

2. **Browser Issues**
   - Let Selenium manage Chrome
   - Check network connectivity
   - Verify page accessibility

3. **State Management**
   - Check state transitions
   - Verify action context
   - Monitor error handling

## License

MIT License - see LICENSE file for details
