import React from "react";
import { BarChart } from "./BarChart";
import { ImageScene } from "./ImageScene";
import { KineticType } from "./KineticType";
import { ListScene } from "./ListScene";
import { StatScene } from "./StatScene";
import { TitleCard } from "./TitleCard";

/** Full-frame scene primitives: aspect-aware (9:16, 16:9, 1:1, 4:5), drawn on a `Bg` tone.
 *  Usable as `Story` scenes and as overlay events. */
// eslint-disable-next-line @typescript-eslint/no-explicit-any -- props come from storyboard JSON
export const SCENES: Record<string, React.FC<any>> = {
  TitleCard,
  KineticType,
  StatScene,
  BarChart,
  ListScene,
  ImageScene,
};
