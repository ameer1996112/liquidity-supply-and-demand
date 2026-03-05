'use client';

import { useEffect, useRef, useState } from 'react';

interface AnimatedNumberProps {
  value: number;
  duration?: number;
  decimals?: number;
  prefix?: string;
  suffix?: string;
  className?: string;
  /** If true, shows + sign for positive numbers */
  signed?: boolean;
  /** Format function — overrides prefix/suffix/decimals */
  format?: (value: number) => string;
}

/**
 * Smoothly animates a number from its previous value to the new value.
 * Uses requestAnimationFrame for 60fps transitions.
 */
export function AnimatedNumber({
  value,
  duration = 600,
  decimals = 2,
  prefix = '',
  suffix = '',
  className,
  signed = false,
  format,
}: AnimatedNumberProps) {
  const [displayValue, setDisplayValue] = useState(value);
  const prevValueRef = useRef(value);
  const rafRef = useRef<number | null>(null);
  const startTimeRef = useRef<number | null>(null);

  useEffect(() => {
    const from = prevValueRef.current;
    const to = value;

    if (from === to) return;

    // Cancel any in-progress animation
    if (rafRef.current !== null) {
      cancelAnimationFrame(rafRef.current);
    }

    startTimeRef.current = null;

    const animate = (timestamp: number) => {
      if (startTimeRef.current === null) {
        startTimeRef.current = timestamp;
      }

      const elapsed = timestamp - startTimeRef.current;
      const progress = Math.min(elapsed / duration, 1);

      // Ease out cubic
      const eased = 1 - Math.pow(1 - progress, 3);
      const current = from + (to - from) * eased;

      setDisplayValue(current);

      if (progress < 1) {
        rafRef.current = requestAnimationFrame(animate);
      } else {
        setDisplayValue(to);
        prevValueRef.current = to;
        rafRef.current = null;
      }
    };

    rafRef.current = requestAnimationFrame(animate);
    prevValueRef.current = to;

    return () => {
      if (rafRef.current !== null) {
        cancelAnimationFrame(rafRef.current);
      }
    };
  }, [value, duration]);

  const formatted = format
    ? format(displayValue)
    : `${prefix}${signed && displayValue > 0 ? '+' : ''}${displayValue.toFixed(
        decimals
      )}${suffix}`;

  return <span className={className}>{formatted}</span>;
}

/**
 * Flash animation wrapper — briefly highlights a value when it changes.
 * Green flash for positive change, red flash for negative.
 */
interface FlashValueProps {
  value: number | null | undefined;
  children: React.ReactNode;
  className?: string;
}

export function FlashValue({ value, children, className }: FlashValueProps) {
  const prevRef = useRef(value);
  const [flashClass, setFlashClass] = useState('');

  useEffect(() => {
    if (value == null || prevRef.current == null) {
      prevRef.current = value;
      return;
    }

    if (value !== prevRef.current) {
      const isPositive = value > prevRef.current;
      const cls = isPositive ? 'flash-positive' : 'flash-negative';
      prevRef.current = value;

      // Use setTimeout to defer setState out of the synchronous effect body
      const applyTimer = setTimeout(() => setFlashClass(cls), 0);
      const clearTimer = setTimeout(() => setFlashClass(''), 800);
      return () => {
        clearTimeout(applyTimer);
        clearTimeout(clearTimer);
      };
    }
  }, [value]);

  return <span className={`${className ?? ''} ${flashClass}`}>{children}</span>;
}
