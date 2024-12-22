import { Browser, ElementHandle, Page } from 'puppeteer';

export interface NavigationState {
  currentUrl: string | null;
  browser: Browser | null;
  page: Page | null;
  currentIndex: number;
  currentElement: ElementHandle | null;
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
  // Common fields
  message?: string;
  description?: string;

  // Navigation response
  title?: string;
  heading?: string;
  elementCount?: number;
  landmarks?: Array<{
    role: string | null;
    label: string;
  }>;

  // Element navigation response
  elementIndex?: number;
  totalElements?: number;

  // Heading response
  headingCount?: number;
  headings?: Array<{
    level: number;
    text: string;
  }>;

  // Search response
  matchCount?: number;
  matches?: Array<{
    text: string;
    context: string;
    role: string;
  }>;
}

export interface ElementInfo {
  role?: string;
  ariaLabel?: string;
  ariaDescribedby?: string;
  type: string;
  inputType?: string;
  text: string;
  value?: string;
  name?: string;
  required?: boolean;
  disabled?: boolean;
  expanded?: string;
  checked?: boolean | string;
}
