/**
 * DiscoverPeoplePage tests — Phase 5.4
 *
 * Tests:
 *  1.  Discover page renders without crashing
 *  2.  Shows skeleton cards while loading
 *  3.  Renders user cards after data loads
 *  4.  Current user is excluded (data from API doesn't include self — backend
 *      responsibility; we verify our component renders only what the API returns)
 *  5.  Search input calls getNetworkingUsers with correct query after debounce
 *  6.  Empty query resets to default list (empty q param)
 *  7.  Load More button is visible when there are more results
 *  8.  Load More appends users (does not replace them)
 *  9.  Load More hides when all results shown
 * 10.  Connect button calls sendConnectionRequest with correct userId
 * 11.  After successful connect, button changes to Pending
 * 12.  API error shows error state with Try Again button
 * 13.  Try Again retries the fetch
 * 14.  Empty API result shows empty state
 * 15.  Sensitive fields (email, password) are not rendered
 */

import React from 'react';
import { render, screen, fireEvent, waitFor, act } from '@testing-library/react';
import userEvent from '@testing-library/user-event';

// ─── Mock next/link ────────────────────────────────────────────────────────────
jest.mock('next/link', () => {
  const Link = ({ children, href, ...props }) => (
    <a href={href} {...props}>{children}</a>
  );
  Link.displayName = 'MockLink';
  return Link;
});

// ─── Mock framer-motion ────────────────────────────────────────────────────────
jest.mock('framer-motion', () => ({
  motion: {
    article: ({ children, ...props }) => {
      const { initial, animate, transition, ...rest } = props;
      return <article {...rest}>{children}</article>;
    },
    div: ({ children, ...props }) => {
      const { initial, animate, transition, exit, ...rest } = props;
      return <div {...rest}>{children}</div>;
    },
  },
  AnimatePresence: ({ children }) => <>{children}</>,
}));

// ─── Mock useDebounce — return value immediately (no delay in tests) ──────────
jest.mock('@/hooks/useDebounce', () => ({
  useDebounce: (value) => value,
}));

// ─── Mock API service ──────────────────────────────────────────────────────────
jest.mock('@/services/api', () => ({
  getNetworkingUsers: jest.fn(),
  sendConnectionRequest: jest.fn(),
  extractErrorMessage: jest.fn((err) => err?.message || 'An error occurred.'),
}));

import { getNetworkingUsers, sendConnectionRequest } from '@/services/api';
import DiscoverPeoplePage from '@/components/networking/DiscoverPeoplePage';

// ─── Helpers ───────────────────────────────────────────────────────────────────

const makeUser = (id, overrides = {}) => ({
  id,
  username: `user_${id}`,
  first_name: 'Test',
  last_name: `User${id}`,
  headline: `Engineer ${id}`,
  location: 'Mumbai',
  profile_photo_url: null,
  connection_status: 'none',
  ...overrides,
});

const PAGE_RESPONSE = (users, total) => ({
  users,
  total: total ?? users.length,
  limit: 20,
  offset: 0,
});

// ─── Tests ─────────────────────────────────────────────────────────────────────

describe('DiscoverPeoplePage', () => {
  beforeEach(() => {
    jest.clearAllMocks();
  });

  // ── 1. Renders without crashing ──────────────────────────────────────────────
  test('1. renders without crashing', async () => {
    getNetworkingUsers.mockResolvedValue(PAGE_RESPONSE([]));
    await act(async () => { render(<DiscoverPeoplePage />); });
    expect(screen.getByText('Discover People')).toBeInTheDocument();
  });

  // ── 2. Shows skeleton cards while loading ────────────────────────────────────
  test('2. shows skeleton cards while loading', async () => {
    // Never resolve so we stay in loading state
    getNetworkingUsers.mockReturnValue(new Promise(() => {}));
    render(<DiscoverPeoplePage />);
    expect(screen.getByTestId('skeleton-grid')).toBeInTheDocument();
    const skeletons = screen.getAllByTestId('person-card-skeleton');
    expect(skeletons.length).toBeGreaterThanOrEqual(3);
  });

  // ── 3. Renders user cards after data loads ───────────────────────────────────
  test('3. renders user cards after data loads', async () => {
    const users = [makeUser('a'), makeUser('b'), makeUser('c')];
    getNetworkingUsers.mockResolvedValue(PAGE_RESPONSE(users));

    await act(async () => { render(<DiscoverPeoplePage />); });

    await waitFor(() => {
      expect(screen.getByTestId('people-grid')).toBeInTheDocument();
    });
    const cards = screen.getAllByTestId('person-card');
    expect(cards).toHaveLength(3);
  });

  // ── 4. Rendered users match exactly what the API returned (no self-injection) ─
  test('4. only renders users returned by the API', async () => {
    const users = [makeUser('x1'), makeUser('x2')];
    getNetworkingUsers.mockResolvedValue(PAGE_RESPONSE(users));

    await act(async () => { render(<DiscoverPeoplePage />); });
    await waitFor(() => screen.getByTestId('people-grid'));

    const cards = screen.getAllByTestId('person-card');
    expect(cards).toHaveLength(2);
  });

  // ── 5. Search input calls API with correct query ─────────────────────────────
  test('5. typing in search calls getNetworkingUsers with q param', async () => {
    getNetworkingUsers.mockResolvedValue(PAGE_RESPONSE([]));
    await act(async () => { render(<DiscoverPeoplePage />); });

    const input = screen.getByTestId('search-input');
    await act(async () => {
      fireEvent.change(input, { target: { value: 'alice' } });
    });

    await waitFor(() => {
      expect(getNetworkingUsers).toHaveBeenCalledWith(
        expect.objectContaining({ q: 'alice', offset: 0 })
      );
    });
  });

  // ── 6. Empty query calls API without q (or empty q) ─────────────────────────
  test('6. clearing search calls API without q param', async () => {
    getNetworkingUsers.mockResolvedValue(PAGE_RESPONSE([]));
    await act(async () => { render(<DiscoverPeoplePage />); });

    const input = screen.getByTestId('search-input');
    // type then clear
    await act(async () => { fireEvent.change(input, { target: { value: 'bob' } }); });
    await act(async () => { fireEvent.change(input, { target: { value: '' } }); });

    await waitFor(() => {
      const calls = getNetworkingUsers.mock.calls;
      const lastCall = calls[calls.length - 1][0];
      // q should be absent or empty when input is cleared
      expect(!lastCall.q || lastCall.q === '').toBe(true);
    });
  });

  // ── 7. Load More button visible when hasMore ─────────────────────────────────
  test('7. Load More button shown when total > returned count', async () => {
    const users = Array.from({ length: 20 }, (_, i) => makeUser(`u${i}`));
    getNetworkingUsers.mockResolvedValue({ ...PAGE_RESPONSE(users, 45) });

    await act(async () => { render(<DiscoverPeoplePage />); });
    await waitFor(() => screen.getByTestId('load-more-btn'));
    expect(screen.getByTestId('load-more-btn')).toBeInTheDocument();
  });

  // ── 8. Load More appends users ───────────────────────────────────────────────
  test('8. clicking Load More appends additional users', async () => {
    const page1 = Array.from({ length: 20 }, (_, i) => makeUser(`p1u${i}`));
    const page2 = Array.from({ length: 5 }, (_, i) => makeUser(`p2u${i}`));

    getNetworkingUsers
      .mockResolvedValueOnce({ users: page1, total: 25, limit: 20, offset: 0 })
      .mockResolvedValueOnce({ users: page2, total: 25, limit: 20, offset: 20 });

    await act(async () => { render(<DiscoverPeoplePage />); });
    await waitFor(() => screen.getByTestId('load-more-btn'));

    await act(async () => {
      fireEvent.click(screen.getByTestId('load-more-btn'));
    });

    await waitFor(() => {
      const cards = screen.getAllByTestId('person-card');
      expect(cards).toHaveLength(25);
    });
  });

  // ── 9. Load More hidden when all results shown ───────────────────────────────
  test('9. Load More is hidden when all users are shown', async () => {
    const users = [makeUser('a'), makeUser('b')];
    getNetworkingUsers.mockResolvedValue(PAGE_RESPONSE(users, 2));

    await act(async () => { render(<DiscoverPeoplePage />); });
    await waitFor(() => screen.getByTestId('end-of-list'));

    expect(screen.queryByTestId('load-more-btn')).not.toBeInTheDocument();
  });

  // ── 10. Connect calls sendConnectionRequest with userId ──────────────────────
  test('10. clicking Connect calls sendConnectionRequest with the user id', async () => {
    const user = makeUser('target-42');
    getNetworkingUsers.mockResolvedValue(PAGE_RESPONSE([user]));
    sendConnectionRequest.mockResolvedValue({ id: 'conn-1', status: 'pending' });

    await act(async () => { render(<DiscoverPeoplePage />); });
    await waitFor(() => screen.getByTestId('people-grid'));

    await act(async () => {
      fireEvent.click(screen.getByRole('button', { name: /connect with test usertarget-42/i }));
    });

    expect(sendConnectionRequest).toHaveBeenCalledWith('target-42');
  });

  // ── 11. After successful connect, button changes to Pending ──────────────────
  test('11. after successful connect, connection_status becomes pending', async () => {
    const user = makeUser('abc');
    getNetworkingUsers.mockResolvedValue(PAGE_RESPONSE([user]));
    sendConnectionRequest.mockResolvedValue({ id: 'c1', status: 'pending' });

    await act(async () => { render(<DiscoverPeoplePage />); });
    await waitFor(() => screen.getByTestId('people-grid'));

    await act(async () => {
      fireEvent.click(screen.getByRole('button', { name: /connect with test userabc/i }));
    });

    await waitFor(() => {
      // After success the optimistic update turns it to pending
      expect(screen.getByRole('button', { name: /pending/i })).toBeDisabled();
    });
  });

  // ── 12. API error shows error state ──────────────────────────────────────────
  test('12. API error shows error state and Try Again button', async () => {
    const err = new Error('Network failure');
    getNetworkingUsers.mockRejectedValue(err);

    await act(async () => { render(<DiscoverPeoplePage />); });
    await waitFor(() => screen.getByTestId('error-state'));

    expect(screen.getByText(/failed to load people/i)).toBeInTheDocument();
    expect(screen.getByRole('button', { name: /try again/i })).toBeInTheDocument();
  });

  // ── 13. Try Again retries the fetch ──────────────────────────────────────────
  test('13. clicking Try Again retries getNetworkingUsers', async () => {
    const err = new Error('Server error');
    getNetworkingUsers
      .mockRejectedValueOnce(err)
      .mockResolvedValue(PAGE_RESPONSE([]));

    await act(async () => { render(<DiscoverPeoplePage />); });
    await waitFor(() => screen.getByTestId('error-state'));

    await act(async () => {
      fireEvent.click(screen.getByRole('button', { name: /try again/i }));
    });

    await waitFor(() => {
      expect(getNetworkingUsers).toHaveBeenCalledTimes(2);
    });
  });

  // ── 14. Empty API result shows empty state ───────────────────────────────────
  test('14. empty result shows empty state message', async () => {
    getNetworkingUsers.mockResolvedValue(PAGE_RESPONSE([]));

    await act(async () => { render(<DiscoverPeoplePage />); });
    await waitFor(() => screen.getByTestId('empty-state'));

    expect(screen.getByTestId('empty-state')).toBeInTheDocument();
  });

  // ── 15. Sensitive fields not rendered ────────────────────────────────────────
  test('15. sensitive fields from API response are not rendered', async () => {
    const user = {
      ...makeUser('z'),
      email: 'secret@example.com',
      password_hash: 'bcrypt-hash-should-never-show',
    };
    getNetworkingUsers.mockResolvedValue(PAGE_RESPONSE([user]));

    await act(async () => { render(<DiscoverPeoplePage />); });
    await waitFor(() => screen.getByTestId('people-grid'));

    expect(screen.queryByText('secret@example.com')).not.toBeInTheDocument();
    expect(screen.queryByText('bcrypt-hash-should-never-show')).not.toBeInTheDocument();
  });
});
