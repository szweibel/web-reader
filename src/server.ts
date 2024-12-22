import { Server } from "@modelcontextprotocol/sdk/server/index.js";
import {
  CallToolRequestSchema,
  ErrorCode,
  ListToolsRequestSchema,
  McpError,
  CallToolRequest
} from '@modelcontextprotocol/sdk/types.js';
import { HandlerResult, NavigationState, ListToolsResponse } from './types.js';
import { PageHandlers } from './handlers.js';

export class WebReaderServer {
  private server: Server;
  private handlers: PageHandlers;

  constructor(state: NavigationState) {
    this.handlers = new PageHandlers(state);
    this.server = new Server(
      {
        name: 'web-reader',
        version: '0.1.0',
      },
      {
        capabilities: {
          tools: {},
        },
      }
    );

    this.setupTools();
  }

  getServer(): Server {
    return this.server;
  }

  private setupTools() {
    // List available tools
    this.server.setRequestHandler(ListToolsRequestSchema, async () => ({
      _meta: {},
      tools: [
        {
          name: 'navigate_to',
          description: 'Navigate to a URL',
          inputSchema: {
            type: 'object',
            properties: {
              url: {
                type: 'string',
                description: 'URL to navigate to',
              },
            },
            required: ['url'],
          },
        },
        {
          name: 'read_current',
          description: 'Read current element or page content',
          inputSchema: {
            type: 'object',
            properties: {},
          },
        },
        {
          name: 'next_element',
          description: 'Move to and read next focusable element',
          inputSchema: {
            type: 'object',
            properties: {},
          },
        },
        {
          name: 'previous_element',
          description: 'Move to and read previous focusable element',
          inputSchema: {
            type: 'object',
            properties: {},
          },
        },
        {
          name: 'list_headings',
          description: 'List all headings on the page',
          inputSchema: {
            type: 'object',
            properties: {},
          },
        },
        {
          name: 'find_text',
          description: 'Find and read text on the page',
          inputSchema: {
            type: 'object',
            properties: {
              text: {
                type: 'string',
                description: 'Text to search for',
              },
            },
            required: ['text'],
          },
        },
      ],
    }));

    // Handle tool calls
    this.server.setRequestHandler(CallToolRequestSchema, async (request: CallToolRequest) => {
      try {
        const baseResponse = {
          _meta: {},
          content: [] as Array<{ type: string; text: string; }>,
        };

        switch (request.params.name) {
          case 'navigate_to': {
            const url = request.params.arguments?.url;
            if (!url || typeof url !== 'string') {
              throw new McpError(ErrorCode.InvalidParams, 'URL is required');
            }
            const result = await this.handlers.handleNavigateTo(url);
            return {
              ...baseResponse,
              content: [{ type: 'text', text: JSON.stringify(result) }],
            };
          }

          case 'read_current': {
            const result = await this.handlers.handleReadCurrent();
            return {
              ...baseResponse,
              content: [{ type: 'text', text: JSON.stringify(result) }],
            };
          }

          case 'next_element': {
            const result = await this.handlers.handleNextElement();
            return {
              ...baseResponse,
              content: [{ type: 'text', text: JSON.stringify(result) }],
            };
          }

          case 'previous_element': {
            const result = await this.handlers.handlePreviousElement();
            return {
              ...baseResponse,
              content: [{ type: 'text', text: JSON.stringify(result) }],
            };
          }

          case 'list_headings': {
            const result = await this.handlers.handleListHeadings();
            return {
              ...baseResponse,
              content: [{ type: 'text', text: JSON.stringify(result) }],
            };
          }

          case 'find_text': {
            const text = request.params.arguments?.text;
            if (!text || typeof text !== 'string') {
              throw new McpError(ErrorCode.InvalidParams, 'Search text is required');
            }
            const result = await this.handlers.handleFindText(text);
            return {
              ...baseResponse,
              content: [{ type: 'text', text: JSON.stringify(result) }],
            };
          }

          default:
            throw new McpError(
              ErrorCode.MethodNotFound,
              `Unknown tool: ${request.params.name}`
            );
        }
      } catch (error) {
        if (error instanceof McpError) throw error;
        throw new McpError(
          ErrorCode.InternalError,
          error instanceof Error ? error.message : String(error)
        );
      }
    });
  }

  async cleanup(): Promise<void> {
    await this.handlers.cleanup();
  }
}
