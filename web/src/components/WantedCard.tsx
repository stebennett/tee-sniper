import { Link } from 'react-router-dom';
import type { WantedResponse } from '../api/types';
import { StatusPill } from './StatusPill';
import { formatDayOfWeek, formatLastAttempt, formatTargetDate } from '../lib/format';

export function WantedCard({ slot }: { slot: WantedResponse }) {
  const title =
    slot.kind === 'one_shot' && slot.target_date
      ? formatTargetDate(slot.target_date)
      : slot.day_of_week != null
        ? formatDayOfWeek(slot.day_of_week)
        : '—';

  return (
    <Link to={`/wanted/${slot.id}`}
          className={`block border border-slate-700 rounded-lg p-3 hover:border-slate-500
                      ${slot.status === 'disabled' ? 'opacity-60' : ''}`}>
      <div className="flex justify-between items-start">
        <strong>{title}</strong>
        <StatusPill status={slot.status} />
      </div>
      <div className="text-sm text-slate-300 mt-1">
        {slot.start_time}–{slot.end_time} · {slot.num_slots} slots
        {slot.partners.length > 0 && ` · ${slot.partners.length} partners`}
      </div>
      <div className="text-xs text-slate-400 mt-1">{formatLastAttempt(slot.attempts)}</div>
    </Link>
  );
}
