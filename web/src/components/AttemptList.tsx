import type { Attempt } from '../api/types';

export function AttemptList({ attempts }: { attempts: Attempt[] }) {
  if (attempts.length === 0) {
    return <p className="text-slate-400">No attempts yet.</p>;
  }
  const sorted = [...attempts].sort((a, b) => (a.ts < b.ts ? 1 : -1));
  return (
    <ul className="space-y-2">
      {sorted.map((a, i) => (
        <li key={i} className="border border-slate-800 rounded p-3">
          <div className="flex justify-between text-sm">
            <span>{new Date(a.ts).toLocaleString()}</span>
            <span className="font-mono">{a.outcome}</span>
          </div>
          {a.booking_id && (
            <div className="text-xs text-slate-400">booking: {a.booking_id}</div>
          )}
          {a.error && (
            <div className="text-xs text-red-400 mt-1">{a.error}</div>
          )}
        </li>
      ))}
    </ul>
  );
}
