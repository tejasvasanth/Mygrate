import { cn } from '@/lib/utils';
import { AnimatedGridPattern } from '@/components/ui/animated-grid-pattern';

interface GridBackdropProps {
  className?: string;
  patternClassName?: string;
  numSquares?: number;
  maxOpacity?: number;
}

/** Quiet orthographic grid behind landing and app chrome. */
export function GridBackdrop({
  className,
  patternClassName,
  numSquares = 18,
  maxOpacity = 0.06,
}: GridBackdropProps) {
  return (
    <div
      aria-hidden="true"
      className={cn(
        'pointer-events-none fixed inset-0 z-0 overflow-hidden text-neutral-400/50',
        className,
      )}
    >
      <div className="absolute inset-0 bg-[#f7faf8]" />
      <AnimatedGridPattern
        width={48}
        height={48}
        numSquares={numSquares}
        maxOpacity={maxOpacity}
        duration={4}
        repeatDelay={1.2}
        className={cn(
          '[mask-image:linear-gradient(to_bottom,white_0%,transparent_85%)]',
          'inset-0 fill-neutral-400/15 stroke-neutral-400/20',
          patternClassName,
        )}
      />
    </div>
  );
}
