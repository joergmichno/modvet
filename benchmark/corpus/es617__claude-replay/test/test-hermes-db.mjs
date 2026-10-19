import { describe, it, before, after } from "node:test";
import assert from "node:assert/strict";
import { mkdirSync, rmSync } from "node:fs";
import { join } from "node:path";
import { tmpdir } from "node:os";
import { detectFormat, parseTranscript } from "../src/parser.mjs";
import { resolveSessionId } from "../src/resolve-session.mjs";
import {
  listHermesSessions,
  readHermesSessionRaw,
  matchHermesSessionIds,
  hermesProfileForDbPath,
  isHermesVirtualPath,
  parseHermesVirtualPath,
} from "../src/hermes-db.mjs";

// Live-SQLite reads need the Node 22.5+ built-in node:sqlite.
let DatabaseSync = null;
try {
  ({ DatabaseSync } = await import("node:sqlite"));
} catch { /* older Node — suite is skipped below */ }

const HOME = join(tmpdir(), `claude-replay-hermes-test-${process.pid}`);
const DEFAULT_DB = join(HOME, ".hermes", "state.db");
const CODEX_DB = join(HOME, ".hermes", "profiles", "codex", "state.db");

const SESSION_A = "20260101_120000_abc123";
// Decoy differing only where SESSION_A has "_" — catches unescaped LIKE wildcards.
const SESSION_A_DECOY = "20260101x120000_decoy1";
const SESSION_B = "20260202_130000_def456";

function createDb(path, sessions) {
  const db = new DatabaseSync(path);
  // Deliberately omit reasoning/reasoning_details columns to mimic an older
  // Hermes schema — reads must tolerate missing message columns.
  db.exec(`
    CREATE TABLE sessions (
      id TEXT PRIMARY KEY, title TEXT, source TEXT, cwd TEXT, model TEXT,
      started_at REAL, last_activity_at REAL, ended_at REAL
    );
    CREATE TABLE messages (
      id INTEGER PRIMARY KEY, session_id TEXT, role TEXT, content TEXT,
      tool_calls TEXT, tool_call_id TEXT, tool_name TEXT,
      timestamp REAL, reasoning_content TEXT, compacted INTEGER
    );
  `);
  const insSession = db.prepare(
    "INSERT INTO sessions (id, title, source, started_at, last_activity_at) VALUES (?, ?, ?, ?, ?)",
  );
  const insMessage = db.prepare(
    `INSERT INTO messages (session_id, role, content, tool_calls, tool_call_id, tool_name, timestamp, reasoning_content, compacted)
     VALUES (?, ?, ?, ?, ?, ?, ?, ?, 0)`,
  );
  for (const s of sessions) {
    insSession.run(s.id, s.title, "cli", s.ts, s.ts + 60);
    for (const m of s.messages || []) {
      insMessage.run(s.id, m.role, m.content ?? null, m.tool_calls ?? null,
        m.tool_call_id ?? null, m.tool_name ?? null, m.ts, m.reasoning ?? null);
    }
  }
  db.close();
}

describe("hermes sqlite", { skip: !DatabaseSync && "node:sqlite unavailable" }, () => {
  before(() => {
    mkdirSync(join(HOME, ".hermes", "profiles", "codex"), { recursive: true });
    createDb(DEFAULT_DB, [
      {
        id: SESSION_A, title: "Fix the parser", ts: 1767268800,
        messages: [
          { role: "user", content: "run ls", ts: 1767268800 },
          {
            role: "assistant", content: "on it", ts: 1767268801,
            reasoning: "user wants a listing",
            tool_calls: JSON.stringify([{ id: "c1", call_id: "c1", type: "function", function: { name: "terminal", arguments: JSON.stringify({ command: "ls" }) } }]),
          },
          { role: "tool", content: JSON.stringify({ output: "file.txt" }), tool_call_id: "c1", tool_name: "terminal", ts: 1767268802 },
        ],
      },
      { id: SESSION_A_DECOY, title: "Decoy", ts: 1767268900 },
    ]);
    createDb(CODEX_DB, [
      {
        id: SESSION_B, title: null, ts: 1770033000,
        messages: [
          { role: "user", content: "hello", ts: 1770033000 },
          { role: "assistant", content: "hi!", ts: 1770033001 },
        ],
      },
    ]);
  });

  after(() => {
    rmSync(HOME, { recursive: true, force: true });
  });

  it("lists sessions across default and profile DBs, newest first", () => {
    const sessions = listHermesSessions(HOME);
    assert.equal(sessions.length, 3);
    assert.equal(sessions[0].file, SESSION_B);
    assert.equal(sessions[0].path, `${CODEX_DB}#session:${SESSION_B}`);
    const a = sessions.find((s) => s.file === SESSION_A);
    assert.equal(a.title, "Fix the parser");
    assert.ok(a.date, "sessions carry an ISO date");
  });

  it("reads a session raw despite missing message columns", () => {
    const raw = readHermesSessionRaw(DEFAULT_DB, SESSION_A);
    assert.ok(raw, "session should load from a reduced schema");
    assert.equal(raw.title, "Fix the parser");
    assert.equal(raw.messages.length, 3);
  });

  it("returns null for unknown sessions and missing DBs", () => {
    assert.equal(readHermesSessionRaw(DEFAULT_DB, "nope"), null);
    assert.equal(readHermesSessionRaw(join(HOME, "missing.db"), SESSION_A), null);
  });

  it("parses turns from a virtual path", () => {
    const virtualPath = `${DEFAULT_DB}#session:${SESSION_A}`;
    assert.equal(detectFormat(virtualPath), "hermes");
    const turns = parseTranscript(virtualPath);
    assert.equal(turns.length, 1);
    const tool = turns[0].blocks.find((b) => b.kind === "tool_use");
    assert.equal(tool.tool_call.name, "Bash");
    assert.equal(tool.tool_call.result, "file.txt");
    const thinking = turns[0].blocks.find((b) => b.kind === "thinking");
    assert.equal(thinking.text, "user wants a listing");
  });

  it("resolves exact and prefix session IDs", () => {
    const exact = resolveSessionId(SESSION_B, { home: HOME });
    assert.equal(exact.length, 1);
    assert.equal(exact[0].path, `${CODEX_DB}#session:${SESSION_B}`);
    assert.equal(exact[0].project, "codex");
    assert.equal(exact[0].group, "Hermes");

    const prefix = resolveSessionId("20260101_", { home: HOME });
    assert.equal(prefix.length, 1, "underscore in prefix must not act as a LIKE wildcard");
    assert.equal(prefix[0].path, `${DEFAULT_DB}#session:${SESSION_A}`);
    assert.equal(prefix[0].project, "default");
  });

  it("matchHermesSessionIds prefers exact matches", () => {
    const matches = matchHermesSessionIds(SESSION_A, HOME);
    assert.deepEqual(matches, [{ dbPath: DEFAULT_DB, id: SESSION_A }]);
  });

  it("virtual path helpers round-trip", () => {
    const p = `${DEFAULT_DB}#session:${SESSION_A}`;
    assert.equal(isHermesVirtualPath(p), true);
    assert.equal(isHermesVirtualPath(DEFAULT_DB), false);
    assert.deepEqual(parseHermesVirtualPath(p), { dbPath: DEFAULT_DB, sessionId: SESSION_A });
    assert.equal(hermesProfileForDbPath(DEFAULT_DB), "default");
    assert.equal(hermesProfileForDbPath(CODEX_DB), "codex");
  });
});
