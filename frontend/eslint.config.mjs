// Added after a `useMemo` placed below an early return shipped to production
// and crashed the app with React error #310. `tsc`, vitest and `vite build`
// all passed that code: nothing here checked the Rules of Hooks, because
// nothing here ran a linter at all.
//
// Severity is chosen so the suite is green today and goes red on a new
// mistake. Nothing violates any of these now, so the rules that cannot be
// argued with are errors: `rules-of-hooks`, and the React Compiler's `purity`
// and `immutability`.
//
// `set-state-in-effect` stays a warning on purpose. It inlines the body of an
// async function called from an effect and does not model the `await` inside,
// so it reports a cascading render for `useEffect(() => { load(); }, [])`
// where every setState actually lands in a microtask after the fetch. That
// pattern is all over this codebase and is correct; two call sites carry an
// explicit disable with the reasoning. An error there would block a build on
// the linter's limitation rather than on a bug.
import js from '@eslint/js';
import globals from 'globals';
import tseslint from 'typescript-eslint';
import reactHooks from 'eslint-plugin-react-hooks';

export default tseslint.config(
  // A disable comment that no longer suppresses anything is a stale claim about
  // the code; three of them stand on reasoning that a plugin release may fix.
  { linterOptions: { reportUnusedDisableDirectives: 'error' } },
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
      'react-hooks/purity': 'error',
      'react-hooks/set-state-in-effect': 'warn',
      'react-hooks/immutability': 'error',
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
