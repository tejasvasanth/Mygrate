import type { ReactNode } from 'react';
import { motion, useReducedMotion, type Variants } from 'framer-motion';

/**
 * Shared motion vocabulary. Everything is short (<= 400ms), low-travel
 * (<= 12px) and eased out, so movement reads as settling rather than sliding.
 * All helpers collapse to no motion when the OS requests reduced motion.
 */

const EASE = [0.22, 1, 0.36, 1] as const;

export const fadeUp: Variants = {
  hidden: { opacity: 0, y: 10 },
  show: { opacity: 1, y: 0, transition: { duration: 0.36, ease: EASE } },
};

/** Parent that releases children one after another. */
export const stagger: Variants = {
  hidden: {},
  show: { transition: { staggerChildren: 0.06, delayChildren: 0.04 } },
};

/** Fades and lifts content in once, on mount. */
export function Reveal({
  children,
  delay = 0,
  className,
}: {
  children: ReactNode;
  delay?: number;
  className?: string;
}) {
  const reduced = useReducedMotion();

  return (
    <motion.div
      className={className}
      initial={reduced ? false : { opacity: 0, y: 10 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ duration: 0.36, ease: EASE, delay }}
    >
      {children}
    </motion.div>
  );
}

/** Wraps a route so page changes cross-fade instead of snapping. */
export function PageTransition({ children }: { children: ReactNode }) {
  const reduced = useReducedMotion();

  return (
    <motion.div
      initial={reduced ? false : { opacity: 0, y: 8 }}
      animate={{ opacity: 1, y: 0 }}
      exit={{ opacity: 0, y: -4 }}
      transition={{ duration: 0.28, ease: EASE }}
    >
      {children}
    </motion.div>
  );
}

/** Container + item pair for lists that should cascade in. */
export function StaggerList({ children, className }: { children: ReactNode; className?: string }) {
  const reduced = useReducedMotion();

  return (
    <motion.div
      className={className}
      variants={stagger}
      initial={reduced ? false : 'hidden'}
      animate="show"
    >
      {children}
    </motion.div>
  );
}

export function StaggerItem({ children, className }: { children: ReactNode; className?: string }) {
  return (
    <motion.div className={className} variants={fadeUp}>
      {children}
    </motion.div>
  );
}

export { motion };
