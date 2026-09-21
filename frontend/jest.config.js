const nextJest = require('next/jest');

const createJestConfig = nextJest({ dir: './' });

/** @type {import('jest').Config} */
const customConfig = {
  testEnvironment: 'jest-environment-jsdom',
  setupFilesAfterEnv: ['<rootDir>/jest.setup.js'],
  moduleNameMapper: {
    '^@/(.*)$': '<rootDir>/$1',
  },
  testMatch: ['**/__tests__/**/*.[jt]s?(x)', '**/?(*.)+(spec|test).[jt]s?(x)'],
};

// createJestConfig returns an async function; we wrap it to patch
// transformIgnorePatterns AFTER next/jest sets its defaults.
const jestConfig = createJestConfig(customConfig);

module.exports = async () => {
  const config = await jestConfig();
  // next/jest sets transformIgnorePatterns to exclude all node_modules.
  // Override to allow ESM packages (lucide-react, framer-motion) to be
  // compiled by SWC.
  config.transformIgnorePatterns = [
    '/node_modules/(?!(lucide-react|framer-motion|@motionone|styleq|tslib)/)',
  ];
  return config;
};
