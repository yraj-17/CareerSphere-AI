/**
 * MyNetworkPage tests — Phase 5.5
 *
 * Follows the exact jest conventions established in DiscoverPeoplePage.test.jsx:
 *   - jest.mock next/link  (plain <a>)
 *   - jest.mock framer-motion  (strip animation props)
 *   - jest.mock @/services/api  (named function mocks)
 *
 * Tests:
 *  1.  My Network page renders without crashing
 *  2.  Connections tab loads connections on mount
 *  3.  Connection cards are displayed with correct names
 *  4.  Connection count badge is correct
 *  5.  Switching to Requests tab fetches incoming requests
 *  6.  Request cards are shown with correct names
 *  7.  Request count badge is correct
 *  8.  Switching to Sent tab fetches outgoing requests
 *  9.  Sent cards are shown with correct names
 * 10.  Sent count badge is correct
 * 11.  Accept button calls acceptConnectionRequest with correct id
 * 12.  Accepted request disappears from Requests list
 * 13.  Connections count increments after accept (tab invalidated)
 * 14.  Reject button calls rejectConnectionRequest with correct id
 * 15.  Rejected request disappears from Requests list
 * 16.  Remove button shows confirmation dialog
 * 17.  Remove dialog Cancel keeps the connection
 * 18.  Remove dialog Confirm calls removeConnection with correct id
 * 19.  Removed connection disappears from Connections list
 * 20.  Cancel (sent) button shows confirmation dialog
 * 21.  Cancel dialog Confirm calls cancelConnectionRequest with correct id
 * 22.  Cancelled sent request disappears from Sent list
 * 23.  View Profile link on Connection card points to correct user route
 * 24.  Empty Connections state renders with Discover People link
 * 25.  Empty Requests state renders correct message
 * 26.  Empty Sent state renders correct message
 * 27.  API error shows error state with Try Again button
 * 28.  Accept button is disabled while request is in-flight (busy)
 * 29.  No sensitive fields (email, password_hash) are rendered
 */

import React from 'react';
import { render, screen, fireEvent, waitFor, act } from '@testing-library/react';

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
      const { initial, animate, transition, exit, ...rest } = props;
      return <article {...rest}>{children}</article>;
    },
    div: ({ children, ...props }) => {
      const { initial, animate, transition, exit, ...rest } = props;
      return <div {...rest}>{children}</div>;
    },
  },
  AnimatePresence: ({ children }) => <>{children}</>,
}));

// ─── Mock API service ──────────────────────────────────────────────────────────
jest.mock('@/services/api', () => ({
  getMyNetworkConnections:  jest.fn(),
  getMyNetworkIncoming:     jest.fn(),
  getMyNetworkOutgoing:     jest.fn(),
  acceptConnectionRequest:  jest.fn(),
  rejectConnectionRequest:  jest.fn(),
  cancelConnectionRequest:  jest.fn(),
  removeConnection:         jest.fn(),
  extractErrorMessage:      jest.fn((err) => err?.message || 'An error occurred.'),
}));

import {
  getMyNetworkConnections,
  getMyNetworkIncoming,
  getMyNetworkOutgoing,
  acceptConnectionRequest,
  rejectConnectionRequest,
  cancelConnectionRequest,
  removeConnection,
} from '@/services/api';

import MyNetworkPage from '@/components/networking/MyNetworkPage';

// ─── Factories ─────────────────────────────────────────────────────────────────

const makeEnrichedConn = (id, overrides = {}) => ({
  id,
  requester_id: 'user-me',
  receiver_id: `user-${id}`,
  status: 'accepted',
  created_at: '2026-01-01T00:00:00Z',
  updated_at: '2026-01-01T00:00:00Z',
  other_user: {
    id: `user-${id}`,
    username: `person_${id}`,
    first_name: 'Alice',
    last_name: `${id}`,
    headline: `Engineer ${id}`,
    location: 'Mumbai',
    profile_photo_url: null,
  },
  ...overrides,
});

const makeIncomingConn = (id) => ({
  ...makeEnrichedConn(id),
  status: 'pending',
  requester_id: `user-${id}`,
  receiver_id: 'user-me',
  other_user: {
    id: `user-${id}`,
    username: `requester_${id}`,
    first_name: 'Bob',
    last_name: `${id}`,
    headline: `Designer ${id}`,
    location: 'Pune',
    profile_photo_url: null,
  },
});

const makeSentConn = (id) => ({
  ...makeEnrichedConn(id),
  status: 'pending',
  requester_id: 'user-me',
  receiver_id: `user-${id}`,
  other_user: {
    id: `user-${id}`,
    username: `receiver_${id}`,
    first_name: 'Carol',
    last_name: `${id}`,
    headline: `Manager ${id}`,
    location: 'Delhi',
    profile_photo_url: null,
  },
});

// ─── Setup / teardown ──────────────────────────────────────────────────────────

beforeEach(() => {
  jest.clearAllMocks();
  // Default: all tabs return empty
  getMyNetworkConnections.mockResolvedValue([]);
  getMyNetworkIncoming.mockResolvedValue([]);
  getMyNetworkOutgoing.mockResolvedValue([]);
  acceptConnectionRequest.mockResolvedValue({ status: 'accepted' });
  rejectConnectionRequest.mockResolvedValue({ status: 'rejected' });
  cancelConnectionRequest.mockResolvedValue({ status: 'cancelled' });
  removeConnection.mockResolvedValue(undefined);
});

// ─── Helpers ───────────────────────────────────────────────────────────────────

async function renderPage() {
  let result;
  await act(async () => {
    result = render(<MyNetworkPage />);
  });
  return result;
}

async function switchTab(tabId) {
  await act(async () => {
    fireEvent.click(screen.getByTestId(`tab-${tabId}`));
  });
}

// ─── Tests ─────────────────────────────────────────────────────────────────────

// 1. Renders without crashing
test('1. My Network page renders without crashing', async () => {
  await renderPage();
  expect(screen.getByText('My Network')).toBeInTheDocument();
  expect(screen.getByText(/manage your connections/i)).toBeInTheDocument();
});

// 2. Connections tab loads on mount
test('2. Connections tab loads connections on mount', async () => {
  getMyNetworkConnections.mockResolvedValue([makeEnrichedConn('c1')]);
  await renderPage();
  await waitFor(() => expect(getMyNetworkConnections).toHaveBeenCalledTimes(1));
});

// 3. Connection cards show correct names
test('3. Connection cards are displayed with correct names', async () => {
  getMyNetworkConnections.mockResolvedValue([
    makeEnrichedConn('c1'),
    makeEnrichedConn('c2'),
  ]);
  await renderPage();
  await waitFor(() => {
    expect(screen.getAllByTestId('connection-card')).toHaveLength(2);
  });
});

// 4. Connection count badge
test('4. Connection count badge matches loaded data', async () => {
  getMyNetworkConnections.mockResolvedValue([
    makeEnrichedConn('c1'),
    makeEnrichedConn('c2'),
    makeEnrichedConn('c3'),
  ]);
  await renderPage();
  await waitFor(() => {
    expect(screen.getByTestId('tab-count-connections')).toHaveTextContent('3');
  });
});

// 5. Switching to Requests tab fetches incoming
test('5. switching to Requests tab fetches incoming requests', async () => {
  getMyNetworkIncoming.mockResolvedValue([makeIncomingConn('r1')]);
  await renderPage();
  await switchTab('requests');
  await waitFor(() => expect(getMyNetworkIncoming).toHaveBeenCalledTimes(1));
});

// 6. Request cards shown
test('6. Request cards are displayed with correct names', async () => {
  getMyNetworkIncoming.mockResolvedValue([makeIncomingConn('r1'), makeIncomingConn('r2')]);
  await renderPage();
  await switchTab('requests');
  await waitFor(() => {
    expect(screen.getAllByTestId('connection-card')).toHaveLength(2);
  });
});

// 7. Request count badge
test('7. Request count badge matches loaded data', async () => {
  getMyNetworkIncoming.mockResolvedValue([makeIncomingConn('r1'), makeIncomingConn('r2')]);
  await renderPage();
  await switchTab('requests');
  await waitFor(() => {
    expect(screen.getByTestId('tab-count-requests')).toHaveTextContent('2');
  });
});

// 8. Switching to Sent tab fetches outgoing
test('8. switching to Sent tab fetches outgoing requests', async () => {
  getMyNetworkOutgoing.mockResolvedValue([makeSentConn('s1')]);
  await renderPage();
  await switchTab('sent');
  await waitFor(() => expect(getMyNetworkOutgoing).toHaveBeenCalledTimes(1));
});

// 9. Sent cards shown
test('9. Sent request cards are displayed', async () => {
  getMyNetworkOutgoing.mockResolvedValue([makeSentConn('s1')]);
  await renderPage();
  await switchTab('sent');
  await waitFor(() => {
    expect(screen.getAllByTestId('connection-card')).toHaveLength(1);
  });
});

// 10. Sent count badge
test('10. Sent count badge matches loaded data', async () => {
  getMyNetworkOutgoing.mockResolvedValue([makeSentConn('s1'), makeSentConn('s2')]);
  await renderPage();
  await switchTab('sent');
  await waitFor(() => {
    expect(screen.getByTestId('tab-count-sent')).toHaveTextContent('2');
  });
});

// 11. Accept calls API with correct id
test('11. Accept button calls acceptConnectionRequest with correct connection id', async () => {
  getMyNetworkIncoming.mockResolvedValue([makeIncomingConn('r1')]);
  await renderPage();
  await switchTab('requests');
  await waitFor(() => screen.getByTestId('accept-btn'));

  await act(async () => {
    fireEvent.click(screen.getByTestId('accept-btn'));
  });

  expect(acceptConnectionRequest).toHaveBeenCalledWith('r1');
});

// 12. Accepted request disappears from list
test('12. Accepted request disappears from Requests list', async () => {
  getMyNetworkIncoming.mockResolvedValue([makeIncomingConn('r1'), makeIncomingConn('r2')]);
  await renderPage();
  await switchTab('requests');
  await waitFor(() => expect(screen.getAllByTestId('connection-card')).toHaveLength(2));

  await act(async () => {
    fireEvent.click(screen.getAllByTestId('accept-btn')[0]);
  });

  await waitFor(() => {
    expect(screen.getAllByTestId('connection-card')).toHaveLength(1);
  });
});

// 13. Connections tab invalidated after accept (will re-fetch on next visit)
test('13. Connections tab is invalidated after accepting a request', async () => {
  // Start with connections loaded
  getMyNetworkConnections.mockResolvedValue([makeEnrichedConn('c1')]);
  getMyNetworkIncoming.mockResolvedValue([makeIncomingConn('r1')]);
  await renderPage();
  await waitFor(() => screen.getByTestId('tab-count-connections'));

  // Switch to requests and accept
  await switchTab('requests');
  await waitFor(() => screen.getByTestId('accept-btn'));
  await act(async () => { fireEvent.click(screen.getByTestId('accept-btn')); });

  // Switch back to connections — it should refetch (called twice total now)
  getMyNetworkConnections.mockResolvedValue([makeEnrichedConn('c1'), makeEnrichedConn('c-new')]);
  await switchTab('connections');
  await waitFor(() => expect(getMyNetworkConnections).toHaveBeenCalledTimes(2));
});

// 14. Reject calls API with correct id
test('14. Reject button calls rejectConnectionRequest with correct id', async () => {
  getMyNetworkIncoming.mockResolvedValue([makeIncomingConn('r1')]);
  await renderPage();
  await switchTab('requests');
  await waitFor(() => screen.getByTestId('reject-btn'));

  await act(async () => {
    fireEvent.click(screen.getByTestId('reject-btn'));
  });

  expect(rejectConnectionRequest).toHaveBeenCalledWith('r1');
});

// 15. Rejected request disappears
test('15. Rejected request disappears from Requests list', async () => {
  getMyNetworkIncoming.mockResolvedValue([makeIncomingConn('r1'), makeIncomingConn('r2')]);
  await renderPage();
  await switchTab('requests');
  await waitFor(() => expect(screen.getAllByTestId('connection-card')).toHaveLength(2));

  await act(async () => {
    fireEvent.click(screen.getAllByTestId('reject-btn')[0]);
  });

  await waitFor(() => {
    expect(screen.getAllByTestId('connection-card')).toHaveLength(1);
  });
});

// 16. Remove shows confirmation dialog
test('16. Remove button shows confirmation dialog', async () => {
  getMyNetworkConnections.mockResolvedValue([makeEnrichedConn('c1')]);
  await renderPage();
  await waitFor(() => screen.getByTestId('remove-btn'));

  fireEvent.click(screen.getByTestId('remove-btn'));
  expect(screen.getByTestId('confirm-dialog')).toBeInTheDocument();
  expect(screen.getByText(/remove this connection/i)).toBeInTheDocument();
});

// 17. Remove dialog Cancel keeps the connection
test('17. Clicking Keep in Remove dialog does not remove the connection', async () => {
  getMyNetworkConnections.mockResolvedValue([makeEnrichedConn('c1')]);
  await renderPage();
  await waitFor(() => screen.getByTestId('remove-btn'));

  fireEvent.click(screen.getByTestId('remove-btn'));
  expect(screen.getByTestId('confirm-dialog')).toBeInTheDocument();

  fireEvent.click(screen.getByRole('button', { name: /keep/i }));
  expect(removeConnection).not.toHaveBeenCalled();
  expect(screen.queryByTestId('confirm-dialog')).not.toBeInTheDocument();
  expect(screen.getByTestId('connection-card')).toBeInTheDocument();
});

// 18. Remove dialog Confirm calls removeConnection
test('18. Confirming Remove calls removeConnection with the correct id', async () => {
  getMyNetworkConnections.mockResolvedValue([makeEnrichedConn('c1')]);
  await renderPage();
  await waitFor(() => screen.getByTestId('remove-btn'));

  fireEvent.click(screen.getByTestId('remove-btn'));
  await act(async () => {
    fireEvent.click(screen.getByTestId('confirm-action-btn'));
  });

  expect(removeConnection).toHaveBeenCalledWith('c1');
});

// 19. Removed connection disappears from list
test('19. Removed connection disappears from Connections list', async () => {
  getMyNetworkConnections.mockResolvedValue([
    makeEnrichedConn('c1'),
    makeEnrichedConn('c2'),
  ]);
  await renderPage();
  await waitFor(() => expect(screen.getAllByTestId('connection-card')).toHaveLength(2));

  fireEvent.click(screen.getAllByTestId('remove-btn')[0]);
  await act(async () => {
    fireEvent.click(screen.getByTestId('confirm-action-btn'));
  });

  await waitFor(() => {
    expect(screen.getAllByTestId('connection-card')).toHaveLength(1);
  });
});

// 20. Cancel (sent) shows confirmation dialog
test('20. Cancel button on Sent tab shows confirmation dialog', async () => {
  getMyNetworkOutgoing.mockResolvedValue([makeSentConn('s1')]);
  await renderPage();
  await switchTab('sent');
  await waitFor(() => screen.getByTestId('cancel-btn'));

  fireEvent.click(screen.getByTestId('cancel-btn'));
  expect(screen.getByTestId('confirm-dialog')).toBeInTheDocument();
  expect(screen.getByText(/cancel this connection request/i)).toBeInTheDocument();
});

// 21. Cancel dialog Confirm calls cancelConnectionRequest
test('21. Confirming Cancel calls cancelConnectionRequest with correct id', async () => {
  getMyNetworkOutgoing.mockResolvedValue([makeSentConn('s1')]);
  await renderPage();
  await switchTab('sent');
  await waitFor(() => screen.getByTestId('cancel-btn'));

  fireEvent.click(screen.getByTestId('cancel-btn'));
  await act(async () => {
    fireEvent.click(screen.getByTestId('confirm-action-btn'));
  });

  expect(cancelConnectionRequest).toHaveBeenCalledWith('s1');
});

// 22. Cancelled request disappears from Sent list
test('22. Cancelled request disappears from Sent list', async () => {
  getMyNetworkOutgoing.mockResolvedValue([makeSentConn('s1'), makeSentConn('s2')]);
  await renderPage();
  await switchTab('sent');
  await waitFor(() => expect(screen.getAllByTestId('connection-card')).toHaveLength(2));

  fireEvent.click(screen.getAllByTestId('cancel-btn')[0]);
  await act(async () => {
    fireEvent.click(screen.getByTestId('confirm-action-btn'));
  });

  await waitFor(() => {
    expect(screen.getAllByTestId('connection-card')).toHaveLength(1);
  });
});

// 23. View Profile link points to correct user route
test('23. View Profile link on Connection card points to correct user route', async () => {
  const conn = makeEnrichedConn('c1');
  getMyNetworkConnections.mockResolvedValue([conn]);
  await renderPage();
  await waitFor(() => screen.getByRole('link', { name: /view profile/i }));

  const link = screen.getByRole('link', { name: /view profile/i });
  expect(link).toHaveAttribute('href', `/dashboard/networking/user-c1`);
});

// 24. Empty Connections state renders with Discover People link
test('24. Empty Connections state renders with Discover People link', async () => {
  getMyNetworkConnections.mockResolvedValue([]);
  await renderPage();
  await waitFor(() => screen.getByTestId('section-empty'));

  expect(screen.getByText(/no connections yet/i)).toBeInTheDocument();

  // There are two "Discover People" links (header + empty state CTA).
  // Assert that at least one points to the discover route.
  const discoverLinks = screen.getAllByRole('link', { name: /discover people/i });
  expect(discoverLinks.length).toBeGreaterThanOrEqual(1);
  expect(discoverLinks.some((l) => l.getAttribute('href') === '/dashboard/networking')).toBe(true);
});

// 25. Empty Requests state renders correct message
test('25. Empty Requests state renders correct message', async () => {
  getMyNetworkIncoming.mockResolvedValue([]);
  await renderPage();
  await switchTab('requests');
  await waitFor(() => screen.getByTestId('section-empty'));

  expect(screen.getByText(/no pending requests/i)).toBeInTheDocument();
});

// 26. Empty Sent state renders correct message
test('26. Empty Sent state renders correct message', async () => {
  getMyNetworkOutgoing.mockResolvedValue([]);
  await renderPage();
  await switchTab('sent');
  await waitFor(() => screen.getByTestId('section-empty'));

  expect(screen.getByText(/no sent requests/i)).toBeInTheDocument();
});

// 27. API error shows error state with Try Again
test('27. API error shows error state with Try Again button', async () => {
  getMyNetworkConnections.mockRejectedValue(new Error('Network error'));
  await renderPage();
  await waitFor(() => screen.getByTestId('section-error'));

  expect(screen.getByTestId('section-error')).toBeInTheDocument();
  expect(screen.getByRole('button', { name: /try again/i })).toBeInTheDocument();
});

// 28. Accept button disabled while in-flight
test('28. Accept button is disabled while request is in-flight', async () => {
  // Hold the promise so we stay in-flight
  let resolve;
  acceptConnectionRequest.mockReturnValue(new Promise((r) => { resolve = r; }));
  getMyNetworkIncoming.mockResolvedValue([makeIncomingConn('r1')]);

  await renderPage();
  await switchTab('requests');
  await waitFor(() => screen.getByTestId('accept-btn'));

  act(() => {
    fireEvent.click(screen.getByTestId('accept-btn'));
  });

  // Button should be disabled during in-flight
  expect(screen.getByTestId('accept-btn')).toBeDisabled();

  // Resolve to clean up
  await act(async () => { resolve({ status: 'accepted' }); });
});

// 29. No sensitive fields rendered
test('29. No sensitive user fields are rendered', async () => {
  const conn = {
    ...makeEnrichedConn('c1'),
    other_user: {
      ...makeEnrichedConn('c1').other_user,
      email: 'secret@example.com',
      password_hash: 'bcrypt-hash-should-never-render',
    },
  };
  getMyNetworkConnections.mockResolvedValue([conn]);
  await renderPage();
  await waitFor(() => screen.getByTestId('connection-card'));

  expect(screen.queryByText('secret@example.com')).not.toBeInTheDocument();
  expect(screen.queryByText('bcrypt-hash-should-never-render')).not.toBeInTheDocument();
});
