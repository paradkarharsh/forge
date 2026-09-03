'use client';

import { useEffect, useState } from 'react';
import { formatDuration } from '../utils/formatters';

export function useElapsedTime(
  startedAt: string | null | undefined,
  completedAt: string | null | undefined,
  isActive: boolean
): { elapsedSeconds: number; formatted: string } {
  const [now, setNow] = useState(() => Date.now());

  useEffect(() => {
    if (!isActive || !startedAt || completedAt) {
      return;
    }

    const interval = setInterval(() => {
      setNow(Date.now());
    }, 1000);

    return () => clearInterval(interval);
  }, [isActive, startedAt, completedAt]);

  if (!startedAt) {
    return { elapsedSeconds: 0, formatted: '—' };
  }

  const startTime = new Date(startedAt).getTime();
  const endTime = completedAt ? new Date(completedAt).getTime() : now;
  const elapsedSeconds = Math.max(0, Math.floor((endTime - startTime) / 1000));

  return {
    elapsedSeconds,
    formatted: formatDuration(elapsedSeconds),
  };
}
