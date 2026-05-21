import type { UseFormRegister, FieldErrors } from 'react-hook-form';

export function NotifyFields({
  register, errors,
}: {
  // eslint-disable-next-line @typescript-eslint/no-explicit-any
  register: UseFormRegister<any>;
  // eslint-disable-next-line @typescript-eslint/no-explicit-any
  errors: FieldErrors<any>;
}) {
  return (
    <fieldset className="space-y-2">
      <legend className="text-sm text-slate-300">Notify (optional)</legend>
      <div>
        <label className="text-xs text-slate-400" htmlFor="notify-to">To (E.164)</label>
        <input id="notify-to" {...register('notify.to')}
               placeholder="+14155551212"
               className="block w-full bg-slate-900 border border-slate-700 rounded px-2 py-1" />
        {/* eslint-disable-next-line @typescript-eslint/no-explicit-any */}
        {errors.notify && (errors.notify as any).to && (
          // eslint-disable-next-line @typescript-eslint/no-explicit-any
          <p className="text-xs text-red-400">{(errors.notify as any).to.message}</p>
        )}
      </div>
      <div>
        <label className="text-xs text-slate-400" htmlFor="notify-from">From (optional)</label>
        <input id="notify-from" {...register('notify.from')}
               className="block w-full bg-slate-900 border border-slate-700 rounded px-2 py-1" />
      </div>
    </fieldset>
  );
}
