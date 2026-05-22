import type { WantedStatus } from '../api/types';

const COLORS: Record<WantedStatus, string> = {
  pending:  'bg-blue-600 text-white',
  booked:   'bg-green-600 text-white',
  expired:  'bg-amber-600 text-white',
  disabled: 'bg-slate-600 text-slate-200',
};

export function StatusPill({ status }: { status: WantedStatus }) {
  return (
    <span className={`text-[11px] px-2 py-0.5 rounded-full ${COLORS[status]}`}>
      {status.toUpperCase()}
    </span>
  );
}
