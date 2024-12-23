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

  private async getFocusableElements(type: 'all' | 'landmarks' | 'headings' = 'all'): Promise<ElementHandle<Element>[]> {
    const page = this.state.page as Page;
    
    let selector = '';
    switch (type) {
      case 'landmarks':
        selector = `
          [role="main"],
          [role="navigation"],
          [role="search"],
          [role="complementary"],
          [role="banner"],
          [role="contentinfo"],
          main,
          nav,
          header,
          footer,
          aside
        `;
        break;
      case 'headings':
        selector = 'h1, h2, h3, h4, h5, h6';
        break;
      default:
        selector = `
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
        `;
    }
    
    return page.$$(selector);
  }

  private async setupLiveRegionObserver(): Promise<void> {
    const page = this.state.page as Page;
    await page.evaluate(() => {
      const observer = new MutationObserver((mutations) => {
        mutations.forEach((mutation) => {
          if (mutation.target instanceof Element) {
            const live = mutation.target.getAttribute('aria-live');
            if (live === 'polite' || live === 'assertive') {
              const text = mutation.target.textContent?.trim();
              if (text) {
                // Send message to Node process
                console.log(JSON.stringify({
                  type: 'live-region',
                  priority: live === 'assertive' ? 'high' : 'normal',
                  text
                }));
              }
            }
          }
        });
      });

      observer.observe(document.body, {
        subtree: true,
        childList: true,
        characterData: true
      });

      // Handle dynamic content
      document.addEventListener('DOMContentLoaded', () => {
        const skipLinks = Array.from(document.querySelectorAll('a[href^="#"]'))
          .filter(link => {
            const text = link.textContent?.toLowerCase() || '';
            return text.includes('skip') || text.includes('jump to') || text.includes('main content');
          });
        
        if (skipLinks.length > 0) {
          console.log(JSON.stringify({
            type: 'skip-links',
            count: skipLinks.length
          }));
        }
      });
    });

    // Handle console messages for live regions
    page.on('console', async (msg) => {
      try {
        const text = msg.text();
        if (text.startsWith('{') && text.endsWith('}')) {
          const data = JSON.parse(text);
          if (data.type === 'live-region') {
            await speak(data.text, { priority: data.priority });
          } else if (data.type === 'skip-links') {
            await speak(`Found ${data.count} skip links on the page`, { priority: 'high' });
          }
        }
      } catch (error) {
        // Ignore parsing errors for non-JSON console messages
      }
    });
  }

  async handleNavigateTo(url: string): Promise<ToolResponse> {
    try {
      // Use existing page from state
      if (!this.state.page) {
        throw new Error('No page available');
      }

      // Navigate to URL
      await this.state.page.goto(url, { 
        waitUntil: 'networkidle0',
        timeout: 30000
      });
      this.state.currentUrl = url;

      // Get page information
      const pageInfo = await this.state.page.evaluate(() => {
        const title = document.title;
        const h1 = document.querySelector('h1')?.textContent?.trim() || '';
        const landmarks = Array.from(document.querySelectorAll('[role="main"], [role="navigation"], [role="search"], main, nav, header, footer, aside'))
          .map(el => ({
            role: el.getAttribute('role') || el.tagName.toLowerCase(),
            label: el.getAttribute('aria-label') || '',
            tag: el.tagName.toLowerCase(),
            text: el.textContent?.trim() || ''
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

  async handleNavigateLandmarks(): Promise<ToolResponse> {
    if (!this.state.page) {
      throw new Error('No page is currently open');
    }

    try {
      this.state.navigationType = 'landmarks';
      const landmarks = await this.getFocusableElements('landmarks');
      
      if (landmarks.length === 0) {
        const message = 'No landmarks found on page';
        await speak(message);
        return { message };
      }

      // Reset index when switching to landmark navigation
      this.state.currentIndex = 0;
      const currentLandmark = landmarks[0];
      
      const landmarkInfo = await this.state.page.evaluate((el) => {
        return {
          role: el.getAttribute('role') || el.tagName.toLowerCase(),
          label: el.getAttribute('aria-label') || '',
          tag: el.tagName.toLowerCase(),
          text: el.textContent?.trim() || ''
        };
      }, currentLandmark);

      const description = `Switched to landmark navigation. ${landmarks.length} landmarks found. Current: ${landmarkInfo.label || landmarkInfo.role} ${landmarkInfo.text ? `containing ${landmarkInfo.text}` : ''}`;
      await speak(description);

      // Highlight current landmark
      await this.state.page.evaluate((el) => {
        const prev = document.querySelector('.screen-reader-highlight');
        if (prev) prev.classList.remove('screen-reader-highlight');
        el.classList.add('screen-reader-highlight');
        el.scrollIntoView({ behavior: 'smooth', block: 'center' });
      }, currentLandmark);

      return {
        navigationType: 'landmarks',
        elementIndex: 0,
        totalElements: landmarks.length,
        description,
        landmarks: [landmarkInfo]
      };
    } catch (error) {
      const message = error instanceof Error ? error.message : String(error);
      await speak(`Error navigating landmarks: ${message}`);
      throw error;
    }
  }

  async handleNavigateHeadings(level?: number): Promise<ToolResponse> {
    if (!this.state.page) {
      throw new Error('No page is currently open');
    }

    try {
      this.state.navigationType = 'headings';
      const headings = await this.getFocusableElements('headings');
      
      if (headings.length === 0) {
        const message = 'No headings found on page';
        await speak(message);
        return { message };
      }

      // Filter headings by level if specified
      const filteredHeadings = await Promise.all(
        headings.map(async h => {
          const info = await this.state.page!.evaluate((el) => ({
            level: parseInt(el.tagName[1]),
            text: el.textContent?.trim() || '',
            ariaLabel: el.getAttribute('aria-label')
          }), h);
          return { element: h, ...info };
        })
      );

      const relevantHeadings = level 
        ? filteredHeadings.filter(h => h.level === level)
        : filteredHeadings;

      if (relevantHeadings.length === 0) {
        const message = `No level ${level} headings found`;
        await speak(message);
        return { message };
      }

      // Reset index when switching heading level
      this.state.currentIndex = 0;
      this.state.headingLevel = level || relevantHeadings[0].level;
      
      const currentHeading = relevantHeadings[0];
      const description = level
        ? `Switched to level ${level} headings. ${relevantHeadings.length} headings found. Current: ${currentHeading.ariaLabel || currentHeading.text}`
        : `Switched to heading navigation. ${headings.length} total headings. Current level ${currentHeading.level}: ${currentHeading.ariaLabel || currentHeading.text}`;
      
      await speak(description);

      // Highlight current heading
      await this.state.page.evaluate((el) => {
        const prev = document.querySelector('.screen-reader-highlight');
        if (prev) prev.classList.remove('screen-reader-highlight');
        el.classList.add('screen-reader-highlight');
        el.scrollIntoView({ behavior: 'smooth', block: 'center' });
      }, currentHeading.element);

      return {
        navigationType: 'headings',
        elementIndex: 0,
        totalElements: relevantHeadings.length,
        description,
        headings: relevantHeadings.map(h => ({
          level: h.level,
          text: h.ariaLabel || h.text,
          isCurrentLevel: h.level === this.state.headingLevel
        })),
        currentHeadingLevel: this.state.headingLevel
      };
    } catch (error) {
      const message = error instanceof Error ? error.message : String(error);
      await speak(`Error navigating headings: ${message}`);
      throw error;
    }
  }

  async handleChangeHeadingLevel(direction: 'up' | 'down'): Promise<ToolResponse> {
    if (!this.state.page || this.state.navigationType !== 'headings') {
      throw new Error('Not in heading navigation mode');
    }

    try {
      const headings = await this.getFocusableElements('headings');
      const levels = await Promise.all(
        headings.map(h => this.state.page!.evaluate(el => parseInt(el.tagName[1]), h))
      );
      
      const uniqueLevels = Array.from(new Set(levels)).sort();
      const currentLevel = this.state.headingLevel || uniqueLevels[0];
      const currentIndex = uniqueLevels.indexOf(currentLevel);
      
      let newLevel: number;
      if (direction === 'up') {
        newLevel = currentIndex > 0 ? uniqueLevels[currentIndex - 1] : currentLevel;
      } else {
        newLevel = currentIndex < uniqueLevels.length - 1 ? uniqueLevels[currentIndex + 1] : currentLevel;
      }

      if (newLevel === currentLevel) {
        const message = direction === 'up' ? 'Already at highest heading level' : 'Already at lowest heading level';
        await speak(message);
        return { message };
      }

      return this.handleNavigateHeadings(newLevel);
    } catch (error) {
      const message = error instanceof Error ? error.message : String(error);
      await speak(`Error changing heading level: ${message}`);
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
      this.state.navigationType = 'all';
      this.state.headingLevel = undefined;
    }
  }
}
