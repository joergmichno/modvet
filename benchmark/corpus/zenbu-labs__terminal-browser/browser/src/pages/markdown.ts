import type { Theme } from "../ui/theme";
import { escape, pageColors } from "./scheme";

// forcing esm
const parser = Promise.all([import("micromark"), import("micromark-extension-gfm")]).then(
  ([{ micromark }, { gfm, gfmHtml }]) =>
    (source: string) => micromark(source, { extensions: [gfm()], htmlExtensions: [gfmHtml()] }),
);

export async function renderMarkdown(source: string, title: string, theme: Theme | null): Promise<string> {
  const body = (await parser)(source);
  const { fg, muted, accent, hairline, field } = pageColors(theme);
  return `<!doctype html>
<html><head><meta charset="utf-8"><title>${escape(title)}</title>
<style>
  :root { color-scheme: dark light; }
  html, body { margin: 0; background: transparent; color: ${fg}; }
  body { font: 15px/1.65 -apple-system, BlinkMacSystemFont, "Segoe UI", system-ui, sans-serif; padding: 32px 40px 64px; max-width: 760px; }
  h1, h2, h3, h4 { line-height: 1.25; margin: 1.6em 0 0.5em; font-weight: 600; }
  h1 { font-size: 1.8em; margin-top: 0; } h2 { font-size: 1.35em; } h3 { font-size: 1.1em; }
  p, ul, ol, pre, table, blockquote { margin: 0 0 1em; }
  a { color: ${accent}; text-decoration: none; } a:hover { text-decoration: underline; }
  code, pre { font: 13px/1.5 ui-monospace, SFMono-Regular, Menlo, monospace; }
  code { background: ${field}; padding: 0.1em 0.35em; border-radius: 4px; }
  pre { background: ${field}; padding: 12px 14px; border-radius: 6px; overflow-x: auto; }
  pre code { background: none; padding: 0; }
  blockquote { color: ${muted}; border-left: 3px solid ${hairline}; margin-left: 0; padding-left: 14px; }
  hr { border: 0; border-top: 1px solid ${hairline}; margin: 2em 0; }
  table { border-collapse: collapse; } th, td { border: 1px solid ${hairline}; padding: 4px 10px; text-align: left; }
  img { max-width: 100%; }
  ul.contains-task-list { list-style: none; padding-left: 0.5em; }
</style></head>
<body>${body}</body></html>`;
}
