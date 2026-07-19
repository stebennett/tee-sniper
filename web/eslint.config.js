import js from '@eslint/js';
import globals from 'globals';
import tseslintPlugin from '@typescript-eslint/eslint-plugin';
import tseslintParser from '@typescript-eslint/parser';
import reactHooks from 'eslint-plugin-react-hooks';
import reactRefresh from 'eslint-plugin-react-refresh';

export default [
  // `tsc -b` (run before `vite build` in the `build` script) emits `.js`
  // (and `.d.ts`/`.tsbuildinfo`) build artifacts alongside the `.ts`/`.tsx`
  // sources under src/ and test/ — see the matching patterns already in
  // .gitignore. The previous `.eslintrc.cjs` was scoped by the CLI's
  // `--ext ts,tsx` flag, which isn't supported/used with flat config, so
  // that same scoping now has to live in the config's own `files`/`ignores`
  // to avoid linting generated output as if it were source.
  { ignores: ['dist', 'src/**/*.js', 'test/**/*.js'] },
  js.configs.recommended,
  {
    files: ['**/*.{ts,tsx}'],
    languageOptions: {
      ecmaVersion: 2022,
      sourceType: 'module',
      globals: {
        ...globals.browser,
      },
      parser: tseslintParser,
    },
    plugins: {
      '@typescript-eslint': tseslintPlugin,
      'react-hooks': reactHooks,
      'react-refresh': reactRefresh,
    },
    rules: {
      ...tseslintPlugin.configs.recommended.rules,
      ...reactHooks.configs.recommended.rules,
      'react-refresh/only-export-components': 'warn',
      // TypeScript (via `tsc -b` in the build step, using tsconfig's `lib`/`types`)
      // already validates identifier references, including ambient DOM types
      // (e.g. RequestInit) and vitest's `globals: true` test globals (e.g.
      // beforeAll). ESLint's core no-undef is not type-aware and produces
      // false positives for these — the documented typescript-eslint fix is
      // to turn it off for TS/TSX files.
      // https://typescript-eslint.io/troubleshooting/faqs/eslint/#i-get-errors-from-the-no-undef-rule-about-global-variables-not-being-defined-even-though-no-typescript-compilation-errors-happen
      'no-undef': 'off',
    },
  },
];
