// @ts-check
import tsPlugin from '@typescript-eslint/eslint-plugin';
import tsParser from '@typescript-eslint/parser';
import reactHooks from 'eslint-plugin-react-hooks';

/**
 * Flat config (ESLint 9+/10).
 * - typescript-eslint flat/recommended: parser + eslint-recommended overrides + recommended rules
 * - eslint-plugin-react-hooks: rules-of-hooks + exhaustive-deps
 */
const typescriptEslintFlat = tsPlugin.configs['flat/recommended'];

export default [
  {
    ignores: [
      'dist/**',
      'node_modules/**',
      'coverage/**',
      'playwright-report/**',
      'test-results/**',
    ],
  },
  ...typescriptEslintFlat,
  {
    files: ['src/**/*.{ts,tsx}'],
    plugins: {
      'react-hooks': reactHooks,
    },
    rules: {
      'react-hooks/rules-of-hooks': 'error',
      'react-hooks/exhaustive-deps': 'warn',
    },
  },
];
