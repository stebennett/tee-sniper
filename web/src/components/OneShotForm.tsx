import { zodResolver } from '@hookform/resolvers/zod';
import { useForm } from 'react-hook-form';
import { SlotFormFields } from './SlotFormFields';
import { oneShotSchema, type OneShotForm as OneShotValues } from '../lib/schemas';

export type OneShotSubmit = OneShotValues;

const today = new Date().toISOString().slice(0, 10);
const plus7 = new Date(Date.now() + 7 * 86400_000).toISOString().slice(0, 10);

export function OneShotForm({ onSubmit, busy }: {
  onSubmit: (v: OneShotSubmit) => void; busy: boolean;
}) {
  const { register, handleSubmit, control, formState: { errors } } = useForm<OneShotValues>({
    resolver: zodResolver(oneShotSchema),
    defaultValues: { num_slots: 1, partners: [] },
  });
  return (
    <form onSubmit={handleSubmit(onSubmit)} className="space-y-3">
      <label className="text-sm block">Target date
        <input type="date" min={today} max={plus7}
               {...register('target_date')}
               className="block bg-slate-900 border border-slate-700 rounded px-2 py-1" />
        {errors.target_date && (
          <p className="text-xs text-red-400">{errors.target_date.message}</p>
        )}
      </label>
      <SlotFormFields register={register} control={control} errors={errors} />
      <button type="submit" disabled={busy}
              className="bg-blue-600 hover:bg-blue-500 text-white rounded px-3 py-2 disabled:opacity-50">
        {busy ? 'Creating…' : 'Create'}
      </button>
    </form>
  );
}
