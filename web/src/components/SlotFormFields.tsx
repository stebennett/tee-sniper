import { Controller, type Control, type UseFormRegister, type FieldErrors } from 'react-hook-form';
import { PartnerPicker } from './PartnerPicker';
import { NotifyFields } from './NotifyFields';

export function SlotFormFields({
  register, control, errors,
}: {
  // eslint-disable-next-line @typescript-eslint/no-explicit-any
  register: UseFormRegister<any>;
  // eslint-disable-next-line @typescript-eslint/no-explicit-any
  control: Control<any>;
  // eslint-disable-next-line @typescript-eslint/no-explicit-any
  errors: FieldErrors<any>;
}) {
  return (
    <>
      <div className="grid grid-cols-2 gap-3">
        <label className="text-sm">Start
          <input type="time" step={60} {...register('start_time')}
                 className="block w-full bg-slate-900 border border-slate-700 rounded px-2 py-1" />
        </label>
        <label className="text-sm">End
          <input type="time" step={60} {...register('end_time')}
                 className="block w-full bg-slate-900 border border-slate-700 rounded px-2 py-1" />
          {errors.end_time && (
            <p className="text-xs text-red-400">{String(errors.end_time.message)}</p>
          )}
        </label>
      </div>

      <label className="text-sm block">Slots
        <select {...register('num_slots', { valueAsNumber: true })}
                className="block bg-slate-900 border border-slate-700 rounded px-2 py-1">
          <option value={1}>1</option><option value={2}>2</option>
          <option value={3}>3</option><option value={4}>4</option>
        </select>
      </label>

      <Controller
        control={control}
        name="partners"
        render={({ field }) => (
          <PartnerPicker value={field.value ?? []} onChange={field.onChange} />
        )}
      />

      <NotifyFields register={register} errors={errors} />
    </>
  );
}
