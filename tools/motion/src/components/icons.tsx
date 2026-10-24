import React from "react";

/** Drawn line icons (24-unit grid, stroke only) — use these instead of emoji in graphics. */
export type IconKind =
  | "speech"
  | "bulb"
  | "mail"
  | "receipt"
  | "calendar"
  | "search"
  | "person"
  | "check"
  | "spark"
  | "send"
  | "chart"
  | "cv"
  | "plane"
  | "book"
  | "cart"
  | "heart"
  | "brain"
  | "moon";

const PATHS: Record<IconKind, React.ReactNode> = {
  speech: <path d="M4 5h16v11H9l-5 4z" />,
  bulb: (
    <>
      <path d="M9 18h6M10 21h4" />
      <path d="M12 3a6 6 0 0 0-3.5 10.9c.9.7 1.5 1.6 1.5 2.6V17h4v-.5c0-1 .6-1.9 1.5-2.6A6 6 0 0 0 12 3z" />
    </>
  ),
  mail: (
    <>
      <rect x="3" y="5" width="18" height="14" rx="2" />
      <path d="M3.5 6.5 12 13l8.5-6.5" />
    </>
  ),
  receipt: (
    <>
      <path d="M6 3h12v18l-3-2-3 2-3-2-3 2z" />
      <path d="M9 8h6M9 12h6M9 16h3" />
    </>
  ),
  calendar: (
    <>
      <rect x="3" y="5" width="18" height="16" rx="2" />
      <path d="M3 10h18M8 3v4M16 3v4" />
    </>
  ),
  search: (
    <>
      <circle cx="11" cy="11" r="6.5" />
      <path d="m16 16 4.5 4.5" />
    </>
  ),
  person: (
    <>
      <circle cx="12" cy="7.5" r="3.8" />
      <path d="M4.5 21c.6-4.2 3.6-6.8 7.5-6.8s6.9 2.6 7.5 6.8" />
    </>
  ),
  check: <path d="m5 12.5 4.5 4.5L19 7.5" />,
  spark: <path d="M12 3c.6 4.6 2.4 6.4 7 7-4.6.6-6.4 2.4-7 7-.6-4.6-2.4-6.4-7-7 4.6-.6 6.4-2.4 7-7z" />,
  send: <path d="M21 3 3 10.5l7 2.5 2.5 7zM10 13l5-5" />,
  chart: (
    <>
      <path d="M4 20h16" />
      <path d="M7 16v-4M12 16V7M17 16v-6" />
    </>
  ),
  cv: (
    <>
      <rect x="5" y="3" width="14" height="18" rx="2" />
      <circle cx="12" cy="9" r="2.2" />
      <path d="M8.5 15h7M9.5 18h5" />
    </>
  ),
  plane: <path d="M3 13.5 21 6l-4.5 13-4-5.2zM12.5 13.8 21 6" />,
  book: (
    <>
      <path d="M12 6.5C10 5 7 4.5 3.5 5v13c3.5-.5 6.5 0 8.5 1.5 2-1.5 5-2 8.5-1.5V5C17 4.5 14 5 12 6.5z" />
      <path d="M12 6.5v13" />
    </>
  ),
  cart: (
    <>
      <path d="M3 4h2.5l2.2 10.5h10.6L20.5 7H6.4" />
      <circle cx="9" cy="19" r="1.4" />
      <circle cx="17" cy="19" r="1.4" />
    </>
  ),
  heart: <path d="M12 20s-7.5-4.6-7.5-10.2A4.3 4.3 0 0 1 12 7.2a4.3 4.3 0 0 1 7.5 2.6C19.5 15.4 12 20 12 20z" />,
  brain: (
    <>
      <path d="M12 5.5a3 3 0 0 0-5.6-.9A3.2 3.2 0 0 0 4 9.6a3.4 3.4 0 0 0 .9 5.6A3.3 3.3 0 0 0 9 19.4a3 3 0 0 0 3-1.4z" />
      <path d="M12 5.5a3 3 0 0 1 5.6-.9 3.2 3.2 0 0 1 2.4 5 3.4 3.4 0 0 1-.9 5.6 3.3 3.3 0 0 1-4.1 4.2 3 3 0 0 1-3-1.4z" />
      <path d="M12 5.5V18M8 10.5c1.2 0 2 .8 2 2M16 10.5c-1.2 0-2 .8-2 2" />
    </>
  ),
  moon: <path d="M19.5 14.5A8 8 0 0 1 9.5 4.5a8 8 0 1 0 10 10z" />,
};

export const LineIcon: React.FC<{ kind: IconKind; size?: number; color: string; stroke?: number; fill?: string }> = ({
  kind,
  size = 48,
  color,
  stroke = 1.8,
  fill = "none",
}) => (
  <svg width={size} height={size} viewBox="0 0 24 24" fill={fill} stroke={color} strokeWidth={stroke} strokeLinecap="round" strokeLinejoin="round">
    {PATHS[kind]}
  </svg>
);
