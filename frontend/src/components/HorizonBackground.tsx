import React, { useEffect, useRef } from 'react';

interface HorizonBackgroundProps {
  theme: 'light' | 'dark';
}

export const HorizonBackground: React.FC<HorizonBackgroundProps> = ({ theme }) => {
  const spotRef = useRef<HTMLDivElement>(null);
  const targetX = useRef<number>(0);
  const targetY = useRef<number>(0);
  const currentX = useRef<number>(0);
  const currentY = useRef<number>(0);
  const rafRef = useRef<number | null>(null);

  useEffect(() => {
    const mediaQueryReduceMotion = window.matchMedia('(prefers-reduced-motion: reduce)');
    const mediaQueryFine = window.matchMedia('(hover: hover) and (pointer: fine)');
    const mediaQueryReduceTransp = window.matchMedia('(prefers-reduced-transparency: reduce)');

    const shouldEnable = () => {
      if (mediaQueryReduceMotion.matches) return false;
      if (mediaQueryReduceTransp.matches) return false;
      if (!mediaQueryFine.matches) return false;
      return true;
    };

    if (!shouldEnable()) {
      if (rafRef.current !== null) {
        cancelAnimationFrame(rafRef.current);
        rafRef.current = null;
      }
      if (spotRef.current) {
        spotRef.current.style.removeProperty('--cursor-x');
        spotRef.current.style.removeProperty('--cursor-y');
      }
      return;
    }

    const initX = window.innerWidth / 2;
    const initY = window.innerHeight / 2;
    targetX.current = initX;
    targetY.current = initY;
    currentX.current = initX;
    currentY.current = initY;
    if (spotRef.current) {
      spotRef.current.style.setProperty('--cursor-x', `${initX}px`);
      spotRef.current.style.setProperty('--cursor-y', `${initY}px`);
    }

    const onMouseMove = (e: MouseEvent) => {
      targetX.current = e.clientX;
      targetY.current = e.clientY;
    };

    const loop = () => {
      const lerpFactor = 0.08;
      currentX.current += (targetX.current - currentX.current) * lerpFactor;
      currentY.current += (targetY.current - currentY.current) * lerpFactor;
      if (spotRef.current) {
        spotRef.current.style.setProperty('--cursor-x', `${currentX.current}px`);
        spotRef.current.style.setProperty('--cursor-y', `${currentY.current}px`);
      }
      rafRef.current = requestAnimationFrame(loop);
    };

    window.addEventListener('mousemove', onMouseMove, { passive: true });
    rafRef.current = requestAnimationFrame(loop);

    const onChange = () => {
      if (!shouldEnable()) {
        window.removeEventListener('mousemove', onMouseMove);
        if (rafRef.current !== null) {
          cancelAnimationFrame(rafRef.current);
          rafRef.current = null;
        }
        if (spotRef.current) {
          spotRef.current.style.removeProperty('--cursor-x');
          spotRef.current.style.removeProperty('--cursor-y');
        }
      } else if (rafRef.current === null) {
        window.addEventListener('mousemove', onMouseMove, { passive: true });
        rafRef.current = requestAnimationFrame(loop);
      }
    };

    mediaQueryReduceMotion.addEventListener?.('change', onChange);
    mediaQueryFine.addEventListener?.('change', onChange);
    mediaQueryReduceTransp.addEventListener?.('change', onChange);

    return () => {
      window.removeEventListener('mousemove', onMouseMove);
      if (rafRef.current !== null) {
        cancelAnimationFrame(rafRef.current);
        rafRef.current = null;
      }
      mediaQueryReduceMotion.removeEventListener?.('change', onChange);
      mediaQueryFine.removeEventListener?.('change', onChange);
      mediaQueryReduceTransp.removeEventListener?.('change', onChange);
    };
  }, []);

  return (
    <>
      <div className={`ambient-field ambient-${theme}`} aria-hidden="true">
        <span className="ambient-blob ambient-blob-a" />
        <span className="ambient-blob ambient-blob-b" />
        <span className="ambient-blob ambient-blob-c" />
        <span className="ambient-grain" />
      </div>
      <div ref={spotRef} className="ambient-cursor-spot" aria-hidden="true" />
    </>
  );
};

