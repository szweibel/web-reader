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
    if (process.env.MCP_DEBUG) {
      console.error('[DEBUG] Initializing WebReaderServer');
    }
    
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
    
    if (process.env.MCP_DEBUG) {
      console.error('[DEBUG] WebReaderServer initialized');
    }
  }

  getServer(): Server {
    return this.server;
  }

  private setupTools() {
    if (process.env.MCP_DEBUG) {
      console.error('[DEBUG] Setting up tools');
    }

    // List available tools
    this.server.setRequestHandler(ListToolsRequestSchema, async () => {
      if (process.env.MCP_DEBUG) {
        console.error('[DEBUG] Handling tools/list request');
      }
      return {
        _meta: {},
        tools: [
          {
            name: 'navigate_to',
            description: 'Navigate to a webpage (e.g., "go to [website]", "open [url]")',
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
            description: 'Read current element (e.g., "read this", "what\'s this?")',
            inputSchema: {
              type: 'object',
              properties: {},
            },
          },
          {
            name: 'next_element',
            description: 'Move to next element (e.g., "next", "move forward")',
            inputSchema: {
              type: 'object',
              properties: {},
            },
          },
          {
            name: 'previous_element',
            description: 'Move to previous element (e.g., "back", "previous")',
            inputSchema: {
              type: 'object',
              properties: {},
            },
          },
          {
            name: 'list_headings',
            description: 'List all headings (e.g., "show headings", "what headings are there?")',
            inputSchema: {
              type: 'object',
              properties: {},
            },
          },
          {
            name: 'find_text',
            description: 'Search for text (e.g., "find [text]", "search for [text]")',
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
          {
            name: 'navigate_landmarks',
            description: 'Navigate by landmarks (e.g., "go to landmarks", "show landmarks")',
            inputSchema: {
              type: 'object',
              properties: {},
            },
          },
          {
            name: 'navigate_headings',
            description: 'Navigate by headings (e.g., "go to headings", "level [1-6]")',
            inputSchema: {
              type: 'object',
              properties: {
                level: {
                  type: 'number',
                  description: 'Optional heading level (1-6) to filter by',
                  minimum: 1,
                  maximum: 6
                },
              },
            },
          },
          {
            name: 'change_heading_level',
            description: 'Change heading level (e.g., "level up", "higher level", "level down")',
            inputSchema: {
              type: 'object',
              properties: {
                direction: {
                  type: 'string',
                  description: 'Direction to move (up/down)',
                  enum: ['up', 'down']
                },
              },
              required: ['direction'],
            },
          },
          // Add LLM tools
          {
            name: 'enhance_description',
            description: 'Generate an enhanced, accessible description of webpage content using a local LLM',
            inputSchema: {
              type: 'object',
              properties: {
                content: {
                  type: 'string',
                  description: 'The webpage content to analyze',
                },
              },
              required: ['content'],
            },
          },
          {
            name: 'suggest_navigation',
            description: 'Suggest navigation actions based on user intent using a local LLM',
            inputSchema: {
              type: 'object',
              properties: {
                intent: {
                  type: 'string',
                  description: 'What the user wants to do or find',
                },
                currentContent: {
                  type: 'string',
                  description: 'Current webpage content',
                },
              },
              required: ['intent', 'currentContent'],
            },
          }
        ]
      };
    });

    // Handle tool calls
    this.server.setRequestHandler(CallToolRequestSchema, async (request: CallToolRequest) => {
      if (process.env.MCP_DEBUG) {
        console.error(`[DEBUG] Handling tool call: ${request.params.name}`);
      }
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

          case 'navigate_landmarks': {
            const result = await this.handlers.handleNavigateLandmarks();
            return {
              ...baseResponse,
              content: [{ type: 'text', text: JSON.stringify(result) }],
            };
          }

          case 'navigate_headings': {
            const level = request.params.arguments?.level;
            if (level !== undefined) {
              const numLevel = Number(level);
              if (!Number.isInteger(numLevel) || numLevel < 1 || numLevel > 6) {
                throw new McpError(ErrorCode.InvalidParams, 'Heading level must be between 1 and 6');
              }
              const result = await this.handlers.handleNavigateHeadings(numLevel);
              return {
                ...baseResponse,
                content: [{ type: 'text', text: JSON.stringify(result) }],
              };
            }
            const result = await this.handlers.handleNavigateHeadings();
            return {
              ...baseResponse,
              content: [{ type: 'text', text: JSON.stringify(result) }],
            };
          }

          case 'change_heading_level': {
            const direction = request.params.arguments?.direction;
            if (direction !== 'up' && direction !== 'down') {
              throw new McpError(ErrorCode.InvalidParams, 'Direction must be "up" or "down"');
            }
            const result = await this.handlers.handleChangeHeadingLevel(direction);
            return {
              ...baseResponse,
              content: [{ type: 'text', text: JSON.stringify(result) }],
            };
          }

          case 'enhance_description': {
            const content = request.params.arguments?.content;
            if (!content || typeof content !== 'string') {
              throw new McpError(ErrorCode.InvalidParams, 'Content is required');
            }
            const result = await this.handlers.handleEnhanceDescription(content);
            return {
              ...baseResponse,
              content: [{ type: 'text', text: JSON.stringify(result) }],
            };
          }

          case 'suggest_navigation': {
            const { intent, currentContent } = request.params.arguments || {};
            if (!intent || typeof intent !== 'string' || !currentContent || typeof currentContent !== 'string') {
              throw new McpError(ErrorCode.InvalidParams, 'Intent and currentContent are required');
            }
            const result = await this.handlers.handleSuggestNavigation(currentContent, intent);
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
