import type { Attempt } from '../api/types';

const DAYS = ['Monday','Tuesday','Wednesday','Thursday','Friday','Saturday','Sunday'];
const SHORT_DAYS = ['Mon','Tue','Wed','Thu','Fri','Sat','Sun'];
const MONTHS = ['Jan','Feb','Mar','Apr','May','Jun','Jul','Aug','Sep','Oct','Nov','Dec'];

export function formatTargetDate(iso: string): string {
  // Treat as a local calendar date (no TZ shifting).
  const [y, m, d] = iso.split('-').map(Number);
  const date = new Date(y, m - 1, d);
  // JS getDay(): 0=Sun..6=Sat. Map to our Mon=0 ordering for short day lookup.
  const jsDow = date.getDay();
  const shortIdx = jsDow === 0 ? 6 : jsDow - 1;
  return `${SHORT_DAYS[shortIdx]} ${d} ${MONTHS[m - 1]}`;
}

export function formatDayOfWeek(dow: number): string {
  return `Every ${DAYS[dow] ?? '?'}`;
}

export function formatLastAttempt(attempts: Attempt[]): string {
  if (attempts.length === 0) return 'No attempts yet';
  const last = [...attempts].sort((a, b) => (a.ts < b.ts ? 1 : -1))[0];
  return `${relTime(last.ts)} · ${last.outcome}`;
}

function relTime(iso: string): string {
  const diffMs = Date.now() - new Date(iso).getTime();
  const mins = Math.round(diffMs / 60_000);
  if (mins < 1) return 'just now';
  if (mins < 60) return `${mins}m ago`;
  const hrs = Math.round(mins / 60);
  if (hrs < 48) return `${hrs}h ago`;
  return `${Math.round(hrs / 24)}d ago`;
}
