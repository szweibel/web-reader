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

    it('should provide accessible descriptions for elements', async () => {
      mockPage.evaluate.mockResolvedValueOnce('Submit form button. This button submits the contact form');

      const result = await handlers.handleReadCurrent();
      expect(result.description).toBe('Submit form button. This button submits the contact form');
    });

    it('should handle live region updates', async () => {
      mockPage.evaluate.mockResolvedValueOnce('Alert: Form submitted successfully');

      const result = await handlers.handleReadCurrent();
      expect(result.description).toBe('Alert: Form submitted successfully');
    });

    it('should handle ARIA expanded states', async () => {
      mockPage.evaluate.mockResolvedValueOnce('Main menu button (expanded)');

      const result = await handlers.handleReadCurrent();
      expect(result.description).toBe('Main menu button (expanded)');
    });

    it('should handle interactive element states', async () => {
      mockPage.evaluate.mockResolvedValueOnce('Newsletter subscription checkbox (checked)');

      const result = await handlers.handleReadCurrent();
      expect(result.description).toBe('Newsletter subscription checkbox (checked)');
    });

    it('should provide context for form controls', async () => {
      mockPage.evaluate.mockResolvedValueOnce('Email address textbox (required): Enter your email');

      const result = await handlers.handleReadCurrent();
      expect(result.description).toBe('Email address textbox (required): Enter your email');
    });
  });

  describe('Heading Navigation', () => {
    beforeEach(() => {
      mockPage.evaluate.mockResolvedValue([
        { level: 1, text: 'Main Heading', ariaLabel: 'Welcome to our site' },
        { level: 2, text: 'Subheading 1', ariaLabel: 'About us section' },
        { level: 2, text: 'Subheading 2', ariaLabel: 'Contact information' },
        { level: 3, text: 'Sub-subheading', ariaLabel: 'Office locations' }
      ]);
    });

    it('should list headings', async () => {
      mockPage.evaluate.mockResolvedValue([
        { level: 1, text: 'Main Heading', ariaLabel: 'Welcome to our site' },
        { level: 2, text: 'Subheading 1', ariaLabel: 'About us section' },
        { level: 2, text: 'Subheading 2', ariaLabel: 'Contact information' },
        { level: 3, text: 'Sub-subheading', ariaLabel: 'Office locations' }
      ]);

      const result = await handlers.handleListHeadings();

      expect(result.headingCount).toBe(4);
      expect(result.headings).toBeDefined();
      if (result.headings) {
        expect(result.headings[0].level).toBe(1);
        expect(result.headings[0].text).toBe('Welcome to our site');
      }
    });

    it('should navigate headings by level', async () => {
      mockPage.$$.mockResolvedValue([{} as ElementHandle<Element>]);
      
      // Mock the evaluate call for getting heading info
      mockPage.evaluate.mockResolvedValueOnce({ 
        level: 2, 
        text: 'About us section', 
        ariaLabel: null 
      });
      
      // Mock the evaluate call for getting description
      mockPage.evaluate.mockResolvedValueOnce('Level 2 heading: About us section');

      const result = await handlers.handleNavigateHeadings(2);

      expect(result.navigationType).toBe('headings');
      expect(result.currentHeadingLevel).toBe(2);
      expect(result.description).toContain('Switched to level 2 headings');
      expect(result.description).toContain('About us section');
    });

    it('should handle no headings found', async () => {
      mockPage.evaluate.mockResolvedValue([]);

      const result = await handlers.handleListHeadings();
      expect(result.message).toBe('No headings found on page');
    });

    it('should navigate heading hierarchy', async () => {
      mockPage.$$.mockResolvedValue([{} as ElementHandle<Element>]);
      
      // Navigate to level 2 heading
      mockPage.evaluate
        .mockResolvedValueOnce({ level: 2, text: 'About us section', ariaLabel: null })
        .mockResolvedValueOnce('Level 2 heading: About us section');

      let result = await handlers.handleNavigateHeadings(2);
      expect(result.description).toContain('About us section');

      // Mock focusable elements for next element
      mockPage.$$.mockResolvedValueOnce([
        {} as ElementHandle<Element>,
        {} as ElementHandle<Element>
      ]);

      // Navigate to child heading (level 3)
      mockPage.evaluate
        .mockResolvedValueOnce('Level 3 heading: Office locations');

      result = await handlers.handleNextElement();
      expect(result.description).toBe('Level 3 heading: Office locations');
    });

    it('should announce heading level changes', async () => {
      mockPage.$$.mockResolvedValue([{} as ElementHandle<Element>]);
      
      // Start at level 1
      mockPage.evaluate
        .mockResolvedValueOnce({ level: 1, text: 'Main Heading', ariaLabel: 'Welcome to our site' })
        .mockResolvedValueOnce('Level 1 heading: Welcome to our site');

      let result = await handlers.handleNavigateHeadings(1);
      expect(result.description).toContain('Switched to level 1 headings');
      expect(result.description).toContain('Welcome to our site');

      // Move to level 2
      mockPage.evaluate
        .mockResolvedValueOnce({ level: 2, text: 'Subheading 1', ariaLabel: 'About us section' })
        .mockResolvedValueOnce('Level 2 heading: About us section');

      result = await handlers.handleNavigateHeadings(2);
      expect(result.description).toContain('Switched to level 2 headings');
      expect(result.description).toContain('About us section');
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
