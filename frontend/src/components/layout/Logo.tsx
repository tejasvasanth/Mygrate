import { brand } from '@/theme';

/** Wordmark — flat mark, no gradient or glow. */
export function Logo({ size = 30, showText = true }: { size?: number; showText?: boolean }) {
  return (
    <span style={{ display: 'inline-flex', alignItems: 'center', gap: 10 }}>
      <span
        style={{
          width: size,
          height: size,
          borderRadius: 6,
          background: brand.green700,
          display: 'inline-flex',
          alignItems: 'center',
          justifyContent: 'center',
          flexShrink: 0,
        }}
      >
        <svg
          width={size * 0.56}
          height={size * 0.56}
          viewBox="0 0 24 24"
          fill="none"
          aria-hidden="true"
        >
          <ellipse cx="12" cy="5.5" rx="7" ry="2.8" stroke="white" strokeWidth="1.8" />
          <path
            d="M5 5.5v6c0 1.55 3.13 2.8 7 2.8s7-1.25 7-2.8v-6"
            stroke="white"
            strokeWidth="1.8"
            strokeLinecap="round"
          />
          <path
            d="M5 11.5v6c0 1.55 3.13 2.8 7 2.8s7-1.25 7-2.8v-6"
            stroke="white"
            strokeWidth="1.8"
            strokeLinecap="round"
            opacity="0.65"
          />
        </svg>
      </span>
      {showText ? (
        <span
          style={{
            fontSize: size * 0.58,
            fontWeight: 600,
            letterSpacing: '-0.02em',
            color: brand.ink,
            fontFamily: "'Satoshi', sans-serif",
          }}
        >
          Migrate.ai
        </span>
      ) : null}
    </span>
  );
}
