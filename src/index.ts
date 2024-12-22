#!/usr/bin/env node
import { StdioServerTransport } from '@modelcontextprotocol/sdk/server/stdio.js';
import { NavigationState } from './types.js';
import { WebReaderServer } from './server.js';
import { checkDependencies } from './utils.js';

async function main() {
  try {
    // Check system dependencies
    await checkDependencies();

    // Initialize state
    const state: NavigationState = {
      currentUrl: null,
      browser: null,
      page: null,
      currentElement: null
    };

    // Create and start server
    const webReader = new WebReaderServer(state);
    const transport = new StdioServerTransport();
    
    // Handle cleanup on exit
    process.on('SIGINT', async () => {
      await webReader.cleanup();
      process.exit(0);
    });

    // Connect server
    await webReader.getServer().connect(transport);
    console.error('Web Reader MCP server running on stdio (not a network port)');
    console.error('Ready to accept commands...');

  } catch (error) {
    console.error('Failed to start server:', error);
    process.exit(1);
  }
}

main().catch(console.error);
