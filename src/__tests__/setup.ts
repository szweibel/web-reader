import { jest } from '@jest/globals';

// Mock the say module for text-to-speech
jest.mock('say', () => {
  return {
    __esModule: true,
    default: {
      speak: jest.fn().mockImplementation((...args: any[]) => {
        const callback = args[args.length - 1];
        if (typeof callback === 'function') callback();
      }),
      stop: jest.fn()
    }
  };
});

// Extend Jest timeout for all tests
jest.setTimeout(30000);
