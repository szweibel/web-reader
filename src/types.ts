import { HTMLElement } from 'node-html-parser';

export interface NavigationState {
  currentUrl: string | null;
  browser: any;
  page: any;
  currentElement: string | null;
}

export interface McpResponse {
  _meta: {
    progressToken?: string | number;
  };
}

export interface HandlerResult extends McpResponse {
  content: Array<{
    type: string;
    text: string;
  }>;
}

export interface ListToolsResponse extends McpResponse {
  tools: Array<{
    name: string;
    description?: string;
    inputSchema: {
      type: 'object';
      properties?: Record<string, unknown>;
      required?: string[];
    };
  }>;
}

export interface ToolResponse {
  title?: string;
  summary?: string;
  text?: string;
  message?: string;
  headings?: string[];
  matches?: number;
  firstMatch?: string;
}
