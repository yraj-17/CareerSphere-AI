import { defineConfig, globalIgnores } from 'eslint/config';
import nextVitals from 'eslint-config-next/core-web-vitals';

export default defineConfig([
  ...nextVitals,
  {
    rules: {
      '@next/next/no-img-element': 'warn',
      // This React 18 codebase intentionally loads/subscribes from effects.
      // React Compiler diagnostics introduced by the Next 16 preset are not
      // applicable until the project opts into the compiler.
      'react-hooks/set-state-in-effect': 'off',
      'react-hooks/static-components': 'off',
      'react-hooks/preserve-manual-memoization': 'off',
    },
  },
  globalIgnores([
    '.next/**',
    'coverage/**',
    'node_modules/**',
  ]),
]);
