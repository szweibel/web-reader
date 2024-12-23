import puppeteer, { ElementHandle, Page } from 'puppeteer';
import { NavigationState, ToolResponse } from './types.js';
import { speak } from './utils.js';

export class PageHandlers {
  constructor(private state: NavigationState) {}

  async handleNavigateTo(url: string): Promise<ToolResponse> {
    if (!this.state.browser) {
      this.state.browser = await puppeteer.launch();
    }

    if (!this.state.page) {
      this.state.page = await this.state.browser.newPage();
    }

    try {
      await this.state.page.goto(url);
      this.state.currentUrl = url;
      this.state.currentIndex = 0;
      this.state.navigationType = 'all';
      this.state.headingLevel = undefined;

      const message = `Navigated to ${url}`;
      await speak(message);
      return { description: message };
    } catch (error) {
      const message = `Failed to navigate to ${url}: ${error instanceof Error ? error.message : String(error)}`;
      await speak(message);
      throw error;
    }
  }

  async handleReadCurrent(): Promise<ToolResponse> {
    if (!this.state.page) {
      throw new Error('No active page');
    }

    const elements = await this.state.page.$$('*');
    if (elements.length === 0) {
      throw new Error('No elements found on page');
    }

    const currentElement = elements[this.state.currentIndex];
    const text = await this.getElementText(currentElement);
    await speak(text);
    return { description: text };
  }

  async handleNextElement(): Promise<ToolResponse> {
    if (!this.state.page) {
      throw new Error('No active page');
    }

    const elements = await this.getNavigableElements();
    if (elements.length === 0) {
      throw new Error('No elements found');
    }

    this.state.currentIndex = (this.state.currentIndex + 1) % elements.length;
    const text = await this.getElementText(elements[this.state.currentIndex]);
    await speak(text);
    return { description: text };
  }

  async handlePreviousElement(): Promise<ToolResponse> {
    if (!this.state.page) {
      throw new Error('No active page');
    }

    const elements = await this.getNavigableElements();
    if (elements.length === 0) {
      throw new Error('No elements found');
    }

    this.state.currentIndex = (this.state.currentIndex - 1 + elements.length) % elements.length;
    const text = await this.getElementText(elements[this.state.currentIndex]);
    await speak(text);
    return { description: text };
  }

  async handleListHeadings(): Promise<ToolResponse> {
    if (!this.state.page) {
      throw new Error('No active page');
    }

    const headings = await this.state.page.$$('h1, h2, h3, h4, h5, h6');
    const headingTexts = await Promise.all(
      headings.map(async (heading) => await this.getElementText(heading))
    );

    const text = headingTexts.join('\n');
    await speak(text);
    return { description: text };
  }

  async handleFindText(searchText: string): Promise<ToolResponse> {
    if (!this.state.page) {
      throw new Error('No active page');
    }

    const elements = await this.state.page.$$('*');
    const matches = [];

    for (let i = 0; i < elements.length; i++) {
      const text = await this.getElementText(elements[i]);
      if (text.toLowerCase().includes(searchText.toLowerCase())) {
        matches.push({ index: i, text });
      }
    }

    if (matches.length === 0) {
      const message = `No matches found for "${searchText}"`;
      await speak(message);
      return { description: message };
    }

    const result = matches.map(m => m.text).join('\n');
    await speak(result);
    return { description: result };
  }

  async handleNavigateLandmarks(): Promise<ToolResponse> {
    if (!this.state.page) {
      throw new Error('No active page');
    }

    const landmarks = await this.state.page.$$('main, nav, header, footer, aside, article, section');
    const landmarkTexts = await Promise.all(
      landmarks.map(async (landmark) => await this.getElementText(landmark))
    );

    const text = landmarkTexts.join('\n');
    await speak(text);
    return { description: text };
  }

  async handleNavigateHeadings(level?: number): Promise<ToolResponse> {
    if (!this.state.page) {
      throw new Error('No active page');
    }

    const selector = level ? `h${level}` : 'h1, h2, h3, h4, h5, h6';
    const headings = await this.state.page.$$(selector);
    
    if (headings.length === 0) {
      const message = level 
        ? `No h${level} headings found` 
        : 'No headings found';
      await speak(message);
      return { description: message };
    }

    this.state.navigationType = 'headings';
    this.state.headingLevel = level;
    this.state.currentIndex = 0;

    const text = await this.getElementText(headings[0]);
    await speak(text);
    return { description: text };
  }

  async handleChangeHeadingLevel(direction: 'up' | 'down'): Promise<ToolResponse> {
    if (!this.state.page || this.state.navigationType !== 'headings') {
      throw new Error('Not in heading navigation mode');
    }

    const currentLevel = this.state.headingLevel || 1;
    const newLevel = direction === 'up' 
      ? Math.max(1, currentLevel - 1)
      : Math.min(6, currentLevel + 1);

    return this.handleNavigateHeadings(newLevel);
  }

  async handleEnhanceDescription(content: string): Promise<ToolResponse> {
    try {
      // Request enhancement from Electron's LLM through IPC
      const enhancedDescription = await window.ipcRenderer.invoke('enhance-description', content);
      await speak(enhancedDescription);
      return {
        description: enhancedDescription
      };
    } catch (error) {
      const message = error instanceof Error ? error.message : String(error);
      await speak(`Error enhancing description: ${message}`);
      throw error;
    }
  }

  async handleSuggestNavigation(currentContent: string, intent: string): Promise<ToolResponse> {
    try {
      // Request navigation suggestions from Electron's LLM through IPC
      const suggestions = await window.ipcRenderer.invoke('suggest-navigation', { currentContent, intent });
      await speak(suggestions);
      return {
        description: suggestions
      };
    } catch (error) {
      const message = error instanceof Error ? error.message : String(error);
      await speak(`Error suggesting navigation: ${message}`);
      throw error;
    }
  }

  private async getNavigableElements(): Promise<ElementHandle<Element>[]> {
    if (!this.state.page) {
      throw new Error('No active page');
    }

    switch (this.state.navigationType) {
      case 'headings':
        return this.state.page.$$(
          this.state.headingLevel ? `h${this.state.headingLevel}` : 'h1, h2, h3, h4, h5, h6'
        );
      case 'landmarks':
        return this.state.page.$$('main, nav, header, footer, aside, article, section');
      default:
        return this.state.page.$$('*');
    }
  }

  private async getElementText(element: ElementHandle<Element>): Promise<string> {
    if (!this.state.page) {
      throw new Error('No active page');
    }
    
    const text = await this.state.page.evaluate((el: Element) => {
      if (el.tagName.toLowerCase() === 'input') {
        const input = el as HTMLInputElement;
        return `${input.type} input${input.value ? ': ' + input.value : ''}`;
      }
      return el.textContent || '';
    }, element);
    return text.trim();
  }

  async cleanup(): Promise<void> {
    if (this.state.browser) {
      await this.state.browser.close();
      this.state.browser = null;
      this.state.page = null;
      this.state.currentUrl = null;
      this.state.currentIndex = 0;
      this.state.navigationType = 'all';
      this.state.headingLevel = undefined;
    }
  }
}
