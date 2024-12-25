# Web Reader

A screen reader application that helps blind users navigate web pages through voice feedback and LLM-enhanced descriptions using node-llama-cpp.

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

### 3. Download LLM Model

The application uses the Llama-3.2-3B-Instruct-Q6_K model for local processing. You'll need to download this model and place it in the `models/` directory.

## Usage

The web reader provides several chat functions for web navigation and accessibility:

### Available Functions

#### Basic Navigation
- `readCurrent`: Read the current element or page content
- `nextElement`: Move to and read the next focusable element
- `previousElement`: Move to and read the previous focusable element

#### Page Structure
- `listHeadings`: List all headings on the page

#### Search
- `findText`: Find and read text on the page

Each function takes a URL parameter to specify which page to interact with, and some functions (like `findText`) take additional parameters for their specific functionality.

## Features

- Local LLM processing using node-llama-cpp
- Voice feedback using system text-to-speech
- Page structure analysis (headings, landmarks)
- Text search functionality
- Focusable element navigation
- Cross-platform support
- Privacy-focused (all processing happens locally)

## Troubleshooting

If you encounter issues with the web reader, try these steps:

1. Verify the build:
```bash
cd web-reader
npm run build
```

2. Check the model:
- Ensure the Llama model is downloaded and placed in the correct directory
- Verify the model path in the configuration

3. Test the LLM:
```bash
cd web-reader
node test-llm-simple.mjs
```

4. Common issues and solutions:

- **Model loading fails:**
  - Check if the model file exists in the correct location
  - Verify file permissions
  - Ensure enough system memory is available

- **No voice feedback:**
  - On macOS: No setup needed, uses system 'say' command
  - On Windows: No setup needed, uses system SAPI
  - On Linux: Install festival if needed

- **Content extraction fails:**
  - Let Puppeteer manage its own Chrome binary
  - Check network connectivity
  - Verify the URL is accessible

## Development

### Project Structure

```
web-reader/
├── llm/                   # LLM integration
│   └── reader.mjs        # Core chat function implementations
├── main/                 # Main process code
│   ├── download-model.js # Model download utility
│   ├── index.js         # Main entry point
│   ├── ipc.js           # IPC handlers
│   └── llm.js           # LLM integration
├── models/               # LLM model files
├── renderer/             # Renderer process code
│   └── index.html       # Main UI
├── src/                 # Source code
│   └── __tests__/      # Test files
└── types/               # TypeScript type definitions
```

### Testing

The project uses Jest for testing:

1. Chat Function Tests
   - Function registration and validation
   - Parameter handling
   - Error scenarios
   - Response formatting

2. Browser Tests
   - Page navigation and content extraction
   - Dynamic content handling
   - Error scenarios and retries

3. Integration Tests
   - End-to-end workflow testing
   - System integration
   - Performance testing

To run tests:
```bash
# Run all tests
npm test

# Run tests in watch mode
npm run test:watch
```

## Contributing

Feel free to submit issues and enhancement requests! When contributing code:

1. Fork the repository
2. Create a feature branch
3. Write tests for new functionality
4. Ensure all tests pass
5. Submit a pull request
