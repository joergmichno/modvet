import { useState } from "react";
import { Box, Input, Text } from "@zenbu-labs/pixel";
import type { WebViewState } from "@zenbu-labs/pixel";
import { Icon } from "./icons";
import type { IconName } from "./icons";
import { mix, type Theme } from "./theme";
import type { ChromeActions, ChromeLayout, DownloadView, ToastView } from "./types";

export function FindBar({
  state,
  actions,
  layout,
  theme,
}: {
  state: WebViewState;
  actions: ChromeActions;
  layout: ChromeLayout;
  theme: Theme;
}) {
  const rem = layout.rem;
  const [text, setText] = useState("");
  const matches = state.findMatches;
  const count = matches ? `${matches.total ? matches.active : 0}/${matches.total}` : "";
  const change = (value: string) => {
    setText(value);
    actions.findChange(value);
  };
  return (
    <Box
      style={{
        position: "absolute",
        inset: { top: layout.toolbarHeight + rem * 0.45, right: rem * 0.75 },
        width: rem * 16,
        height: rem * 2,
        alignItems: "center",
        gap: rem * 0.2,
        padding: { left: rem * 0.6, right: rem * 0.3 },
        background: theme.overlay,
        cornerRadius: rem * 0.5,
        border: { width: 1, color: theme.fieldBorder },
      }}
    >
      <Input
        value={text}
        autoFocus
        style={{ flexGrow: 1, flexBasis: 0, wrap: false, fontSize: rem * 0.9 }}
        caretColor={theme.accent}
        selectionColor={theme.selection}
        onChange={change}
      />
      <Text style={{ color: theme.muted, fontSize: rem * 0.8, selectable: false }}>
        {count}
      </Text>
      <FindButton icon="back" rem={rem} theme={theme} onClick={() => actions.findNext(false)} />
      <FindButton icon="forward" rem={rem} theme={theme} onClick={() => actions.findNext(true)} />
      <FindButton icon="close" rem={rem} theme={theme} onClick={actions.findClose} />
    </Box>
  );
}

function FindButton({
  icon,
  rem,
  theme,
  onClick,
}: {
  icon: IconName;
  rem: number;
  theme: Theme;
  onClick(): void;
}) {
  return (
    <Box
      style={{
        width: rem * 1.2,
        height: rem * 1.2,
        alignItems: "center",
        justifyContent: "center",
        cornerRadius: rem * 0.25,
        hoverBackground: theme.hover,
        flexShrink: 0,
      }}
      onClick={onClick}
    >
      <Icon icon={icon} size={rem * 0.95} color={theme.muted} />
    </Box>
  );
}

export function DownloadHud({
  download,
  layout,
  theme,
}: {
  download: DownloadView;
  layout: ChromeLayout;
  theme: Theme;
}) {
  const rem = layout.rem;
  const status =
    download.state === "done"
      ? "saved"
      : download.state === "failed"
        ? "failed"
        : download.percent != null
          ? `${download.percent}%`
          : "downloading";
  return (
    <Box
      style={{
        position: "absolute",
        inset: { bottom: rem * 0.6, left: rem * 0.75 },
        height: rem * 2,
        alignItems: "center",
        gap: rem * 0.5,
        padding: { left: rem * 0.8, right: rem * 0.8 },
        background: theme.overlay,
        cornerRadius: rem * 0.5,
        border: { width: 1, color: theme.fieldBorder },
      }}
    >
      <Icon icon="download" size={rem * 0.95} color={theme.muted} />
      <Text style={{ fontSize: rem * 0.9, wrap: false, selectable: false }}>{download.name}</Text>
      <Text style={{ color: theme.muted, fontSize: rem * 0.8, wrap: false, selectable: false }}>
        {status}
      </Text>
    </Box>
  );
}

export function Toast({
  toast,
  layout,
  theme,
}: {
  toast: ToastView;
  layout: ChromeLayout;
  theme: Theme;
}) {
  const rem = layout.rem;
  const detailLines = toast.detail ? toast.detail.split("\n") : [];
  const action = toast.action;
  return (
    <Box
      style={{
        position: "absolute",
        inset: { top: layout.toolbarHeight + rem * 0.5, right: rem * 0.75 },
        flexDirection: "column",
        justifyContent: "center",
        gap: rem * 0.25,
        height:
          rem * (2 + (detailLines.length > 0 ? 0.3 + detailLines.length * 1.05 : 0) + (toast.action ? 1.7 : 0)),
        padding: { left: rem * 0.9, right: rem * 0.9 },
        background: toast.alert ? mix(theme.overlay, theme.red, 0.22) : theme.overlay,
        cornerRadius: rem * 0.5,
        border: { width: 1, color: toast.alert ? mix(theme.overlay, theme.red, 0.5) : theme.fieldBorder },
      }}
    >
      <Text
        style={{
          fontSize: detailLines.length > 0 ? rem : rem * 0.9,
          color: toast.failed ? [255, 143, 146, 255] : theme.fg,
          wrap: false,
          selectable: false,
        }}
      >
        {toast.text}
      </Text>
      {detailLines.map((line) => (
        <Text
          key={line}
          style={{
            fontSize: rem * 0.75,
            color: theme.muted,
            wrap: false,
            selectable: false,
          }}
        >
          {line}
        </Text>
      ))}
      {action && (
        <Box
          style={{
            height: rem * 1.4,
            alignItems: "center",
            justifyContent: "center",
            padding: { left: rem * 0.6, right: rem * 0.6 },
            cornerRadius: rem * 0.3,
            background: mix(theme.overlay, theme.accent, 0.25),
            hoverBackground: mix(theme.overlay, theme.accent, 0.45),
            flexShrink: 0,
          }}
          onClick={action.run}
        >
          <Text style={{ fontSize: rem * 0.8, color: theme.fg, wrap: false, selectable: false }}>
            {action.label}
          </Text>
        </Box>
      )}
    </Box>
  );
}

export function ZoomHud({
  factor,
  layout,
  theme,
  findOpen,
}: {
  factor: number;
  layout: ChromeLayout;
  theme: Theme;
  findOpen: boolean;
}) {
  const rem = layout.rem;
  return (
    <Box
      style={{
        position: "absolute",
        inset: {
          top: layout.toolbarHeight + rem * (findOpen ? 2.9 : 0.45),
          right: rem * 0.75,
        },
        height: rem * 2,
        alignItems: "center",
        padding: { left: rem * 0.8, right: rem * 0.8 },
        background: theme.overlay,
        cornerRadius: rem * 0.5,
        border: { width: 1, color: theme.fieldBorder },
      }}
    >
      <Text style={{ fontSize: rem * 0.9, wrap: false, selectable: false }}>
        {Math.round(factor * 100)}%
      </Text>
    </Box>
  );
}
