/**
 * Hermes SQLite reader — shared by editor-server, CLI, parser, and resolver.
 *
 * Hermes stores sessions in SQLite at:
 *   ~/.hermes/state.db                (default profile)
 *   ~/.hermes/profiles/<name>/state.db  (named profiles, e.g. "codex")
 *
 * Each DB has tables `sessions(id, title, source, cwd, model, started_at,
 * last_activity_at, ended_at, ...)` and `messages(session_id, role, content,
 * tool_calls, tool_call_id, tool_name, timestamp, reasoning_content, compacted)`.
 *
 * We read with the Node 22.5+ built-in `node:sqlite` (DatabaseSync) so there
 * is no native dependency. On older Node or missing DB the helpers return
 * null/[] and the caller degrades silently.
 */

import { existsSync, readdirSync, statSync } from "node:fs";
import { join, sep } from "node:path";
import { homedir } from "node:os";
import { createRequire } from "node:module";

// Synchronous probe (no top-level await — this module is part of the browser
// bundle, where the shimmed createRequire throws and DatabaseSync stays null).
let DatabaseSync = null;
try {
  DatabaseSync = createRequire(import.meta.url)("node:sqlite").DatabaseSync;
} catch {
  DatabaseSync = null;
}

function getHermesHomes(homeDir) {
  const homes = [join(homeDir, ".hermes")];
  try {
    const profilesDir = join(homeDir, ".hermes", "profiles");
    if (existsSync(profilesDir)) {
      for (const name of readdirSync(profilesDir)) {
        const p = join(profilesDir, name);
        try {
          if (!statSync(p).isDirectory()) continue;
        } catch { continue; }
        homes.push(p);
      }
    }
  } catch { /* ignore */ }
  return homes;
}

function getHermesDbPaths(homeDir) {
  const homes = getHermesHomes(homeDir);
  const out = [];
  for (const h of homes) {
    const dbPath = join(h, "state.db");
    if (existsSync(dbPath)) out.push(dbPath);
  }
  return out;
}

function toIso(ts) {
  if (ts == null || ts === "") return null;
  const n = typeof ts === "string" ? parseFloat(ts) : ts;
  if (!Number.isFinite(n) || n <= 0) return null;
  const ms = n < 1_577_836_800_000 ? n * 1000 : n;
  const d = new Date(ms);
  return Number.isNaN(d.getTime()) ? null : d.toISOString();
}

export function isHermesVirtualPath(p) {
  return typeof p === "string" && p.includes("#session:");
}

export function parseHermesVirtualPath(p) {
  const idx = p.indexOf("#session:");
  if (idx === -1) return null;
  const dbPath = p.slice(0, idx);
  const sessionId = p.slice(idx + "#session:".length).split(/[/?#]/, 1)[0].trim();
  if (!dbPath || !sessionId) return null;
  return { dbPath, sessionId };
}

export function getHermesHomesSync(homeDir = homedir()) {
  return getHermesHomes(homeDir);
}

export function getHermesDbPathsSync(homeDir = homedir()) {
  return getHermesDbPaths(homeDir);
}

/**
 * Profile name for a Hermes DB path: "codex" for
 * ~/.hermes/profiles/codex/state.db, "default" for ~/.hermes/state.db.
 */
export function hermesProfileForDbPath(dbPath) {
  const marker = sep + "profiles" + sep;
  const idx = dbPath.indexOf(marker);
  if (idx === -1) return "default";
  return dbPath.slice(idx + marker.length).split(sep)[0] || "default";
}

/**
 * Find sessions whose ID matches `idOrPrefix` (exact first, then prefix)
 * across the default DB and all profile DBs. Returns [{ dbPath, id }].
 */
export function matchHermesSessionIds(idOrPrefix, homeDir = homedir()) {
  if (!DatabaseSync) return [];
  const out = [];
  for (const dbPath of getHermesDbPaths(homeDir)) {
    let db;
    try {
      db = new DatabaseSync(dbPath, { readOnly: true });
    } catch { continue; }
    try {
      const exact = db.prepare("SELECT id FROM sessions WHERE id = ?").get(idOrPrefix);
      if (exact) {
        out.push({ dbPath, id: exact.id });
        continue;
      }
      // Escape LIKE wildcards — Hermes IDs contain underscores.
      const escaped = idOrPrefix.replace(/[\\%_]/g, (c) => "\\" + c);
      const rows = db.prepare(
        "SELECT id FROM sessions WHERE id LIKE ? ESCAPE '\\' LIMIT 5",
      ).all(escaped + "%");
      for (const r of rows) out.push({ dbPath, id: r.id });
    } catch { /* ignore per-db errors */ }
    finally {
      try { db.close(); } catch { /* ignore */ }
    }
  }
  return out;
}

/**
 * Read a single Hermes session from SQLite and return the raw export shape
 * { id, title, source, cwd, model, started_at, messages: [...] } or null.
 * Sync — suitable for use from the parser and CLI hot path.
 */
export function readHermesSessionRaw(dbPath, sessionId) {
  if (!DatabaseSync || !existsSync(dbPath)) return null;
  let db;
  try {
    db = new DatabaseSync(dbPath, { readOnly: true });
  } catch { return null; }
  try {
    const probe = db.prepare(
      "SELECT name FROM sqlite_master WHERE type='table' AND name IN ('sessions','messages')",
    ).all();
    const names = new Set(probe.map((r) => r.name));
    if (!names.has("sessions") || !names.has("messages")) return null;

    const session = db.prepare("SELECT * FROM sessions WHERE id = ?").get(sessionId);
    if (!session) return null;

    // SELECT * so DBs from older/newer Hermes versions (whose message columns
    // differ) still load; the parser tolerates missing fields.
    const messages = db.prepare(
      "SELECT * FROM messages WHERE session_id = ? ORDER BY timestamp ASC, id ASC",
    ).all(sessionId);

    return {
      id: session.id,
      title: session.title ?? null,
      source: session.source ?? null,
      cwd: session.cwd ?? null,
      model: session.model ?? null,
      started_at: session.started_at ?? null,
      ended_at: session.ended_at ?? null,
      last_activity_at: session.last_activity_at ?? null,
      git_branch: session.git_branch ?? null,
      git_repo_root: session.git_repo_root ?? null,
      messages,
      _dbPath: dbPath,
    };
  } catch { return null; }
  finally {
    try { db.close(); } catch { /* ignore */ }
  }
}

export function readHermesSessionText(dbPath, sessionId) {
  const raw = readHermesSessionRaw(dbPath, sessionId);
  if (!raw) return null;
  return JSON.stringify(raw);
}

/**
 * Discover Hermes sessions across the default home and all profiles.
 * Returns an array of { file, path, date, title } objects compatible with
 * the editor-server's group shape.
 */
export function listHermesSessions(homeDir = homedir()) {
  if (!DatabaseSync) return [];
  const out = [];
  const seen = new Set();
  const dbPaths = getHermesDbPaths(homeDir);
  for (const dbPath of dbPaths) {
    let db;
    try {
      db = new DatabaseSync(dbPath, { readOnly: true });
    } catch { continue; }
    try {
      const probe = db.prepare(
        "SELECT name FROM sqlite_master WHERE type='table' AND name IN ('sessions','messages')",
      ).all();
      const names = new Set(probe.map((r) => r.name));
      if (!names.has("sessions") || !names.has("messages")) continue;

      const rows = db.prepare(
        `SELECT id, title, source, cwd, model, started_at, last_activity_at, ended_at
         FROM sessions
         ORDER BY COALESCE(last_activity_at, ended_at, started_at) DESC
         LIMIT 500`,
      ).all();

      for (const row of rows) {
        if (!row.id || seen.has(row.id)) continue;
        seen.add(row.id);
        const ts = row.last_activity_at ?? row.ended_at ?? row.started_at;
        const date = toIso(ts);
        out.push({
          file: row.id,
          path: `${dbPath}#session:${row.id}`,
          date,
          title: row.title || null,
          _hermesSource: row.source || null,
          _hermesDbPath: dbPath,
        });
      }
    } catch { /* ignore per-db errors */ }
    finally {
      try { db.close(); } catch { /* ignore */ }
    }
  }
  out.sort((a, b) => {
    if (!a.date && !b.date) return 0;
    if (!a.date) return 1;
    if (!b.date) return -1;
    return b.date.localeCompare(a.date);
  });
  return out;
}
