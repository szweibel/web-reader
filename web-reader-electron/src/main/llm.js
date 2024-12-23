const { downloadModel } = require('./download-model');

// Dynamic imports for all ES modules
let MCPToolkit, getLlama, LlamaChatSession;
async function importDeps() {
  const [
    { MCPToolkit: MCPToolkitClass },
    { getLlama: getLlamaFn, LlamaChatSession: LlamaChatSessionClass }
  ] = await Promise.all([
    import('mcp-langchain-ts-client'),
    import('node-llama-cpp')
  ]);
  MCPToolkit = MCPToolkitClass;
  getLlama = getLlamaFn;
  LlamaChatSession = LlamaChatSessionClass;
}

class LLMManager {
  constructor() {
    this.enabled = false;
    this.toolkit = null;
    this.model = null;
    this.context = null;
    this.session = null;
    this.agent = null;
  }

  async init() {
    try {
      console.log('Initializing Web Reader...');
      
      // Import dependencies and initialize MCP toolkit
      await importDeps();
      this.toolkit = new MCPToolkit({
        command: 'node',
        args: ['/Users/stephenzweibel/Apps/web-reader/build/index.js']
      });
      await this.toolkit.initialize();
      console.log('MCP toolkit initialized');

      // Initialize LLM
      const modelPath = await downloadModel((progress) => {
        console.log(`Downloading model: ${progress.toFixed(1)}%`);
      });
      
      // Log model path for debugging
      console.log('Loading model from:', modelPath);
      
      // Initialize LLM
      const llama = await getLlama({
        modelPath,
        enableLogging: true,
        nCtx: 2048,
        nThreads: 4,
        seed: 0,
        f16Kv: true,
        embedding: false
      });
      this.model = llama;
      
      this.session = new LlamaChatSession({
        llama: this.model,
        contextSize: 2048,
        temperature: 0.7,
        maxTokens: 2000
      });
      
      console.log('LLM initialized');
      this.enabled = true;
      console.log('Web Reader fully initialized');
    } catch (error) {
      console.error('Failed to initialize:', error);
      this.enabled = false;
    }
  }

  async enhanceDescription(content) {
    if (!this.enabled || !this.session) {
      return `Loading content: ${content}`;
    }

    try {
      console.log('Enhancing description for:', content);
      // Get available tools
      const tools = Object.keys(this.toolkit.tools).join(', ');
      const result = await this.session.chat(
        `You are an AI assistant helping blind users navigate web content.
         Available tools: ${tools}
         
         First, use navigate_to to open this webpage: ${content}
         Then describe what you find using read_current.`
      );
      console.log('LLM response:', result);
      return result.trim();
    } catch (error) {
      console.error('Navigation error:', error);
      return `Error loading content: ${error instanceof Error ? error.message : String(error)}`;
    }
  }

  async suggestNavigation(content, intent) {
    if (!this.enabled || !this.session) {
      return 'Basic navigation available';
    }

    try {
      console.log('Suggesting navigation for:', content, 'with intent:', intent);
      // Get available tools
      const tools = Object.keys(this.toolkit.tools).join(', ');
      const result = await this.session.chat(
        `You are an AI assistant helping blind users navigate web content.
         Available tools: ${tools}
         
         To explore ${content} with intent "${intent}", I recommend:
         1. First use navigate_to to open the webpage
         2. Then use list_headings to get an overview
         3. Use navigate_headings and read_current to explore content
         4. Use next_element and previous_element to move through details
         
         Let me help you do that step by step.`
      );
      console.log('LLM response:', result);
      return result.trim();
    } catch (error) {
      console.error('Navigation error:', error);
      return 'Navigation suggestions not available';
    }
  }

  async cleanup() {
    // No cleanup needed
  }
}

module.exports = { LLMManager };
