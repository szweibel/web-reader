# Web Reader Testing Guide

This guide provides essential information for testing the Web Reader MCP server, a screen reader tool that helps blind users navigate web pages through voice feedback. The testing suite focuses on accessibility features, browser interactions, and state management.

## Quick Start

```bash
# Run all tests
npm test

# Run tests in watch mode
npm run test:watch

# Run specific test file
npm test src/__tests__/mcp.test.ts
```

## Test Structure

### Test Files (`src/__tests__/`)
- `browser.test.ts`: Browser interaction tests using Puppeteer
- `mcp.test.ts`: Handler and state management tests
- `setup.ts`: Test utilities and mocks

### Test Environments
1. Node (`mcp.test.ts`)
   - Handler functionality
   - State management
   - Mock-based testing

2. Browser (`browser.test.ts`)
   - Real browser testing via Puppeteer
   - Uses example.com as test site
   - Accessibility verification

## Core Test Areas

### 1. Browser Interactions
```typescript
// Navigation
await page.goto('https://example.com');
expect(await page.title()).toBe('Example Domain');

// Element Finding
const elements = await page.$$('a[href], button, [role="button"]');
```

### 2. Handler Functionality
```typescript
// Element Navigation
const result = await handlers.handleNextElement();
expect(result.elementIndex).toBe(1);

// Heading Navigation
const headings = await handlers.handleListHeadings();
expect(headings.length).toBeGreaterThan(0);
```

### 3. Accessibility Features
- ARIA attributes/labels
- Live region updates
- Interactive states
- Form controls
- Heading hierarchy
- Landmark navigation

## Test Categories

### 1. Navigation Tests
- URL navigation
- Element traversal
- Heading navigation
- Landmark navigation
- Error handling

### 2. Accessibility Tests
- ARIA attributes
- Screen reader output
- Keyboard navigation
- Focus management
- Live regions

### 3. Error Tests
- Invalid URLs
- Missing elements
- Network errors
- Resource cleanup
- State recovery

### 4. State Tests
- Navigation state
- Element selection
- Mode switching
- Resource management

## Writing Tests

### Test Structure
```typescript
describe('Feature', () => {
  // Setup
  beforeEach(() => {
    mockPage = createMockPage();
    handlers = new PageHandlers(initialState);
  });

  // Test cases
  it('should handle basic case', async () => {
    const result = await handlers.someMethod();
    expect(result).toBeDefined();
  });

  it('should handle error case', async () => {
    await expect(handlers.someMethod())
      .rejects.toThrow();
  });
});
```

### Mocking Guidelines
1. Page Methods
```typescript
mockPage.evaluate.mockResolvedValue('description');
mockPage.$$.mockResolvedValue([element]);
```

2. Browser Events
```typescript
mockPage.on('console', callback);
mockPage.evaluate(() => console.log('event'));
```

3. Navigation State
```typescript
handlers = new PageHandlers({
  currentIndex: 0,
  navigationType: 'all'
});
```

## Best Practices

### 1. Test Organization
- One concept per test
- Clear descriptions
- Proper setup/cleanup
- Async handling

### 2. Accessibility Testing
- Test ARIA attributes
- Verify descriptions
- Check state changes
- Validate navigation

### 3. Error Handling
- Test edge cases
- Verify messages
- Check recovery
- Resource cleanup

### 4. State Management
- Verify transitions
- Test persistence
- Handle race conditions
- Check cleanup

## Configuration

Jest configuration in `jest.config.cjs`:
```javascript
{
  projects: [
    {
      displayName: 'node',
      testMatch: ['**/mcp.test.ts']
    },
    {
      displayName: 'browser',
      preset: 'jest-puppeteer',
      testMatch: ['**/browser.test.ts']
    }
  ]
}
```
