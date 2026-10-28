// Added after a `useMemo` placed below an early return shipped to production
// and crashed the app with React error #310. `tsc`, vitest and `vite build`
// all passed that code: nothing here checked the Rules of Hooks, because
// nothing here ran a linter at all.
//
// Severity is chosen so the suite is green today and goes red on a new
// mistake. `rules-of-hooks` is an error with no current violations. The React
// Compiler rules in this plugin (purity, set-state-in-effect, immutability)
// do flag real patterns in the existing code, so they warn rather than block
// a build on work nobody has scheduled yet.
import js from '@eslint/js';
import globals from 'globals';
import tseslint from 'typescript-eslint';
import reactHooks from 'eslint-plugin-react-hooks';

export default tseslint.config(
  // `._*` are AppleDouble stubs the SMB volume leaves beside real files; they
  // carry an extended attribute, not source, and do not parse.
  { ignores: ['dist', 'coverage', '**/._*'] },
  js.configs.recommended,
  ...tseslint.configs.recommended,
  reactHooks.configs.flat['recommended-latest'],
  {
    files: ['src/**/*.{ts,tsx}', 'public/*.{ts,js}'],
    languageOptions: { globals: { ...globals.browser, ...globals.serviceworker } },
  },
  { files: ['vite.config.ts', 'tailwind.config.js'], languageOptions: { globals: globals.node } },
  {
    files: ['postcss.config.js'],
    languageOptions: { sourceType: 'commonjs', globals: globals.node },
  },
  {
    rules: {
      'react-hooks/rules-of-hooks': 'error',
      'react-hooks/exhaustive-deps': 'warn',
      'react-hooks/purity': 'warn',
      'react-hooks/set-state-in-effect': 'warn',
      'react-hooks/immutability': 'warn',
      // The codebase uses `err: any` on caught errors and `any` for NHTSA's
      // untyped payloads throughout; flagging 64 of them says nothing new.
      '@typescript-eslint/no-explicit-any': 'off',
      // `catch {}` is deliberate where a failure is already handled by the
      // state it leaves behind — a preload warm, a revoked blob URL.
      'no-empty': ['error', { allowEmptyCatch: true }],
      '@typescript-eslint/no-unused-vars': ['error', { argsIgnorePattern: '^_', varsIgnorePattern: '^_' }],
    },
  },
);
