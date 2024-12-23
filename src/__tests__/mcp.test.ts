import { jest } from '@jest/globals';
import { PageHandlers } from '../handlers.js';
import { Browser, ElementHandle, Page } from 'puppeteer';
import { HeadingInfo } from '../types.js';

describe('Web Reader Handlers', () => {
  let mockPage: jest.Mocked<Page>;
  let handlers: PageHandlers;

  beforeEach(() => {
    // Mock page methods
    mockPage = {
      $: jest.fn(),
      $$: jest.fn(),
      evaluate: jest.fn(),
      goto: jest.fn(),
      title: jest.fn(),
      on: jest.fn(),
      close: jest.fn(),
    } as unknown as jest.Mocked<Page>;

    handlers = new PageHandlers({
      currentUrl: null,
      browser: null,
      page: mockPage,
      currentIndex: 0,
      currentElement: null,
      navigationType: 'all'
    });
  });

  describe('Navigation', () => {
    it('should handle missing page', async () => {
      handlers = new PageHandlers({
        currentUrl: null,
        browser: null,
        page: null,
        currentIndex: 0,
        currentElement: null,
        navigationType: 'all'
      });

      await expect(handlers.handleReadCurrent()).rejects.toThrow('No page is currently open');
    });

    it('should navigate to URL', async () => {
      mockPage.goto.mockResolvedValue(null);
      mockPage.title.mockResolvedValue('Test Page');
      mockPage.evaluate.mockResolvedValue({
        title: 'Test Page',
        h1: 'Main Heading',
        landmarks: []
      });
      mockPage.$$.mockResolvedValue([{} as ElementHandle<Element>]);

      const result = await handlers.handleNavigateTo('https://example.com');

      expect(result.title).toBe('Test Page');
      expect(result.heading).toBe('Main Heading');
      expect(result.elementCount).toBe(1);
    });

    it('should handle navigation errors', async () => {
      mockPage.goto.mockRejectedValue(new Error('Failed to load'));

      await expect(handlers.handleNavigateTo('https://invalid.example')).rejects.toThrow('Failed to load');
    });
  });

  describe('Element Navigation', () => {
    beforeEach(() => {
      // Mock focusable elements
      mockPage.$$.mockResolvedValue([
        {} as ElementHandle<Element>,
        {} as ElementHandle<Element>,
        {} as ElementHandle<Element>
      ]);
      mockPage.evaluate.mockResolvedValue('Element Description');
    });

    it('should read current element', async () => {
      const result = await handlers.handleReadCurrent();

      expect(result.elementIndex).toBe(0);
      expect(result.totalElements).toBe(3);
      expect(result.description).toBe('Element Description');
    });

    it('should move to next element', async () => {
      await handlers.handleNextElement();
      const result = await handlers.handleReadCurrent();

      expect(result.elementIndex).toBe(1);
    });

    it('should move to previous element', async () => {
      handlers = new PageHandlers({
        ...handlers['state'],
        currentIndex: 2
      });

      await handlers.handlePreviousElement();
      const result = await handlers.handleReadCurrent();

      expect(result.elementIndex).toBe(1);
    });

    it('should handle reaching end of elements', async () => {
      handlers = new PageHandlers({
        ...handlers['state'],
        currentIndex: 2
      });

      const result = await handlers.handleNextElement();
      expect(result.message).toBe('Reached end of page');
    });

    it('should handle reaching start of elements', async () => {
      handlers = new PageHandlers({
        ...handlers['state'],
        currentIndex: 0
      });

      const result = await handlers.handlePreviousElement();
      expect(result.message).toBe('At start of page');
    });
  });

  describe('Heading Navigation', () => {
    beforeEach(() => {
      mockPage.evaluate.mockResolvedValue([
        { level: 1, text: 'Main Heading', ariaLabel: null },
        { level: 2, text: 'Subheading 1', ariaLabel: null },
        { level: 2, text: 'Subheading 2', ariaLabel: null }
      ]);
    });

    it('should list headings', async () => {
      const result = await handlers.handleListHeadings();

      expect(result.headingCount).toBe(3);
      expect(result.headings).toBeDefined();
      if (result.headings) {
        expect(result.headings[0].level).toBe(1);
        expect(result.headings[0].text).toBe('Main Heading');
      }
    });

    it('should navigate headings by level', async () => {
      mockPage.$$.mockResolvedValue([{} as ElementHandle<Element>]);
      mockPage.evaluate.mockResolvedValueOnce({ 
        level: 2, 
        text: 'Subheading', 
        ariaLabel: null 
      } as { level: number; text: string; ariaLabel: string | null });

      const result = await handlers.handleNavigateHeadings(2);

      expect(result.navigationType).toBe('headings');
      expect(result.currentHeadingLevel).toBe(2);
    });

    it('should handle no headings found', async () => {
      mockPage.evaluate.mockResolvedValue([] as Array<{ level: number; text: string; ariaLabel: string | null }>);

      const result = await handlers.handleListHeadings();
      expect(result.message).toBe('No headings found on page');
    });
  });

  describe('Landmark Navigation', () => {
    beforeEach(() => {
      mockPage.$$.mockResolvedValue([{} as ElementHandle<Element>]);
      mockPage.evaluate.mockResolvedValue({
        role: 'main',
        label: 'Main Content',
        tag: 'main',
        text: 'Content'
      });
    });

    it('should navigate landmarks', async () => {
      const result = await handlers.handleNavigateLandmarks();

      expect(result.navigationType).toBe('landmarks');
      expect(result.landmarks).toBeDefined();
      if (result.landmarks) {
        expect(result.landmarks[0].role).toBe('main');
        expect(result.landmarks[0].label).toBe('Main Content');
      }
    });

    it('should handle no landmarks found', async () => {
      mockPage.$$.mockResolvedValue([] as Array<ElementHandle<Element>>);

      const result = await handlers.handleNavigateLandmarks();
      expect(result.message).toBe('No landmarks found on page');
    });
  });

  describe('Text Search', () => {
    it('should find text on page', async () => {
      mockPage.evaluate.mockResolvedValue([
        {
          text: 'Search Text',
          context: 'Surrounding text',
          role: 'paragraph'
        }
      ]);

      const result = await handlers.handleFindText('Search Text');

      expect(result.matchCount).toBe(1);
      expect(result.matches).toBeDefined();
      if (result.matches) {
        expect(result.matches[0].text).toBe('Search Text');
      }
    });

    it('should handle text not found', async () => {
      mockPage.evaluate.mockResolvedValue([] as Array<{
        text: string;
        context: string;
        ariaLabel: string | null;
        role: string;
      }>);

      const result = await handlers.handleFindText('Nonexistent Text');
      expect(result.message).toBe('Text "Nonexistent Text" not found on page');
    });
  });

  describe('Cleanup', () => {
    it('should cleanup resources', async () => {
      const mockBrowser = {
        close: jest.fn()
      };

      handlers = new PageHandlers({
        currentUrl: 'https://example.com',
        browser: mockBrowser as unknown as Browser,
        page: mockPage,
        currentIndex: 1,
        currentElement: {} as ElementHandle<Element>,
        navigationType: 'all'
      });

      await handlers.cleanup();

      expect(mockBrowser.close).toHaveBeenCalled();
      expect(handlers['state'].browser).toBeNull();
      expect(handlers['state'].page).toBeNull();
      expect(handlers['state'].currentUrl).toBeNull();
      expect(handlers['state'].currentIndex).toBe(0);
    });
  });
});
