import { usePartners } from '../hooks/usePartners';

export function PartnerPicker({
  value, onChange,
}: { value: string[]; onChange: (next: string[]) => void }) {
  const { data: partners = [], isLoading } = usePartners();
  const atCap = value.length >= 3;

  function toggle(id: string) {
    if (value.includes(id)) onChange(value.filter((x) => x !== id));
    else if (!atCap) onChange([...value, id]);
  }

  if (isLoading) return <p className="text-slate-400">Loading partners…</p>;
  if (partners.length === 0) {
    return <p className="text-slate-400 text-sm">No partners configured.</p>;
  }
  return (
    <fieldset className="grid grid-cols-2 gap-2">
      <legend className="text-sm text-slate-300 mb-1">Partners (max 3)</legend>
      {partners.map((p) => {
        const checked = value.includes(p.id);
        return (
          <label key={p.id} className="flex items-center gap-2 text-sm">
            <input
              type="checkbox"
              aria-label={p.name}
              checked={checked}
              disabled={!checked && atCap}
              onChange={() => toggle(p.id)}
            />
            {p.name}
          </label>
        );
      })}
    </fieldset>
  );
}
