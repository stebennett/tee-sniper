import { describe, expect, it } from 'vitest';
import { oneShotSchema, recurringSchema, loginSchema } from './schemas';

describe('schemas', () => {
  it('login requires non-empty username + pin', () => {
    expect(loginSchema.safeParse({ username: '', pin: 'x' }).success).toBe(false);
    expect(loginSchema.safeParse({ username: 'u', pin: 'p' }).success).toBe(true);
  });

  it('one-shot rejects end_time <= start_time', () => {
    const base = { target_date: '2026-05-25', start_time: '14:00', end_time: '14:00',
                   num_slots: 1, partners: [] };
    expect(oneShotSchema.safeParse(base).success).toBe(false);
  });

  it('one-shot accepts a valid window', () => {
    expect(oneShotSchema.safeParse({
      target_date: '2026-05-25', start_time: '14:00', end_time: '16:00',
      num_slots: 1, partners: [],
    }).success).toBe(true);
  });

  it('partners max length 3', () => {
    const base = { target_date: '2026-05-25', start_time: '14:00', end_time: '16:00',
                   num_slots: 1, partners: ['a','b','c','d'] };
    expect(oneShotSchema.safeParse(base).success).toBe(false);
  });

  it('recurring requires day_of_week 0..6', () => {
    const ok = { day_of_week: 0, start_time: '09:00', end_time: '11:00',
                 num_slots: 2, partners: [] };
    expect(recurringSchema.safeParse(ok).success).toBe(true);
    expect(recurringSchema.safeParse({ ...ok, day_of_week: 7 }).success).toBe(false);
  });
});
