import { useState } from 'react';
import { Link, useNavigate, useParams } from 'react-router-dom';
import { toast } from 'sonner';
import { ApiError } from '../api/client';
import { ConfirmDialog } from '../components/ConfirmDialog';
import { AttemptList } from '../components/AttemptList';
import { PartnerPicker } from '../components/PartnerPicker';
import { StatusPill } from '../components/StatusPill';
import { useDeleteWanted, usePatchWanted, useWanted } from '../hooks/useWanted';

export function WantedDetailPage() {
  const { id = '' } = useParams();
  const navigate = useNavigate();
  const { data: slot, isLoading } = useWanted(id);
  const patch = usePatchWanted(id);
  const del = useDeleteWanted();
  const [confirming, setConfirming] = useState(false);
  const [form, setForm] = useState<{
    start_time: string;
    end_time: string;
    num_slots: number;
    partners: string[];
  }>({ start_time: '', end_time: '', num_slots: 1, partners: [] });

  // Sync the editable form from the fetched slot without an effect: adjust
  // state during render, guarded by a previous-value check. This is React's
  // recommended pattern for deriving-and-then-editing state from props/data
  // (https://react.dev/learn/you-might-not-need-an-effect) and satisfies
  // eslint-plugin-react-hooks v7's `set-state-in-effect` rule, which flags
  // the previous `useEffect(() => setForm(...), [slot])` sync.
  const [syncedSlot, setSyncedSlot] = useState<typeof slot>(undefined);
  if (slot && slot !== syncedSlot) {
    setSyncedSlot(slot);
    setForm({
      start_time: slot.start_time,
      end_time: slot.end_time,
      num_slots: slot.num_slots,
      partners: slot.partners,
    });
  }

  if (isLoading || !slot) return <main className="p-6 text-slate-400">Loading…</main>;

  async function save() {
    try { await patch.mutateAsync(form); toast.success('Saved'); }
    catch (e) { toast.error(e instanceof ApiError ? e.detail : String(e)); }
  }

  async function toggleDisabled() {
    try {
      await patch.mutateAsync({ disabled: slot!.status !== 'disabled' });
    } catch (e) { toast.error(e instanceof ApiError ? e.detail : String(e)); }
  }

  async function confirmDelete() {
    try {
      await del.mutateAsync(slot!.id);
      toast.success('Deleted');
      navigate('/wanted');
    } catch (e) { toast.error(e instanceof ApiError ? e.detail : String(e)); }
  }

  return (
    <main className="max-w-5xl mx-auto p-6">
      <Link to="/wanted" className="text-sm text-slate-300 hover:text-slate-100 underline">
        ← Back to wanted tee-times
      </Link>

      <div className="mt-4 grid grid-cols-1 lg:grid-cols-2 gap-6">
        <section>
          <div className="flex items-center justify-between mb-3">
            <h1 className="text-xl font-semibold">Edit</h1>
            <StatusPill status={slot.status} />
          </div>
          <div className="space-y-3">
            <div className="grid grid-cols-2 gap-3">
              <label className="text-sm">Start
                <input type="time" value={form.start_time}
                       onChange={(e) => setForm({ ...form, start_time: e.target.value })}
                       className="block w-full bg-slate-900 border border-slate-700 rounded px-2 py-1" />
              </label>
              <label className="text-sm">End
                <input type="time" value={form.end_time}
                       onChange={(e) => setForm({ ...form, end_time: e.target.value })}
                       className="block w-full bg-slate-900 border border-slate-700 rounded px-2 py-1" />
              </label>
            </div>
            <label className="text-sm block">Slots
              <select value={form.num_slots}
                      onChange={(e) => setForm({ ...form, num_slots: Number(e.target.value) })}
                      className="block bg-slate-900 border border-slate-700 rounded px-2 py-1">
                <option value={1}>1</option><option value={2}>2</option>
                <option value={3}>3</option><option value={4}>4</option>
              </select>
            </label>
            <PartnerPicker
              value={form.partners}
              onChange={(partners) => setForm({ ...form, partners })}
            />
            <div className="flex gap-2">
              <button onClick={save} disabled={patch.isPending}
                      className="bg-blue-600 hover:bg-blue-500 text-white rounded px-3 py-1.5">
                Save
              </button>
              <button onClick={toggleDisabled}
                      className="bg-slate-700 hover:bg-slate-600 rounded px-3 py-1.5">
                {slot.status === 'disabled' ? 'Enable' : 'Disable'}
              </button>
              <button onClick={() => setConfirming(true)}
                      className="bg-red-700 hover:bg-red-600 text-white rounded px-3 py-1.5 ml-auto">
                Delete
              </button>
            </div>
          </div>
        </section>

        <section>
          <h2 className="text-xl font-semibold mb-3">Attempts</h2>
          <AttemptList attempts={slot.attempts} />
        </section>
      </div>

      <ConfirmDialog
        open={confirming}
        title="Delete this wanted slot?"
        body="This cannot be undone."
        confirmLabel="Confirm"
        onConfirm={confirmDelete}
        onCancel={() => setConfirming(false)}
      />
    </main>
  );
}
