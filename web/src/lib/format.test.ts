import { describe, expect, it } from 'vitest';
import { formatTargetDate, formatDayOfWeek, formatLastAttempt } from './format';

describe('format helpers', () => {
  it('formats a target date as "Sat 24 May"', () => {
    expect(formatTargetDate('2026-05-23')).toMatch(/^Sat\b.+May$/);
  });

  it('formats day_of_week with Monday=0', () => {
    expect(formatDayOfWeek(0)).toBe('Every Monday');
    expect(formatDayOfWeek(6)).toBe('Every Sunday');
  });

  it('returns "No attempts yet" for empty array', () => {
    expect(formatLastAttempt([])).toBe('No attempts yet');
  });

  it('summarises the most recent attempt', () => {
    const a = [
      { ts: '2026-05-19T10:00:00Z', target_date: '2026-05-20',
        outcome: 'no_slots' as const, booking_id: null, error: null },
      { ts: '2026-05-19T12:00:00Z', target_date: '2026-05-20',
        outcome: 'booked' as const, booking_id: 'B1', error: null },
    ];
    expect(formatLastAttempt(a)).toMatch(/booked/);
  });
});
