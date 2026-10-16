#!/usr/bin/env node
// A terminal-browser socket backend on top of tmux. Run it inside tmux, then
// point terminal-browser at it:
//   node server.mjs /tmp/tb-tmux.sock &
//   export TERMINAL_BROWSER_TERMINAL_SOCKET=/tmp/tb-tmux.sock
import { execFile } from "node:child_process";
import fs from "node:fs";
import net from "node:net";
import { promisify } from "node:util";

const exec = promisify(execFile);

const socketPath = process.argv[2];
if (!socketPath) {
  process.stderr.write("usage: server.mjs <socket path>]\n");
  process.exit(1);
}

async function tmux(args, input) {
  const running = exec("tmux", args);
  if (input !== undefined) running.child.stdin.end(input);
  return (await running).stdout;
}

const PANE_FORMAT = "#{session_name}\t#{window_id}\t#{pane_id}\t#{pane_tty}\t#{pane_current_command}";

async function listPanes() {
  const listing = await tmux(["list-panes", "-a", "-F", PANE_FORMAT]);
  return listing
    .split("\n")
    .filter((line) => line.trim())
    .map((line) => {
      const [session, window, id, tty, command] = line.split("\t");
      return { id, tab: `${session}:${window}`, tty: tty || null, command: command || null };
    });
}

function shellQuote(argv) {
  return argv.map((arg) => (/^[\w\-./:=+@%,]+$/.test(arg) ? arg : `'${arg.replaceAll("'", `'\\''`)}'`)).join(" ");
}

const methods = {
  async hello() {
    return { name: "tmux (socket example)", methods: Object.keys(methods).filter((name) => name !== "hello") };
  },
  async getCurrentPane({ tty }) {
    const pane = (await listPanes()).find((pane) => pane.tty === tty);
    return { pane: pane ? { id: pane.id, tab: pane.tab } : null };
  },
  async split({ from, direction, command, size }) {
    const axis = direction === "right" || direction === "left" ? "-h" : "-v";
    const before = direction === "left" || direction === "up" ? ["-b"] : [];
    const length = size ? ["-l", `${Math.round(size * 100)}%`] : [];
    await tmux(["split-window", axis, ...before, ...length, "-t", from.id, shellQuote(command)]);
    return {};
  },
  async listPanes() {
    return { panes: await listPanes() };
  },
  async neighbor({ from, direction }) {
    const listing = await tmux(["list-panes", "-t", from.id, "-F", "#{pane_id}\t#{pane_left}\t#{pane_top}\t#{pane_right}\t#{pane_bottom}"]);
    const rects = listing
      .split("\n")
      .filter((line) => line.trim())
      .map((line) => {
        const [id, left, top, right, bottom] = line.split("\t");
        return { id, left: Number(left), top: Number(top), right: Number(right), bottom: Number(bottom) };
      });
    const self = rects.find((rect) => rect.id === from.id);
    if (!self) return { pane: null };
    const beside = {
      right: (rect) => rect.left === self.right + 2,
      left: (rect) => rect.right === self.left - 2,
      down: (rect) => rect.top === self.bottom + 2,
      up: (rect) => rect.bottom === self.top - 2,
    }[direction];
    const overlap = (rect) =>
      direction === "right" || direction === "left"
        ? Math.min(rect.bottom, self.bottom) - Math.max(rect.top, self.top)
        : Math.min(rect.right, self.right) - Math.max(rect.left, self.left);
    let found = null;
    for (const rect of rects) {
      if (rect.id === self.id || !beside(rect) || overlap(rect) < 0) continue;
      if (!found || overlap(rect) > overlap(found)) found = rect;
    }
    return { pane: found ? { id: found.id, tab: from.tab } : null };
  },
  async sendText({ pane, text }) {
    if (text === "") return {};
    await tmux(["load-buffer", "-b", "terminal-browser", "-"], text);
    await tmux(["paste-buffer", "-p", "-d", "-b", "terminal-browser", "-t", pane]);
    return {};
  },
  async focusPane({ pane }) {
    await tmux(["select-window", "-t", pane]);
    await tmux(["select-pane", "-t", pane]);
    return {};
  },
};

async function answer(line) {
  let request;
  try {
    request = JSON.parse(line);
  } catch {
    return { id: null, error: { message: "request is not json" } };
  }
  const method = methods[request.method];
  if (!method) return { id: request.id, error: { message: `unknown method ${request.method}` } };
  try {
    return { id: request.id, result: await method(request.params ?? {}) };
  } catch (error) {
    return { id: request.id, error: { message: error instanceof Error ? error.message : String(error) } };
  }
}

if (fs.existsSync(socketPath)) {
  if (!fs.lstatSync(socketPath).isSocket()) {
    process.stderr.write(`${socketPath} exists and is not a socket, refusing to replace it\n`);
    process.exit(1);
  }
  fs.rmSync(socketPath);
}
const server = net.createServer((connection) => {
  let buffer = "";
  connection.setEncoding("utf8");
  connection.on("error", () => {});
  connection.on("data", async (chunk) => {
    buffer += chunk;
    const newline = buffer.indexOf("\n");
    if (newline < 0) return;
    const reply = await answer(buffer.slice(0, newline));
    connection.end(`${JSON.stringify(reply)}\n`);
  });
});
server.listen(socketPath, () => {
  fs.chmodSync(socketPath, 0o600);
  process.stderr.write(`listening on ${socketPath}\n`);
});
for (const signal of ["SIGINT", "SIGTERM"]) {
  process.on(signal, () => {
    server.close();
    fs.rmSync(socketPath, { force: true });
    process.exit(0);
  });
}
