import { describe, it } from "node:test";
import assert from "node:assert/strict";
import { getTheme, listThemes, themeToCss, loadThemeFile } from "../src/themes.mjs";
import { writeFileSync, unlinkSync } from "node:fs";
import { tmpdir } from "node:os";
import { join } from "node:path";

describe("getTheme", () => {
  it("returns a built-in theme", () => {
    const theme = getTheme("dracula");
    assert.equal(theme.bg, "#282a36");
    assert.equal(theme.accent, "#bd93f9");
  });

  it("throws on unknown theme", () => {
    assert.throws(() => getTheme("nonexistent"), /Unknown theme/);
  });
});

describe("listThemes", () => {
  it("returns sorted theme names", () => {
    const names = listThemes();
    assert.deepEqual(names, ["bubbles", "dracula", "github-light", "monokai", "solarized-dark", "tokyo-night"]);
  });
});

describe("themeToCss", () => {
  it("generates CSS :root block", () => {
    const css = themeToCss(getTheme("tokyo-night"));
    assert.match(css, /^:root \{/);
    assert.match(css, /--bg: #1a1b26/);
    assert.match(css, /--accent: #bb9af7/);
    assert.match(css, /\}$/);
  });
});

describe("loadThemeFile", () => {
  it("loads and merges with defaults", () => {
    const path = join(tmpdir(), "test-theme.json");
    writeFileSync(path, JSON.stringify({ bg: "#000000" }));
    try {
      const theme = loadThemeFile(path);
      assert.equal(theme.bg, "#000000");
      // Filled from tokyo-night defaults
      assert.equal(theme.accent, "#bb9af7");
    } finally {
      unlinkSync(path);
    }
  });

  it("throws on non-object JSON", () => {
    const path = join(tmpdir(), "test-theme-bad.json");
    writeFileSync(path, '"not an object"');
    try {
      assert.throws(() => loadThemeFile(path), /JSON object/);
    } finally {
      unlinkSync(path);
    }
  });
});
