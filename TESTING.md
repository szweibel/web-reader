# Web Reader Testing Overview

This document provides a structured overview of the testing strategy used in the Web Reader project, designed for clarity and ease of understanding.

## Test Files

The test files are located in the `src/__tests__` directory:

### Core Test Files
- `browser.test.ts`: Tests real browser interactions using example.com
- `mcp.test.ts`: Tests basic handler functionality and error cases
- `setup.ts`: Mock implementations and shared test utilities

## Testing Strategy

The project follows a focused, incremental testing approach:

### 1. Core Browser Testing
Tests use real websites (example.com) to:
- Verify basic navigation works
- Ensure element selection functions
- Test content extraction
- Validate page structure parsing

Example test:
```typescript
it('should find heading', async () => {
  const h1 = await page.$('h1');
  expect(h1).toBeTruthy();
  
  const text = await page.evaluate(el => el?.textContent || '', h1);
  expect(text).toBe('Example Domain');
});
```

### 2. Handler Testing
Tests focus on error cases and basic functionality:
- Verify error handling
- Test state management
- Validate input validation
- Check initialization

Example test:
```typescript
it('should handle missing page', async () => {
  const handlers = new PageHandlers({
    currentUrl: null,
    browser: null,
    page: null,
    currentIndex: 0,
    currentElement: null,
    navigationType: 'all'
  });

  await expect(handlers.handleReadCurrent())
    .rejects.toThrow('No page is currently open');
});
```

### 3. Test Environment
Tests run in two environments:

1. **Node Environment** (`node`)
   - Used for handler and utility tests
   - Fast execution
   - Focus on error cases

2. **Browser Environment** (`browser`)
   - Uses Puppeteer for real browser testing
   - Tests against example.com
   - Verifies core functionality

## Expanding Test Coverage

When adding new tests:

1. **Start Simple**
   - Begin with basic functionality
   - Use example.com when possible
   - Focus on one feature at a time

2. **Add Complexity Gradually**
   - Start with happy paths
   - Add error cases
   - Consider edge cases
   - Test accessibility features

3. **Consider Test Categories**
   - Navigation tests
   - Element selection tests
   - Accessibility tests
   - Error handling tests
   - Live region tests

4. **Follow Best Practices**
   - Keep tests focused
   - Use clear descriptions
   - Clean up resources
   - Handle async properly
   - Consider test isolation

## Configuration

The project uses separate Jest configurations for node and browser tests:

```javascript
module.exports = {
  projects: [
    {
      displayName: 'node',
      testEnvironment: 'node',
      testMatch: ['**/src/__tests__/mcp.test.ts']
    },
    {
      displayName: 'browser',
      preset: 'jest-puppeteer',
      testEnvironment: 'puppeteer',
      testMatch: ['**/src/__tests__/browser.test.ts']
    }
  ]
};
```

## Best Practices

1. **Test Structure**
   - One concept per test
   - Clear test descriptions
   - Proper setup and cleanup
   - Handle async correctly

2. **Browser Testing**
   - Use stable test sites
   - Handle loading states
   - Clean up resources
   - Consider timeouts

3. **Error Handling**
   - Test error cases explicitly
   - Verify error messages
   - Handle cleanup after errors
   - Test timeout scenarios

4. **Code Quality**
   - TypeScript for type safety
   - Proper null handling
   - Clear assertions
   - Meaningful test data

## Future Expansion

When expanding test coverage:

1. **New Features**
   - Start with basic tests
   - Add to browser.test.ts or mcp.test.ts
   - Consider new test files for complex features
   - Maintain test isolation

2. **Complex Scenarios**
   - Add gradually
   - Document assumptions
   - Consider performance
   - Test accessibility

3. **Integration Tests**
   - Test feature combinations
   - Verify workflows
   - Consider user scenarios
   - Test real-world cases

4. **Performance Tests**
   - Add as needed
   - Focus on critical paths
   - Consider timeouts
   - Test resource cleanup
