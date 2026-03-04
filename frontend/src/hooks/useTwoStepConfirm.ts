import { useCallback, useEffect, useRef, useState } from 'react';

interface UseTwoStepConfirmOptions {
  /**
   * How long the button stays "armed" after the first click (ms).
   * Defaults to ~2.5 seconds to balance safety vs. flow.
   */
  timeoutMs?: number;
}

interface TwoStepConfirmState {
  /** Whether the control is currently armed awaiting a second click. */
  armed: boolean;
  /** Whole seconds remaining before the arming window expires. */
  secondsRemaining: number | null;
  /**
   * Call from your button onClick handler. First call arms,
   * second call within the window runs `onConfirm`.
   */
  requestConfirm: (onConfirm: () => void) => void;
  /** Manually reset the arming state (optional). */
  reset: () => void;
}

export function useTwoStepConfirm(
  options: UseTwoStepConfirmOptions = {},
): TwoStepConfirmState {
  const { timeoutMs = 2500 } = options;

  const [armed, setArmed] = useState(false);
  const [secondsRemaining, setSecondsRemaining] = useState<number | null>(null);
  const expiryRef = useRef<number | null>(null);
  const timerRef = useRef<number | null>(null);

  const clearTimer = useCallback(() => {
    if (timerRef.current != null) {
      window.clearInterval(timerRef.current);
      timerRef.current = null;
    }
  }, []);

  const reset = useCallback(() => {
    setArmed(false);
    setSecondsRemaining(null);
    expiryRef.current = null;
    clearTimer();
  }, [clearTimer]);

  const arm = useCallback(() => {
    const expiry = Date.now() + timeoutMs;
    expiryRef.current = expiry;
    setArmed(true);
    setSecondsRemaining(Math.ceil(timeoutMs / 1000));

    clearTimer();
    timerRef.current = window.setInterval(() => {
      if (expiryRef.current == null) {
        clearTimer();
        return;
      }
      const remainingMs = expiryRef.current - Date.now();
      if (remainingMs <= 0) {
        reset();
        return;
      }
      setSecondsRemaining(Math.max(1, Math.ceil(remainingMs / 1000)));
    }, 250);
  }, [clearTimer, reset, timeoutMs]);

  const requestConfirm = useCallback(
    (onConfirm: () => void) => {
      if (!armed) {
        arm();
        return;
      }
      reset();
      onConfirm();
    },
    [arm, armed, reset],
  );

  useEffect(() => {
    return () => {
      clearTimer();
    };
  }, [clearTimer]);

  return {
    armed,
    secondsRemaining,
    requestConfirm,
    reset,
  };
}

