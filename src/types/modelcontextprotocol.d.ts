declare module '@modelcontextprotocol/sdk' {
  export class Server {
    constructor(
      info: {
        name: string;
        version: string;
      },
      config: {
        capabilities: {
          tools: Record<string, unknown>;
        };
      }
    );

    setRequestHandler<T>(schema: unknown, handler: (request: T) => Promise<any>): void;
    connect(transport: StdioServerTransport): Promise<void>;
  }

  export class StdioServerTransport {
    constructor();
  }

  export const CallToolRequestSchema: unique symbol;
  export const ListToolsRequestSchema: unique symbol;

  export enum ErrorCode {
    InvalidParams = 'InvalidParams',
    MethodNotFound = 'MethodNotFound',
    InternalError = 'InternalError'
  }

  export class McpError extends Error {
    constructor(code: ErrorCode, message: string);
  }

  export interface CallToolRequest {
    params: {
      name: string;
      arguments?: Record<string, unknown>;
    };
  }
}
