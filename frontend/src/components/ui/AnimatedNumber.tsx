import { useEffect, useRef, useState } from 'react';
import { useReducedMotion } from 'framer-motion';

interface Props {
  value: number;
  /** Formats the interpolated value for display. */
  format?: (value: number) => string;
  durationMs?: number;
}

/**
 * Counts from the previous value to the new one so live figures (rows
 * migrated, progress) change smoothly rather than snapping between renders.
 */
export function AnimatedNumber({ value, format = (v) => String(Math.round(v)), durationMs = 600 }: Props) {
  const reduced = useReducedMotion();
  const [display, setDisplay] = useState(value);
  const fromRef = useRef(value);
  const frameRef = useRef<number | undefined>(undefined);

  useEffect(() => {
    if (reduced) {
      setDisplay(value);
      return;
    }

    const from = fromRef.current;
    const to = value;
    if (from === to) return;

    const start = performance.now();

    const tick = (now: number) => {
      const t = Math.min(1, (now - start) / durationMs);
      // easeOutCubic — fast start, gentle landing.
      const eased = 1 - Math.pow(1 - t, 3);
      setDisplay(from + (to - from) * eased);

      if (t < 1) {
        frameRef.current = requestAnimationFrame(tick);
      } else {
        fromRef.current = to;
      }
    };

    frameRef.current = requestAnimationFrame(tick);

    return () => {
      if (frameRef.current !== undefined) cancelAnimationFrame(frameRef.current);
      fromRef.current = display;
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [value, durationMs, reduced]);

  return <>{format(display)}</>;
}
