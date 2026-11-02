import { BehindWord } from "./components/BehindWord";
import { CodePanel } from "./components/CodePanel";
import { DocCard } from "./components/DocCard";
import { Gauge } from "./components/Gauge";
import { Notice } from "./components/Notice";
import { PhonePanel } from "./components/PhonePanel";
import { StageDrawer } from "./components/StageDrawer";
import { Stickers } from "./components/Stickers";
import { Stuck } from "./components/Stuck";

/** The stage's own components (live-stage): drawn like overlay components, with `durationInFrames`, but also
 *  placeable on the `behind` and `panel` layers. Each has a <Name>.schema.json under components/. */
// eslint-disable-next-line @typescript-eslint/no-explicit-any -- props come from short.json events
export const STAGE: Record<string, React.FC<any>> = {
  Stickers,
  BehindWord,
  DocCard,
  StageDrawer,
  PhonePanel,
  CodePanel,
  Gauge,
  Stuck,
  Notice,
};
