import { useEffect, useState } from "react";
import { Icon } from "../icons";
import type { Theme } from "../theme";
import { copy } from "./copy";

const COPIED_FLASH_MS = 1500;

export function useCopiedFlash(): [boolean, () => void] {
  const [copied, setCopied] = useState(0);
  useEffect(() => {
    if (!copied) return;
    const timer = setTimeout(() => setCopied(0), COPIED_FLASH_MS);
    return () => clearTimeout(timer);
  }, [copied]);
  return [copied > 0, () => setCopied(Date.now())];
}

export function CopyIcon({ copied, size, theme }: { copied: boolean; size: number; theme: Theme }) {
  return (
    <Icon
      icon={copied ? "check" : "copy"}
      size={size}
      color={copied ? theme.green : theme.muted}
      weight={copied ? 2.4 : 1.8}
    />
  );
}
