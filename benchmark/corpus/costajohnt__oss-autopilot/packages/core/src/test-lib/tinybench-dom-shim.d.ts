// tinybench@6.1.4 (pinned exactly by vitest 5.0.0) declares
// `const performanceNow: () => DOMHighResTimeStamp` in its .d.ts without
// declaring or importing that DOM type. This package type-checks with
// `skipLibCheck: false` and no `dom` lib, so the reference is unresolvable
// and `tsc -p tsconfig.tests.json` fails with TS2304. See issue #1676.
//
// Aliasing the single missing name is narrower than adding `dom` to `lib`,
// which would make every browser global (window, document, fetch, …)
// silently type-check in a Node-only package.
//
// This file lives in src/test-lib/ because only tsconfig.tests.json needs it:
// tsconfig.json excludes test files, so tinybench's types never reach the
// production build. Delete it once vitest ships a tinybench that declares
// the type itself (fixed upstream in tinybench 6.2.0, not yet depended on).
declare type DOMHighResTimeStamp = number;
