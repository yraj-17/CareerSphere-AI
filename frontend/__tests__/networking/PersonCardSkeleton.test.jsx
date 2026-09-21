/**
 * PersonCardSkeleton — Phase 5.4
 *
 * Tests:
 *  1. Renders without crashing
 *  2. Has expected data-testid
 *  3. Does not render any user data
 *  4. aria-hidden is set (skeleton is decorative)
 */

import React from 'react';
import { render, screen } from '@testing-library/react';
import PersonCardSkeleton from '@/components/networking/PersonCardSkeleton';

describe('PersonCardSkeleton', () => {
  test('1. renders without crashing', () => {
    const { container } = render(<PersonCardSkeleton />);
    expect(container.firstChild).toBeTruthy();
  });

  test('2. has data-testid="person-card-skeleton"', () => {
    render(<PersonCardSkeleton />);
    expect(screen.getByTestId('person-card-skeleton')).toBeInTheDocument();
  });

  test('3. does not render any visible text user content', () => {
    render(<PersonCardSkeleton />);
    // No names, usernames, headlines should appear
    expect(screen.queryByRole('heading')).not.toBeInTheDocument();
    expect(screen.queryByRole('button')).not.toBeInTheDocument();
  });

  test('4. aria-hidden is set so screen readers skip it', () => {
    render(<PersonCardSkeleton />);
    expect(screen.getByTestId('person-card-skeleton')).toHaveAttribute('aria-hidden', 'true');
  });
});
