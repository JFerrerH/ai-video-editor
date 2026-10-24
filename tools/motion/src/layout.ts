import { useVideoConfig } from "remotion";

/** Frame sizes for the full-frame `Story` composition. The short side is always 1080,
 *  so pixel sizes written for one aspect read the same in another. */
export const ASPECTS = {
  "9:16": { width: 1080, height: 1920 }, // Reels / TikTok / Shorts
  "16:9": { width: 1920, height: 1080 }, // YouTube, decks, web
  "1:1": { width: 1080, height: 1080 }, // feed
  "4:5": { width: 1080, height: 1350 }, // feed (more height than 1:1)
} as const;
export type Aspect = keyof typeof ASPECTS;

export type Safe = { top: number; bottom: number; left: number; right: number };

/** Where readable content may go, per aspect.
 *  9:16 mirrors SAFE in theme.ts (IG header blur, bottom UI, right button rail).
 *  16:9 keeps clear of the YouTube progress bar / caption area at the bottom.
 *  Feed formats get an even title-safe margin. */
export const SAFE_BY_ASPECT: Record<Aspect, Safe> = {
  "9:16": { top: 290, bottom: 384, left: 130, right: 160 },
  "16:9": { top: 90, bottom: 120, left: 130, right: 130 },
  "1:1": { top: 90, bottom: 100, left: 90, right: 90 },
  "4:5": { top: 100, bottom: 120, left: 90, right: 90 },
};

export const aspectOf = (width: number, height: number): Aspect => {
  const r = width / height;
  if (r > 1.5) return "16:9";
  if (r > 0.95) return "1:1";
  if (r > 0.7) return "4:5";
  return "9:16";
};

/** Frame geometry for scene components: size, aspect, safe box and its inner width/height. */
export const useFrameLayout = () => {
  const { width, height } = useVideoConfig();
  const aspect = aspectOf(width, height);
  const safe = SAFE_BY_ASPECT[aspect];
  return {
    width,
    height,
    aspect,
    portrait: height > width,
    safe,
    innerW: width - safe.left - safe.right,
    innerH: height - safe.top - safe.bottom,
  };
};
