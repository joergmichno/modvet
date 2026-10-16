import type { ZoomDirection } from "@zenbu-labs/pixel";

export type { ZoomDirection };

export function zoomDirection(key: string): ZoomDirection | null {
  if (key === "=" || key === "+") return 1;
  if (key === "-" || key === "_") return -1;
  if (key === "0") return 0;
  return null;
}
