import { createContext, useContext } from "react";

export type FontFile = {
  family: string;
  url: string; // path inside the --public-dir
  weight?: string; // "400" or a variable font's range "100 800"; may arrive as a number in hand-written props
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
  // CSS lists: the Mac face, then the Noto face the Linux image ships
  fonts: {
    serif: 'Georgia, "Noto Serif", serif',
    sans: '"Helvetica Neue", "Noto Sans", sans-serif',
    mono: 'Menlo, "Noto Sans Mono", monospace',
  },
  fontFiles: [],
};

/** Text colour that reads on a solid `hex` fill: white on a dark/saturated fill, `ink` on a light one
 *  (a lime or pale-yellow accent). Uses WCAG relative luminance. */
export const textOn = (hex: string, ink: string) => {
  const h = hex.replace("#", "");
  const full = h.length === 3 ? h.split("").map((c) => c + c).join("") : h.slice(0, 6);
  const [r, g, b] = [0, 2, 4].map((i) => {
    const c = parseInt(full.slice(i, i + 2), 16) / 255;
    return c <= 0.03928 ? c / 12.92 : ((c + 0.055) / 1.055) ** 2.4;
  });
  return 0.2126 * r + 0.7152 * g + 0.0722 * b > 0.4 ? ink : "#FFFFFF";
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
  side: 130, // min margin from the left/right edges for cards and pills (IG crops ~30 px a side on phones)
};
