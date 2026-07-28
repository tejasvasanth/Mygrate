import { useEffect, useRef, useState } from 'react';

/**
 * Circular score gauge, hand-rolled as SVG so the arc, the numeral and the
 * threshold colour stay in one place. Used by both the schema trust score and
 * the validation confidence score so the two read as the same instrument.
 */

export type GaugeTone = 'red' | 'amber' | 'green';

export const TONE_HEX: Record<GaugeTone, string> = {
  red: '#DC2626',
  amber: '#F59E0B',
  green: '#16A34A',
};

/** Shared threshold ladder. Trust score and confidence use different cuts. */
export function toneFor(score: number, amberAt: number, greenAt: number): GaugeTone {
  if (score >= greenAt) return 'green';
  if (score >= amberAt) return 'amber';
  return 'red';
}

/** Counts a value up once on mount — the gauge should feel like it measures. */
function useCountUp(target: number, ms = 900): number {
  const [value, setValue] = useState(0);
  const frame = useRef<number>(0);

  useEffect(() => {
    const reduce = window.matchMedia?.('(prefers-reduced-motion: reduce)').matches;
    if (reduce) {
      setValue(target);
      return;
    }
    const start = performance.now();
    const tick = (now: number) => {
      const t = Math.min(1, (now - start) / ms);
      // easeOutCubic — fast arrival, gentle settle.
      setValue(target * (1 - Math.pow(1 - t, 3)));
      if (t < 1) frame.current = requestAnimationFrame(tick);
    };
    frame.current = requestAnimationFrame(tick);
    return () => cancelAnimationFrame(frame.current);
  }, [target, ms]);

  return value;
}

export function ScoreGauge({
  score,
  tone,
  size = 180,
  suffix,
  caption,
  label,
}: {
  score: number;
  tone: GaugeTone;
  size?: number;
  /** Rendered small next to the numeral, e.g. "%" or "/100". */
  suffix?: string;
  /** Small line under the numeral, inside the dial. */
  caption?: string;
  /** Line under the whole dial. */
  label?: string;
}) {
  const animated = useCountUp(score);
  const color = TONE_HEX[tone];

  const stroke = size * 0.075;
  const radius = (size - stroke) / 2;
  const cx = size / 2;
  const cy = size / 2;
  // 270° dial, opening at the bottom — leaves room for the caption.
  const sweep = 0.75;
  const circumference = 2 * Math.PI * radius;
  const arc = circumference * sweep;
  const offset = arc * (1 - Math.min(100, Math.max(0, animated)) / 100);

  return (
    <div className="flex flex-col items-center gap-2">
      <div className="relative" style={{ width: size, height: size }}>
        <svg
          width={size}
          height={size}
          viewBox={`0 0 ${size} ${size}`}
          role="img"
          aria-label={`${label ?? 'Score'}: ${Math.round(score)}${suffix ?? ''}`}
          style={{ transform: 'rotate(135deg)' }}
        >
          <circle
            cx={cx}
            cy={cy}
            r={radius}
            fill="none"
            stroke="#E4EDE7"
            strokeWidth={stroke}
            strokeLinecap="round"
            strokeDasharray={`${arc} ${circumference}`}
          />
          <circle
            cx={cx}
            cy={cy}
            r={radius}
            fill="none"
            stroke={color}
            strokeWidth={stroke}
            strokeLinecap="round"
            strokeDasharray={`${arc} ${circumference}`}
            strokeDashoffset={offset}
            style={{ filter: `drop-shadow(0 0 6px ${color}33)` }}
          />
        </svg>
        <div className="absolute inset-0 flex flex-col items-center justify-center">
          <div className="flex items-baseline" style={{ color }}>
            <span
              className="font-bold tabular-nums leading-none"
              style={{ fontSize: size * 0.3, letterSpacing: '-0.03em' }}
            >
              {Math.round(animated)}
            </span>
            {suffix ? (
              <span className="font-semibold" style={{ fontSize: size * 0.11 }}>
                {suffix}
              </span>
            ) : null}
          </div>
          {caption ? (
            <span
              className="mt-1 text-[#7C8A83]"
              style={{ fontSize: Math.max(10, size * 0.062) }}
            >
              {caption}
            </span>
          ) : null}
        </div>
      </div>
      {label ? (
        <span className="text-sm font-semibold text-[#0F1B14]">{label}</span>
      ) : null}
    </div>
  );
}
