import { levelMeta } from "../levels";

export interface LevelShapeProps {
  level: string | null | undefined;
  size?: number;
  /** Override the fill (defaults to the level's categorical hue). */
  color?: string;
}

/**
 * A small filled glyph whose **shape** encodes the administrative level — a non-colour cue so the
 * level stays distinguishable for colour-blind users and in greyscale. Shape + colour both come from
 * the `LEVELS` SSOT (`src/lib/levels.ts`). Ported from the `design/` export (`components.jsx`).
 */
export function LevelShape({ level, size = 12, color }: LevelShapeProps) {
  const meta = levelMeta(level);
  const fill = color ?? meta.color;
  const common = { width: size, height: size, viewBox: "0 0 12 12", "aria-hidden": true } as const;

  switch (meta.shape) {
    case "square":
      return (
        <svg {...common}>
          <rect x="1" y="1" width="10" height="10" rx="1" fill={fill} />
        </svg>
      );
    case "diamond":
      return (
        <svg {...common}>
          <rect x="2.5" y="2.5" width="7" height="7" transform="rotate(45 6 6)" fill={fill} />
        </svg>
      );
    case "triangle":
      return (
        <svg {...common}>
          <path d="M6 1l5 9.5H1z" fill={fill} />
        </svg>
      );
    case "circle":
    default:
      return (
        <svg {...common}>
          <circle cx="6" cy="6" r="5" fill={fill} />
        </svg>
      );
  }
}
