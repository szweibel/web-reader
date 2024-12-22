import puppeteer, { ElementHandle, Page } from 'puppeteer';
import { NavigationState, ToolResponse } from './types.js';
import { speak } from './utils.js';

export class PageHandlers {
  constructor(private state: NavigationState) {}

  private async getAccessibleDescription(element: ElementHandle<Element>): Promise<string> {
    const page = this.state.page as Page;
    return page.evaluate(function(el: Element): string {
      // Get element properties
      const role = el.getAttribute('role');
      const ariaLabel = el.getAttribute('aria-label');
      const ariaDescribedby = el.getAttribute('aria-describedby');
      const type = el.tagName.toLowerCase();
      const inputType = el instanceof HTMLInputElement ? el.type : '';
      const text = el.textContent?.trim() || '';
      const value = el instanceof HTMLInputElement ? el.value : '';
      const name = el.getAttribute('name');
      const required = el.hasAttribute('required');
      const disabled = el.hasAttribute('disabled') || el.hasAttribute('aria-disabled');
      const expanded = el.getAttribute('aria-expanded');
      const checked = el.hasAttribute('checked') || el.getAttribute('aria-checked');
      
      // Build description
      let desc = '';
      
      // Role and type
      if (ariaLabel) {
        desc += ariaLabel;
      } else {
        if (role) desc += `${role} `;
        else if (inputType) desc += `${inputType} input`;
        else if (type === 'a') desc += 'link';
        else if (type === 'button') desc += 'button';
        else desc += type;
      }

      // State information
      const states = [];
      if (required) states.push('required');
      if (disabled) states.push('disabled');
      if (expanded === 'true') states.push('expanded');
      else if (expanded === 'false') states.push('collapsed');
      if (checked === 'true' || checked === true || checked === '') states.push('checked');
      else if (checked === 'false') states.push('unchecked');
      
      if (states.length) {
        desc += ` (${states.join(', ')})`;
      }

      // Content
      if (value) desc += `: ${value}`;
      else if (text && !ariaLabel) desc += `: ${text}`;
      
      // Additional description
      if (ariaDescribedby) {
        const describedBy = document.getElementById(ariaDescribedby);
        if (describedBy) desc += `. ${describedBy.textContent}`;
      }

      return desc.trim();
    }, element);
  }

  private async getFocusableElements(): Promise<ElementHandle<Element>[]> {
    const page = this.state.page as Page;
    return page.$$(`
      a[href]:not([aria-hidden="true"]),
      button:not([disabled]):not([aria-hidden="true"]),
      input:not([disabled]):not([aria-hidden="true"]),
      select:not([disabled]):not([aria-hidden="true"]),
      textarea:not([disabled]):not([aria-hidden="true"]),
      [tabindex]:not([tabindex="-1"]):not([aria-hidden="true"]),
      [role="button"]:not([aria-hidden="true"]),
      [role="link"]:not([aria-hidden="true"]),
      [role="menuitem"]:not([aria-hidden="true"]),
      [role="option"]:not([aria-hidden="true"])
    `);
  }

  async handleNavigateTo(url: string): Promise<ToolResponse> {
    // Close existing browser if any
    await this.cleanup();
    
    try {
      // Launch new browser and navigate
      this.state.browser = await puppeteer.launch({ headless: true });
      this.state.page = await this.state.browser.newPage();
      
      // Enable better error handling
      this.state.page.on('error', console.error);
      this.state.page.on('pageerror', console.error);
      
      await this.state.page.goto(url, { waitUntil: 'networkidle0' });
      this.state.currentUrl = url;

      // Get page information
      const pageInfo = await this.state.page.evaluate(() => {
        const title = document.title;
        const h1 = document.querySelector('h1')?.textContent?.trim() || '';
        const landmarks = Array.from(document.querySelectorAll('[role="main"], [role="navigation"], [role="search"]'))
          .map(el => ({
            role: el.getAttribute('role'),
            label: el.getAttribute('aria-label') || ''
          }));
        return { title, h1, landmarks };
      });

      // Count interactive elements
      const elements = await this.getFocusableElements();
      const elementCount = elements.length;

      const description = `Loaded ${pageInfo.title}. ${pageInfo.h1 ? `Main heading: ${pageInfo.h1}.` : ''} Found ${elementCount} interactive elements.`;
      await speak(description);

      return {
        title: pageInfo.title,
        heading: pageInfo.h1,
        elementCount,
        landmarks: pageInfo.landmarks,
        description
      };
    } catch (error) {
      const message = error instanceof Error ? error.message : String(error);
      await speak(`Failed to load page: ${message}`);
      throw error;
    }
  }

  async handleReadCurrent(): Promise<ToolResponse> {
    if (!this.state.page) {
      throw new Error('No page is currently open');
    }

    try {
      const elements = await this.getFocusableElements();
      if (elements.length === 0) {
        const message = 'No interactive elements found';
        await speak(message);
        return { message };
      }

      const currentElement = elements[this.state.currentIndex || 0];
      const description = await this.getAccessibleDescription(currentElement);
      await speak(description);

      return {
        elementIndex: this.state.currentIndex,
        totalElements: elements.length,
        description
      };
    } catch (error) {
      const message = error instanceof Error ? error.message : String(error);
      await speak(`Error reading element: ${message}`);
      throw error;
    }
  }

  async handleNextElement(): Promise<ToolResponse> {
    if (!this.state.page) {
      throw new Error('No page is currently open');
    }

    try {
      const elements = await this.getFocusableElements();
      if (elements.length === 0) {
        const message = 'No interactive elements found';
        await speak(message);
        return { message };
      }

      this.state.currentIndex = (this.state.currentIndex || 0) + 1;
      if (this.state.currentIndex >= elements.length) {
        this.state.currentIndex = elements.length - 1;
        const message = 'Reached end of page';
        await speak(message);
        return { message };
      }

      const currentElement = elements[this.state.currentIndex];
      const description = await this.getAccessibleDescription(currentElement);
      await speak(description);

      // Highlight current element
      await this.state.page.evaluate((el) => {
        const prev = document.querySelector('.screen-reader-highlight');
        if (prev) prev.classList.remove('screen-reader-highlight');
        el.classList.add('screen-reader-highlight');
        el.scrollIntoView({ behavior: 'smooth', block: 'center' });
      }, currentElement);

      return {
        elementIndex: this.state.currentIndex,
        totalElements: elements.length,
        description
      };
    } catch (error) {
      const message = error instanceof Error ? error.message : String(error);
      await speak(`Error moving to next element: ${message}`);
      throw error;
    }
  }

  async handlePreviousElement(): Promise<ToolResponse> {
    if (!this.state.page) {
      throw new Error('No page is currently open');
    }

    try {
      const elements = await this.getFocusableElements();
      if (elements.length === 0) {
        const message = 'No interactive elements found';
        await speak(message);
        return { message };
      }

      this.state.currentIndex = Math.max((this.state.currentIndex || 0) - 1, 0);
      if (this.state.currentIndex === 0) {
        const message = 'At start of page';
        await speak(message);
        return { message };
      }

      const currentElement = elements[this.state.currentIndex];
      const description = await this.getAccessibleDescription(currentElement);
      await speak(description);

      // Highlight current element
      await this.state.page.evaluate((el) => {
        const prev = document.querySelector('.screen-reader-highlight');
        if (prev) prev.classList.remove('screen-reader-highlight');
        el.classList.add('screen-reader-highlight');
        el.scrollIntoView({ behavior: 'smooth', block: 'center' });
      }, currentElement);

      return {
        elementIndex: this.state.currentIndex,
        totalElements: elements.length,
        description
      };
    } catch (error) {
      const message = error instanceof Error ? error.message : String(error);
      await speak(`Error moving to previous element: ${message}`);
      throw error;
    }
  }

  async handleListHeadings(): Promise<ToolResponse> {
    if (!this.state.page) {
      throw new Error('No page is currently open');
    }

    try {
      const headings = await this.state.page.evaluate(() => {
        return Array.from(document.querySelectorAll('h1, h2, h3, h4, h5, h6'))
          .filter(h => h.getAttribute('aria-hidden') !== 'true')
          .map(h => ({
            level: parseInt(h.tagName[1]),
            text: h.textContent?.trim() || '',
            ariaLabel: h.getAttribute('aria-label')
          }));
      });

      if (headings.length === 0) {
        const message = 'No headings found on page';
        await speak(message);
        return { message };
      }

      const headingDescriptions = headings.map((h, i) => 
        `Level ${h.level} heading ${i + 1} of ${headings.length}: ${h.ariaLabel || h.text}`
      );

      await speak(`Found ${headings.length} headings. ${headingDescriptions.join('. ')}`);

      return {
        headingCount: headings.length,
        headings: headings.map(h => ({
          level: h.level,
          text: h.ariaLabel || h.text
        }))
      };
    } catch (error) {
      const message = error instanceof Error ? error.message : String(error);
      await speak(`Error listing headings: ${message}`);
      throw error;
    }
  }

  async handleFindText(searchText: string): Promise<ToolResponse> {
    if (!this.state.page) {
      throw new Error('No page is currently open');
    }

    try {
      // Find elements containing the text
      const matches = await this.state.page.evaluate((text) => {
        const walker = document.createTreeWalker(
          document.body,
          NodeFilter.SHOW_TEXT,
          {
            acceptNode: (node) => {
              if (node.parentElement?.getAttribute('aria-hidden') === 'true') {
                return NodeFilter.FILTER_REJECT;
              }
              return node.textContent?.toLowerCase().includes(text.toLowerCase())
                ? NodeFilter.FILTER_ACCEPT
                : NodeFilter.FILTER_REJECT;
            }
          }
        );

        const matches = [];
        let node;
        while (node = walker.nextNode()) {
          const element = node.parentElement;
          if (element) {
            matches.push({
              text: node.textContent?.trim() || '',
              context: element.textContent?.trim() || '',
              ariaLabel: element.getAttribute('aria-label'),
              role: element.getAttribute('role') || element.tagName.toLowerCase()
            });
          }
        }
        return matches;
      }, searchText);

      if (matches.length === 0) {
        const message = `Text "${searchText}" not found on page`;
        await speak(message);
        return { message };
      }

      const description = `Found ${matches.length} matches for "${searchText}". First match: ${matches[0].text}`;
      await speak(description);

      return {
        matchCount: matches.length,
        matches: matches.map(m => ({
          text: m.text,
          context: m.context,
          role: m.role
        }))
      };
    } catch (error) {
      const message = error instanceof Error ? error.message : String(error);
      await speak(`Error searching text: ${message}`);
      throw error;
    }
  }

  async cleanup(): Promise<void> {
    if (this.state.browser) {
      await this.state.browser.close();
      this.state.browser = null;
      this.state.page = null;
      this.state.currentUrl = null;
      this.state.currentIndex = 0;
    }
  }
}
