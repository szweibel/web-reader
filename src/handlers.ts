import puppeteer from 'puppeteer';
import { parse, HTMLElement } from 'node-html-parser';
import { NavigationState, ToolResponse } from './types.js';
import { speak, getElementDescription } from './utils.js';

export class PageHandlers {
  constructor(private state: NavigationState) {}

  async handleNavigateTo(url: string): Promise<ToolResponse> {
    // Close existing browser if any
    if (this.state.browser) {
      await this.state.browser.close();
    }

    // Launch new browser and navigate
    this.state.browser = await puppeteer.launch();
    this.state.page = await this.state.browser.newPage();
    await this.state.page.goto(url);
    this.state.currentUrl = url;
    this.state.currentElement = null;

    // Get page title and initial content
    const title = await this.state.page.title();
    const content = await this.state.page.content();
    const root = parse(content);
    const mainContent = root.querySelector('main') || root.querySelector('body');
    const summary = mainContent?.textContent?.slice(0, 200) || '';

    // Read the title and summary
    await speak(`Navigated to ${title}. ${summary}`);

    return {
      title,
      summary: summary + '...'
    };
  }

  async handleReadCurrent(): Promise<ToolResponse> {
    if (!this.state.page) {
      throw new Error('No page is currently open');
    }

    const content = await this.state.page.content();
    const root = parse(content);
    
    let elementToRead;
    if (this.state.currentElement) {
      elementToRead = root.querySelector(this.state.currentElement);
    } else {
      elementToRead = root.querySelector('main') || root.querySelector('body');
    }

    const text = getElementDescription(elementToRead);
    await speak(text);

    return { text };
  }

  async handleNextElement(): Promise<ToolResponse> {
    if (!this.state.page) {
      throw new Error('No page is currently open');
    }

    const content = await this.state.page.content();
    const root = parse(content);
    
    const focusableElements = root.querySelectorAll(
      'a, button, input, select, textarea, [tabindex]:not([tabindex="-1"])'
    );

    let currentIndex = -1;
    if (this.state.currentElement) {
      currentIndex = focusableElements.findIndex(
        (el: HTMLElement) => el.toString() === this.state.currentElement
      );
    }

    const nextElement = focusableElements[currentIndex + 1];
    if (!nextElement) {
      const message = 'No more focusable elements';
      await speak(message);
      return { message };
    }

    this.state.currentElement = nextElement.toString();
    const text = getElementDescription(nextElement);
    await speak(text);

    return { text };
  }

  async handlePreviousElement(): Promise<ToolResponse> {
    if (!this.state.page) {
      throw new Error('No page is currently open');
    }

    const content = await this.state.page.content();
    const root = parse(content);
    
    const focusableElements = root.querySelectorAll(
      'a, button, input, select, textarea, [tabindex]:not([tabindex="-1"])'
    );

    let currentIndex = focusableElements.length;
    if (this.state.currentElement) {
      currentIndex = focusableElements.findIndex(
        (el: HTMLElement) => el.toString() === this.state.currentElement
      );
    }

    const prevElement = focusableElements[currentIndex - 1];
    if (!prevElement) {
      const message = 'No previous focusable elements';
      await speak(message);
      return { message };
    }

    this.state.currentElement = prevElement.toString();
    const text = getElementDescription(prevElement);
    await speak(text);

    return { text };
  }

  async handleListHeadings(): Promise<ToolResponse> {
    if (!this.state.page) {
      throw new Error('No page is currently open');
    }

    const content = await this.state.page.content();
    const root = parse(content);
    
    const headings = root.querySelectorAll('h1, h2, h3, h4, h5, h6');
    const headingTexts = headings.map((h: HTMLElement, i: number) => {
      const level = h.tagName.toLowerCase();
      const text = h.textContent.trim();
      return `${i + 1}. ${level}: ${text}`;
    });

    const text = headingTexts.join('\n');
    await speak('Page headings:\n' + text);

    return { headings: headingTexts };
  }

  async handleFindText(searchText: string): Promise<ToolResponse> {
    if (!this.state.page) {
      throw new Error('No page is currently open');
    }

    const content = await this.state.page.content();
    const root = parse(content);
    
    // Find elements containing the text
    const elements = root.querySelectorAll('*');
    const matches = elements.filter((el: HTMLElement) => 
      el.textContent.toLowerCase().includes(searchText.toLowerCase())
    );

    if (matches.length === 0) {
      const message = `Text "${searchText}" not found on page`;
      await speak(message);
      return { message };
    }

    // Focus the first match
    this.state.currentElement = matches[0].toString();
    const text = getElementDescription(matches[0]);
    await speak(`Found "${searchText}". ${text}`);

    return {
      matches: matches.length,
      firstMatch: text
    };
  }

  async cleanup(): Promise<void> {
    if (this.state.browser) {
      await this.state.browser.close();
    }
  }
}
