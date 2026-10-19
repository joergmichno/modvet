// Empty shim for Node.js modules not needed in browser
export function readFileSync() { throw new Error("readFileSync not available in browser"); }
export function deflateSync() { throw new Error("deflateSync not available in browser"); }
export function fileURLToPath(url) { return url; }
// node:fs / node:path / node:os / node:module stubs used by hermes-db.mjs —
// its helpers degrade to no-ops in the browser and are never called there.
export function existsSync() { return false; }
export function readdirSync() { return []; }
export function statSync() { throw new Error("statSync not available in browser"); }
export function join(...parts) { return parts.join("/"); }
export const sep = "/";
export function homedir() { return ""; }
export function createRequire() { throw new Error("createRequire not available in browser"); }
