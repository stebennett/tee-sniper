import { zodResolver } from '@hookform/resolvers/zod';
import { useForm } from 'react-hook-form';
import { SlotFormFields } from './SlotFormFields';
import { recurringSchema, type RecurringForm as RecurringValues } from '../lib/schemas';

const DAYS = ['Mon','Tue','Wed','Thu','Fri','Sat','Sun'];

export function RecurringForm({ onSubmit, busy }: {
  onSubmit: (v: RecurringValues) => void; busy: boolean;
}) {
  const { register, handleSubmit, control, formState: { errors } } = useForm<RecurringValues>({
    resolver: zodResolver(recurringSchema),
    defaultValues: { num_slots: 1, partners: [], day_of_week: 0 },
  });
  return (
    <form onSubmit={handleSubmit(onSubmit)} className="space-y-3">
      <label className="text-sm block">Day of week
        <select {...register('day_of_week', { valueAsNumber: true })}
                className="block bg-slate-900 border border-slate-700 rounded px-2 py-1">
          {DAYS.map((d, i) => <option key={i} value={i}>{d}</option>)}
        </select>
      </label>
      <label className="text-sm block">End date (optional)
        <input type="date" {...register('end_date')}
               className="block bg-slate-900 border border-slate-700 rounded px-2 py-1" />
      </label>
      <SlotFormFields register={register} control={control} errors={errors} />
      <button type="submit" disabled={busy}
              className="bg-blue-600 hover:bg-blue-500 text-white rounded px-3 py-2 disabled:opacity-50">
        {busy ? 'Creating…' : 'Create'}
      </button>
    </form>
  );
}
