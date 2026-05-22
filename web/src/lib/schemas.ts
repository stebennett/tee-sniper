import { z } from 'zod';

const HHMM = /^\d{2}:\d{2}$/;
const YMD  = /^\d{4}-\d{2}-\d{2}$/;
const E164 = /^\+[1-9]\d{1,14}$/;

export const loginSchema = z.object({
  username: z.string().min(1, 'Username required'),
  pin:      z.string().min(1, 'PIN required'),
});

const notifySchema = z.preprocess(
  (v) => {
    if (v && typeof v === 'object' && (v as Record<string, unknown>).to === '') return undefined;
    return v;
  },
  z.object({
    to:   z.string().regex(E164, 'Must be E.164, e.g. +14155551212'),
    from: z.string().regex(E164).optional().or(z.literal('').transform(() => undefined)),
  }).optional(),
);

const commonShape = {
  start_time: z.string().regex(HHMM),
  end_time:   z.string().regex(HHMM),
  num_slots:  z.number().int().min(1).max(4),
  partners:   z.array(z.string()).max(3),
  notify:     notifySchema,
};

function refineWindow<T extends { start_time: string; end_time: string }>(s: z.ZodType<T>) {
  return s.refine((v) => v.end_time > v.start_time, {
    message: 'End time must be after start time', path: ['end_time'],
  });
}

export const oneShotSchema = refineWindow(
  z.object({ target_date: z.string().regex(YMD), ...commonShape }),
);

export const recurringSchema = refineWindow(
  z.object({
    day_of_week: z.number().int().min(0).max(6),
    end_date: z.string().regex(YMD).optional().or(z.literal('').transform(() => undefined)),
    ...commonShape,
  }),
);

export type LoginForm     = z.infer<typeof loginSchema>;
export type OneShotForm   = z.infer<typeof oneShotSchema>;
export type RecurringForm = z.infer<typeof recurringSchema>;
