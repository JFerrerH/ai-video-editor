import { createContext, useContext } from "react";

export type FontFile = {
  family: string;
  url: string; // path inside the --public-dir
  weight?: string;
  style?: "normal" | "italic";
};

export type Brand = {
  colors: {
    bg: string; // light page / card background
    tint1: string; // soft gradient tints on cutaway backdrops
    tint2: string;
    ink: string; // primary text
    muted: string;
    accent: string; // stamps, warnings
    success: string;
  };
  fonts: { serif: string; sans: string; mono: string };
  fontFiles: FontFile[];
};

// Neutral fallback (mirrors NEUTRAL in tools/brand.py); projects pass their
// brand via props, loaded from brands/<slug>/brand.json.
export const defaultBrand: Brand = {
  colors: {
    bg: "#F4F4F2",
    tint1: "#E4E4E0",
    tint2: "#D9DEE4",
    ink: "#1A1A1A",
    muted: "#6B6B6B",
    accent: "#D64545",
    success: "#2F7D5B",
  },
  fonts: { serif: "Georgia", sans: "Helvetica Neue", mono: "Menlo" },
  fontFiles: [],
};

export const BrandContext = createContext<Brand>(defaultBrand);
export const useBrand = () => useContext(BrandContext);

// Safe zones for 1080x1920 Reels/TikTok: keep content out of the top tabs,
// the bottom ~20% UI, the right-side buttons, and the caption band.
// top: Instagram blurs/overlays its header over the top ~14–15% (measured on a real Reels
// preview: the blur reaches ~270–300 px of the source), so nothing readable starts above 290.
export const SAFE = {
  top: 290,
  topBandBottom: 640, // overlays that sit above the speaker's head
  captionTop: 1170, // caption band ~1170–1300
  right: 160,
};
