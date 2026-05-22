import { useState } from 'react';
import { Link } from 'react-router-dom';
import { useAuth } from '../auth/useAuth';
import { useWantedList } from '../hooks/useWanted';
import { WantedCard } from '../components/WantedCard';
import type { WantedStatus } from '../api/types';

type Filter = 'all' | WantedStatus;
const FILTERS: { key: Filter; label: string }[] = [
  { key: 'all', label: 'All' },
  { key: 'pending', label: 'Pending' },
  { key: 'booked', label: 'Booked' },
  { key: 'disabled', label: 'Disabled' },
  { key: 'expired', label: 'Expired' },
];

export function WantedListPage() {
  const auth = useAuth();
  const { data: slots, isLoading, error } = useWantedList();
  const [filter, setFilter] = useState<Filter>('all');

  const filtered = (slots ?? []).filter((s) => filter === 'all' ? true : s.status === filter);

  return (
    <main className="max-w-5xl mx-auto p-6">
      <header className="flex items-center justify-between mb-4">
        <h1 className="text-2xl font-semibold">Wanted tee-times</h1>
        <div className="flex items-center gap-3 text-sm">
          <Link to="/wanted/new"
                className="bg-blue-600 hover:bg-blue-500 text-white rounded px-3 py-1.5">
            + New
          </Link>
          <span className="text-slate-400">Logged in as {auth.username}</span>
          <button onClick={() => auth.logout()} className="text-slate-300 underline">Logout</button>
        </div>
      </header>

      <div className="flex gap-2 mb-4">
        {FILTERS.map((f) => (
          <button key={f.key}
                  onClick={() => setFilter(f.key)}
                  className={`text-sm px-3 py-1 rounded-full border
                              ${filter === f.key
                                ? 'bg-slate-700 border-slate-500'
                                : 'border-slate-700 hover:border-slate-500'}`}>
            {f.label}
          </button>
        ))}
      </div>

      {isLoading && <p className="text-slate-400">Loading…</p>}
      {error && <p className="text-red-400">Failed to load wanted slots.</p>}
      {!isLoading && filtered.length === 0 && (
        <p className="text-slate-400">No wanted slots match this filter.</p>
      )}

      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-3">
        {filtered.map((s) => <WantedCard key={s.id} slot={s} />)}
      </div>
    </main>
  );
}
