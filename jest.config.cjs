/** @type {import('ts-jest').JestConfigWithTsJest} */
module.exports = {
  testEnvironment: 'node',
  testEnvironmentOptions: {
    env: {
      NODE_ENV: 'test'
    }
  },
  projects: [
    {
      displayName: 'node',
      testEnvironment: 'node',
      testEnvironmentOptions: {
        env: {
          NODE_ENV: 'test'
        }
      },
      testMatch: [
        '**/src/__tests__/mcp.test.ts'
      ],
      transform: {
        '^.+\\.(ts|tsx|js|jsx)$': ['ts-jest', {
          useESM: true,
          tsconfig: {
            allowJs: true,
            esModuleInterop: true
          }
        }]
      },
      moduleNameMapper: {
        '^(\\.{1,2}/.*)\\.js$': '$1'
      },
      transformIgnorePatterns: [
        '/node_modules/(?!(@modelcontextprotocol|zod)/)'
      ],
      extensionsToTreatAsEsm: ['.ts'],
      setupFilesAfterEnv: [
        '<rootDir>/src/__tests__/setup.ts'
      ]
    },
    {
      displayName: 'browser',
      preset: 'jest-puppeteer',
      testEnvironment: 'puppeteer',
      testMatch: [
        '**/src/__tests__/browser.test.ts'
      ],
      transform: {
        '^.+\\.ts$': ['ts-jest', {
          useESM: true,
          tsconfig: {
            allowJs: true,
            esModuleInterop: true
          }
        }]
      },
      moduleNameMapper: {
        '^(\\.{1,2}/.*)\\.js$': '$1'
      },
      transformIgnorePatterns: [
        '/node_modules/(?!(@modelcontextprotocol|zod)/)'
      ],
      extensionsToTreatAsEsm: ['.ts']
    }
  ],
  maxWorkers: 1, // Run tests sequentially
  testTimeout: 30000 // 30 second timeout
};
