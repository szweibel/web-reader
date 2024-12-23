import { initializeAgentExecutorWithOptions } from 'langchain/agents';
import { MCPToolkit } from 'mcp-langchain-ts-client';
import { getLlama, LlamaChatSession } from 'node-llama-cpp';

async function run(tools, userPrompt) {
  try {
    // Initialize Llama directly like in llm.js
    const llama = await getLlama();
    const model = await llama.loadModel({
      modelPath: './models/llama-2-7b-chat.Q4_K_M.gguf',
      nCtx: 2048,
      nThreads: 4,
      seed: 0
    });
    
    const context = await model.createContext();
    const session = new LlamaChatSession({
      contextSequence: context.getSequence()
    });

    // Create a wrapper that implements LangChain's LLM interface
    const llamaWrapper = {
      async call(prompt) {
        const response = await session.prompt(prompt);
        return response.trim();
      },
      async invoke(input) {
        return this.call(input);
      }
    };

    // Create agent executor with our wrapped model
    const executor = await initializeAgentExecutorWithOptions(tools, llamaWrapper, {
      agentType: "zero-shot-react-description",
      verbose: true,
      maxIterations: 3,
    });

    // Run agent
    const result = await executor.invoke({
      input: userPrompt,
    });

    return result.output;
  } catch (error) {
    console.error('Error in LangChain agent:', error);
    throw error;
  }
}

async function main() {
  try {
    // Initialize MCP toolkit with our web reader server
    const toolkit = new MCPToolkit({
      command: 'node',
      args: ['/Users/stephenzweibel/Apps/web-reader/build/index.js']
    });
    await toolkit.initialize();
    
    // Get available tools
    const tools = toolkit.getTools();
    console.log('Available tools:', tools.map(t => t.name));

    // Test prompt using web reader tools
    const prompt = `
      I need help exploring https://example.com. Please:
      1. Navigate to the page using navigate_to
      2. List all headings using list_headings
      3. Read the main content using read_current
    `;

    const response = await run(tools, prompt);
    console.log('Agent response:', response);
  } catch (error) {
    console.error('Failed to run experiment:', error);
  }
}

main().catch(console.error);
