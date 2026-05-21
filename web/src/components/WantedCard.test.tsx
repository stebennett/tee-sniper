import { render, screen } from '@testing-library/react';
import { describe, expect, it } from 'vitest';
import { MemoryRouter } from 'react-router-dom';
import { WantedCard } from './WantedCard';
import type { WantedResponse } from '../api/types';

const base: WantedResponse = {
  id: 'abc', kind: 'one_shot',
  target_date: '2026-05-23', day_of_week: null, end_date: null,
  start_time: '14:00', end_time: '16:30',
  num_slots: 4, partners: ['p1','p2'],
  has_credentials: true, notify: null,
  status: 'pending', attempts: [],
  created_at: '2026-05-19T00:00:00Z', updated_at: '2026-05-19T00:00:00Z',
};

describe('WantedCard', () => {
  it('renders one_shot title from target_date', () => {
    render(<MemoryRouter><WantedCard slot={base} /></MemoryRouter>);
    expect(screen.getByText(/Sat\b.+May/)).toBeInTheDocument();
    expect(screen.getByText('14:00–16:30 · 4 slots · 2 partners')).toBeInTheDocument();
    expect(screen.getByText('PENDING')).toBeInTheDocument();
    expect(screen.getByText('No attempts yet')).toBeInTheDocument();
  });

  it('renders recurring title from day_of_week', () => {
    render(<MemoryRouter><WantedCard slot={{
      ...base, kind: 'recurring', target_date: null, day_of_week: 6,
    }} /></MemoryRouter>);
    expect(screen.getByText('Every Sunday')).toBeInTheDocument();
  });
});
