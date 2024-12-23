import { Browser, Page, ElementHandle } from 'puppeteer';
import type { IpcRenderer } from 'electron';

declare global {
  interface Window {
    ipcRenderer: IpcRenderer;
  }
}

export interface NavigationState {
  browser: Browser | null;
  page: Page | null;
  currentUrl: string | null;
  currentIndex: number;
  navigationType: 'all' | 'headings' | 'landmarks';
  headingLevel?: number;
  currentElement: ElementHandle<Element> | null;
}

export interface HeadingInfo {
  level: number;
  text: string;
}

export interface LandmarkInfo {
  type: string;
  text: string;
  role: string;
  label?: string;
}

export interface MatchInfo {
  index: number;
  text: string;
}

export interface ToolResponse {
  description: string;
  // Navigation info
  title?: string;
  heading?: string;
  elementCount?: number;
  elementIndex?: number;
  totalElements?: number;
  message?: string;
  
  // Heading navigation
  headingCount?: number;
  headings?: HeadingInfo[];
  navigationType?: 'all' | 'headings' | 'landmarks';
  currentHeadingLevel?: number;
  
  // Landmark navigation
  landmarks?: LandmarkInfo[];
  
  // Search results
  matchCount?: number;
  matches?: MatchInfo[];
}

export interface NavigationRequest {
  currentContent: string;
  intent: string;
}

// Re-export types used in server.ts
export type HandlerResult = ToolResponse;
export type ListToolsResponse = {
  _meta: Record<string, unknown>;
  tools: Array<{
    name: string;
    description: string;
    inputSchema?: Record<string, unknown>;
  }>;
};
