import React from "react";
import { Checklist } from "./Checklist";
import { Counter, FunnelBars, Gauge, Stopwatch, TileGrid } from "./Numbers";
import { Badge, Stamp } from "./Stamp";
import { Terminal } from "./Terminal";

/** Cue-driven, aspect-aware widgets for BeatScene slots. Each takes `box` (its slot), `bg`, `at`,
 *  `out` plus its own props; times are seconds from the scene start. */
// eslint-disable-next-line @typescript-eslint/no-explicit-any -- props come from storyboard JSON
export const WIDGETS: Record<string, React.FC<any>> = {
  Terminal,
  Checklist,
  Stamp,
  Counter,
  Gauge,
  Stopwatch,
  FunnelBars,
  TileGrid,
  Badge,
};
