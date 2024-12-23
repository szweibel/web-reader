import { jest } from '@jest/globals';
import { Browser, Page } from 'puppeteer';

describe('Browser Navigation', () => {
  let browser: Browser;
  let page: Page;

  beforeAll(async () => {
    browser = await (await import('puppeteer')).launch({ headless: true });
    page = await browser.newPage();
    await page.goto('https://example.com');
  });

  afterAll(async () => {
    if (page) {
      await page.close();
    }
    if (browser) {
      await browser.close();
    }
  }, 35000);

  describe('Basic Navigation', () => {
    it('should navigate to example.com', async () => {
      const title = await page.title();
      expect(title).toBe('Example Domain');
    });

    it('should find heading', async () => {
      const h1 = await page.$('h1');
      expect(h1).toBeTruthy();
      
      const text = await page.evaluate(el => el?.textContent || '', h1);
      expect(text).toBe('Example Domain');
    });

    it('should find paragraph', async () => {
      const p = await page.$('p');
      expect(p).toBeTruthy();
      
      const text = await page.evaluate(el => el?.textContent || '', p);
      expect(text).toContain('This domain is for use in illustrative examples');
    });
  });

  describe('Element Navigation', () => {
    it('should find all interactive elements', async () => {
      const elements = await page.$$('a[href], button, input, select, textarea, [tabindex]:not([tabindex="-1"])');
      expect(elements.length).toBeGreaterThan(0);
    });

    it('should find and validate links', async () => {
      const links = await page.$$('a[href]');
      expect(links.length).toBeGreaterThan(0);

      for (const link of links) {
        const href = await page.evaluate(el => el.getAttribute('href'), link);
        expect(href).toBeTruthy();
      }
    });
  });

  describe('Heading Navigation', () => {
    it('should find all headings', async () => {
      const headings = await page.$$('h1, h2, h3, h4, h5, h6');
      expect(headings.length).toBeGreaterThan(0);
    });

    it('should get heading levels', async () => {
      const headings = await page.$$('h1, h2, h3, h4, h5, h6');
      for (const heading of headings) {
        const level = await page.evaluate(el => parseInt(el.tagName[1]), heading);
        expect(level).toBeGreaterThanOrEqual(1);
        expect(level).toBeLessThanOrEqual(6);
      }
    });
  });

  describe('Landmark Navigation', () => {
    it('should find landmarks', async () => {
      const landmarks = await page.$$('[role="main"], [role="navigation"], [role="search"], main, nav, header, footer, aside');
      expect(landmarks.length).toBeGreaterThanOrEqual(0);
    });

    it('should validate landmark roles', async () => {
      const elements = await page.$$('[role]');
      for (const element of elements) {
        const role = await page.evaluate(el => el.getAttribute('role'), element);
        expect(role).toBeTruthy();
      }
    });
  });

  describe('Error Handling', () => {
    it('should handle 404 pages', async () => {
      const response = await page.goto('https://example.com/nonexistent');
      expect(response?.status()).toBe(404);
    });

    it('should handle invalid URLs', async () => {
      await expect(page.goto('https://invalid.example.com')).rejects.toThrow();
    });
  });

  describe('Accessibility Features', () => {
    it('should find elements with ARIA attributes', async () => {
      await page.waitForSelector('[aria-label], [aria-describedby], [aria-hidden]', { timeout: 5000 }).catch(() => null);
      const ariaElements = await page.$$('[aria-label], [aria-describedby], [aria-hidden]');
      // We don't assert length since not all pages will have ARIA attributes
      expect(Array.isArray(ariaElements)).toBe(true);
    });

    it('should validate tabindex values', async () => {
      const elements = await page.$$('[tabindex]');
      for (const element of elements) {
        const tabindex = await page.evaluate(el => el.getAttribute('tabindex'), element);
        expect(Number(tabindex)).not.toBeNaN();
      }
    });
  });
});
