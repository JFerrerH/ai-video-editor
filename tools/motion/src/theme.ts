import { measureText } from "@remotion/layout-utils";
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

const rgbOf = (hex: string) => {
  const h = hex.replace("#", "");
  const full = h.length === 3 ? h.split("").map((c) => c + c).join("") : h.slice(0, 6);
  return [0, 2, 4].map((i) => parseInt(full.slice(i, i + 2), 16) / 255);
};

/** WCAG relative luminance of a hex colour. */
export const luminance = (hex: string) => {
  const [r, g, b] = rgbOf(hex).map((c) => (c <= 0.03928 ? c / 12.92 : ((c + 0.055) / 1.055) ** 2.4));
  return 0.2126 * r + 0.7152 * g + 0.0722 * b;
};

/** WCAG contrast ratio of two hex colours (1–21). */
export const contrast = (a: string, b: string) => {
  const [hi, lo] = [luminance(a), luminance(b)].sort((x, y) => y - x);
  return (hi + 0.05) / (lo + 0.05);
};

/** Text colour that reads on a solid `hex` fill: `ink` or white, whichever contrasts more with it (white on a
 *  dark/saturated fill, `ink` on a light one such as a lime or pale-yellow accent). */
export const textOn = (hex: string, ink: string) => (contrast(ink, hex) >= contrast("#FFFFFF", hex) ? ink : "#FFFFFF");

const toHsl = (hex: string): [number, number, number] => {
  const [r, g, b] = rgbOf(hex);
  const max = Math.max(r, g, b);
  const min = Math.min(r, g, b);
  const l = (max + min) / 2;
  if (max === min) return [0, 0, l];
  const d = max - min;
  const s = l > 0.5 ? d / (2 - max - min) : d / (max + min);
  const h = max === r ? (g - b) / d + (g < b ? 6 : 0) : max === g ? (b - r) / d + 2 : (r - g) / d + 4;
  return [h / 6, s, l];
};

const fromHsl = (h: number, s: number, l: number) => {
  const q = l < 0.5 ? l * (1 + s) : l + s - l * s;
  const p = 2 * l - q;
  const ch = (t: number) => {
    const u = t < 0 ? t + 1 : t > 1 ? t - 1 : t;
    const v = u < 1 / 6 ? p + (q - p) * 6 * u : u < 1 / 2 ? q : u < 2 / 3 ? p + (q - p) * (2 / 3 - u) * 6 : p;
    return Math.round(v * 255).toString(16).padStart(2, "0");
  };
  return `#${ch(h + 1 / 3)}${ch(h)}${ch(h - 1 / 3)}`;
};

/** The brand accent drawn as text, or as a text stamp's border, on a solid `fill`: the accent itself when it
 *  reaches `min` WCAG contrast there (3:1; pass 4.5 for text under 48 px), else the same hue stepped 5 % in
 *  lightness away from the fill (darker on a light fill, lighter on a dark one) until it does, else `ink`
 *  (white where ink doesn't read). Accent used as a fill behind text keeps `textOn` for the text. */
export const accentOn = (colors: Brand["colors"], fill: string, min = 3) => readable(colors.accent, fill, colors.ink, min);

/** Any brand colour (muted, a label grey) drawn as text on a solid `fill`: itself when it reaches `min` WCAG
 *  contrast, else the nearest shade of the same hue that does (`accentOn`'s steps), else `ink` or white. */
export const readable = (color: string, fill: string, ink: string, min = 4.5) => {
  if (contrast(color, fill) >= min) return color;
  const [h, s, l] = toHsl(color);
  const step = luminance(fill) > 0.18 ? -0.05 : 0.05;
  for (let x = l + step; x >= 0 && x <= 1; x += step) {
    const c = fromHsl(h, s, x);
    if (contrast(c, fill) >= min) return c;
  }
  return contrast(ink, fill) >= min ? ink : "#FFFFFF";
};

// the lightest part of the dark backdrop (its top glow, where headers sit): dark-tone text is measured on it
export const DARK_GLOW = "#3C4048";

/** The text colour for something drawn straight on the backdrop (no card of its own): ink on the light
 *  backdrop, the light tone on the dark one (`dark: true`), `overFootage` when there's no backdrop. */
export const onBackdrop = (colors: Brand["colors"], props: { full?: boolean; dark?: boolean }, overFootage: string) =>
  !props.full ? overFootage : props.dark ? "#F5F4F0" : colors.ink;

/** What an overlay event is drawn on: the brand backdrop (`full`, ink-coloured when `dark`) or the footage.
 *  Set per event by OverlayLayer; components read it with useBackdrop() for `onBackdrop`. */
export const BackdropContext = createContext<{ full?: boolean; dark?: boolean }>({});
export const useBackdrop = () => useContext(BackdropContext);

export const BrandContext = createContext<Brand>(defaultBrand);
export const useBrand = () => useContext(BrandContext);

/** The kit with its `muted` colour made to read (4.5:1) on the white cards and on the kit's own background: muted text
 *  (kickers, notes, line numbers) is still text a viewer reads. The kit's hue is kept; only its lightness moves. */
export const readableKit = (brand: Brand): Brand => {
  const c = brand.colors;
  const muted = readable(readable(c.muted, "#FFFFFF", c.ink), c.bg, c.ink);
  const tinted = readable(muted, c.tint1, c.ink);
  return muted === c.muted && tinted === c.muted ? brand : { ...brand, colors: { ...c, muted: tinted } };
};

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
  textBottom: 1536, // no text below this (tools/shortform.py SAFE_BOTTOM): the bottom UI and the caption shade
};

// The smallest text a component draws: the engine refuses text under 28 px (tools/shortform.py MIN_TEXT); 2 px more
// so rounding and a card's slight rotation never take it under.
export const MIN_TEXT = 30;
// the widest a card may be: the frame between the safe sides
export const SAFE_WIDTH = 1080 - 2 * SAFE.side;

/** The font size at which `text` fits `width` on one line, from `max` down to `min` (MIN_TEXT by default). Past
 *  `min` it stays at `min` and wraps by words (FIT_WRAP), so text never shrinks under what the engine accepts and
 *  never leaves its box sideways. Every component that sizes text to a box uses this, not its own numbers. */
export const fitSize = (
  text: string,
  o: { fontFamily: string; max: number; width: number; min?: number; fontWeight?: number | string; letterSpacing?: string },
) => {
  const min = Math.min(o.max, o.min ?? MIN_TEXT);
  const w = measureText({ text, fontFamily: o.fontFamily, fontSize: o.max, fontWeight: String(o.fontWeight ?? 400), letterSpacing: o.letterSpacing }).width;
  return Math.max(min, Math.min(o.max, Math.floor((o.max * o.width) / Math.max(1, w))));
};

/** Wrap by words, and break a word only when it alone is wider than its box: text stays inside it either way. */
export const FIT_WRAP = { overflowWrap: "anywhere", wordBreak: "normal" } as const;
