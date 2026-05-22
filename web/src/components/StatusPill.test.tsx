import { render, screen } from '@testing-library/react';
import { describe, expect, it } from 'vitest';
import { StatusPill } from './StatusPill';

describe('StatusPill', () => {
  it.each(['pending','booked','expired','disabled'] as const)('renders %s', (s) => {
    render(<StatusPill status={s} />);
    expect(screen.getByText(s.toUpperCase())).toBeInTheDocument();
  });
});
