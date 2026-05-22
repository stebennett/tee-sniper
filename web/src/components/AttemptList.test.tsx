import { render, screen } from '@testing-library/react';
import { describe, expect, it } from 'vitest';
import { AttemptList } from './AttemptList';

describe('AttemptList', () => {
  it('shows empty state', () => {
    render(<AttemptList attempts={[]} />);
    expect(screen.getByText('No attempts yet.')).toBeInTheDocument();
  });

  it('renders newest first with outcome + error', () => {
    render(<AttemptList attempts={[
      { ts: '2026-05-19T10:00:00Z', target_date: '2026-05-20',
        outcome: 'no_slots', booking_id: null, error: null },
      { ts: '2026-05-19T12:00:00Z', target_date: '2026-05-20',
        outcome: 'booking_failed', booking_id: null, error: 'partner unknown' },
    ]} />);
    const rows = screen.getAllByRole('listitem');
    expect(rows[0]).toHaveTextContent('booking_failed');
    expect(rows[0]).toHaveTextContent('partner unknown');
  });
});
