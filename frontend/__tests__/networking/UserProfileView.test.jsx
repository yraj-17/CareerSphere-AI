/**
 * UserProfileView tests — Phase 5.6
 *
 * Tests the profile view component. Follows exact conventions from
 * DiscoverPeoplePage.test.jsx / MyNetworkPage.test.jsx.
 *
 * Tests:
 *  A. Profile rendering
 *     1.  Page renders loading skeleton while fetching
 *     2.  Renders profile name, username, headline, location
 *     3.  Renders About section when present
 *     4.  Renders skills as badges
 *     5.  Renders experience section
 *     6.  Renders education section
 *     7.  Empty sections show appropriate message
 *  B. Loading / error states
 *     8.  Shows skeleton during load
 *     9.  Shows error state on API failure
 *     10. Try Again retries the fetch
 *  C. Connection states
 *     11. Connect button shown when status=none
 *     12. Pending button shown when outgoing pending
 *     13. Accept + Decline buttons shown when incoming pending
 *     14. Connected + Remove shown when accepted
 *     15. Edit Profile shown for own profile
 *  D. Connection actions
 *     16. Connect calls sendConnectionRequest with correct userId
 *     17. After Connect, status changes to Pending
 *     18. Accept calls acceptConnectionRequest with connection id
 *     19. Reject calls rejectConnectionRequest with connection id
 *     20. Remove calls removeConnection with connection id
 *  E. Security
 *     21. email not rendered
 *     22. password_hash not rendered
 *     23. currentUser id used to detect own profile
 */

import React from 'react';
import { render, screen, fireEvent, waitFor, act } from '@testing-library/react';

// ─── Mocks ────────────────────────────────────────────────────────────────────

jest.mock('next/link', () => {
  const Link = ({ children, href, ...props }) => <a href={href} {...props}>{children}</a>;
  Link.displayName = 'MockLink';
  return Link;
});

jest.mock('framer-motion', () => ({
  motion: {
    div: ({ children, ...p }) => { const { initial, animate, transition, exit, ...r } = p; return <div {...r}>{children}</div>; },
  },
  AnimatePresence: ({ children }) => <>{children}</>,
}));

jest.mock('@/services/api', () => ({
  getPublicProfile:          jest.fn(),
  getNetworkingUserConnection: jest.fn(),
  sendConnectionRequest:     jest.fn(),
  acceptConnectionRequest:   jest.fn(),
  rejectConnectionRequest:   jest.fn(),
  removeConnection:          jest.fn(),
  extractErrorMessage:       jest.fn((err) => err?.message || 'Error'),
}));

import {
  getPublicProfile,
  getNetworkingUserConnection,
  sendConnectionRequest,
  acceptConnectionRequest,
  rejectConnectionRequest,
  removeConnection,
} from '@/services/api';

import UserProfileView from '@/components/networking/UserProfileView';

// ─── Factories ─────────────────────────────────────────────────────────────────

const VIEWER = { id: 'viewer-001', first_name: 'Alice', last_name: 'Viewer' };

const makeProfile = (overrides = {}) => ({
  user: { id: 'target-001', username: 'johndoe', first_name: 'John', last_name: 'Doe' },
  headline: 'Software Engineer',
  location: 'Mumbai, India',
  about: 'Passionate developer.',
  profile_photo_url: null,
  skills: [{ id: 's1', name: 'Python' }, { id: 's2', name: 'React' }],
  experience: [{
    id: 'e1', company: 'TechCorp', job_title: 'SWE',
    employment_type: 'Full-time', location: 'Remote',
    start_date: '2022-01-01', end_date: null, currently_working: true, description: null,
  }],
  education: [{
    id: 'edu1', institution: 'IIT Bombay', degree: 'B.Tech',
    field_of_study: 'CS', start_date: '2018-07-01', end_date: '2022-05-01', description: null,
  }],
  projects: [],
  certifications: [],
  ...overrides,
});

const NO_CONN = { status: 'none', connection_id: null, requester_id: null, receiver_id: null };
const PENDING_SENT = { status: 'pending', connection_id: 'conn-1', requester_id: 'viewer-001', receiver_id: 'target-001' };
const PENDING_RECV = { status: 'pending', connection_id: 'conn-1', requester_id: 'target-001', receiver_id: 'viewer-001' };
const ACCEPTED = { status: 'accepted', connection_id: 'conn-1', requester_id: 'viewer-001', receiver_id: 'target-001' };

// ─── Setup ─────────────────────────────────────────────────────────────────────

beforeEach(() => {
  jest.clearAllMocks();
  getPublicProfile.mockResolvedValue(makeProfile());
  getNetworkingUserConnection.mockResolvedValue(NO_CONN);
  sendConnectionRequest.mockResolvedValue({ id: 'conn-new', status: 'pending' });
  acceptConnectionRequest.mockResolvedValue({ id: 'conn-1', status: 'accepted' });
  rejectConnectionRequest.mockResolvedValue({ id: 'conn-1', status: 'rejected' });
  removeConnection.mockResolvedValue(undefined);
});

async function renderView(userId = 'target-001', currentUser = VIEWER) {
  await act(async () => { render(<UserProfileView userId={userId} currentUser={currentUser} />); });
}

// ─── A. Profile rendering ──────────────────────────────────────────────────────

test('A1. shows loading skeleton while fetching', () => {
  getPublicProfile.mockReturnValue(new Promise(() => {}));
  render(<UserProfileView userId="target-001" currentUser={VIEWER} />);
  expect(screen.getByTestId('profile-skeleton')).toBeInTheDocument();
});

test('A2. renders profile name, username, headline, and location', async () => {
  await renderView();
  await waitFor(() => screen.getByTestId('profile-name'));
  expect(screen.getByTestId('profile-name')).toHaveTextContent('John Doe');
  expect(screen.getByTestId('profile-username')).toHaveTextContent('@johndoe');
  expect(screen.getByTestId('profile-headline')).toHaveTextContent('Software Engineer');
  expect(screen.getByTestId('profile-location')).toHaveTextContent('Mumbai, India');
});

test('A3. renders About section when present', async () => {
  await renderView();
  await waitFor(() => screen.getByTestId('section-about'));
  expect(screen.getByText('Passionate developer.')).toBeInTheDocument();
});

test('A4. renders skills as badges', async () => {
  await renderView();
  await waitFor(() => screen.getByTestId('section-skills'));
  expect(screen.getByText('Python')).toBeInTheDocument();
  expect(screen.getByText('React')).toBeInTheDocument();
});

test('A5. renders experience section', async () => {
  await renderView();
  await waitFor(() => screen.getByTestId('section-experience'));
  expect(screen.getByText(/TechCorp/)).toBeInTheDocument();
  expect(screen.getByText(/SWE/)).toBeInTheDocument();
});

test('A6. renders education section', async () => {
  await renderView();
  await waitFor(() => screen.getByTestId('section-education'));
  expect(screen.getByText('IIT Bombay')).toBeInTheDocument();
  expect(screen.getByText(/B\.Tech/)).toBeInTheDocument();
});

test('A7. empty skills section shows message', async () => {
  getPublicProfile.mockResolvedValue(makeProfile({ skills: [] }));
  await renderView();
  await waitFor(() => screen.getByTestId('section-skills'));
  expect(screen.getByText(/no skills listed/i)).toBeInTheDocument();
});

// ─── B. Loading / error states ────────────────────────────────────────────────

test('B8. shows skeleton during load', () => {
  getPublicProfile.mockReturnValue(new Promise(() => {}));
  render(<UserProfileView userId="target-001" currentUser={VIEWER} />);
  expect(screen.getByTestId('profile-skeleton')).toBeInTheDocument();
});

test('B9. shows error state on API failure', async () => {
  getPublicProfile.mockRejectedValue(new Error('Network error'));
  await renderView();
  await waitFor(() => screen.getByTestId('profile-error'));
  expect(screen.getByText(/could not load profile/i)).toBeInTheDocument();
});

test('B10. Try Again retries the fetch', async () => {
  getPublicProfile.mockRejectedValueOnce(new Error('fail')).mockResolvedValue(makeProfile());
  await renderView();
  await waitFor(() => screen.getByTestId('profile-error'));
  await act(async () => { fireEvent.click(screen.getByRole('button', { name: /try again/i })); });
  await waitFor(() => screen.getByTestId('profile-view'));
  expect(getPublicProfile).toHaveBeenCalledTimes(2);
});

// ─── C. Connection states ─────────────────────────────────────────────────────

test('C11. Connect button shown when status=none', async () => {
  getNetworkingUserConnection.mockResolvedValue(NO_CONN);
  await renderView();
  await waitFor(() => screen.getByTestId('connect-btn'));
  expect(screen.getByTestId('connect-btn')).toBeInTheDocument();
});

test('C12. Pending button shown for outgoing pending', async () => {
  getNetworkingUserConnection.mockResolvedValue(PENDING_SENT);
  await renderView();
  await waitFor(() => screen.getByTestId('pending-btn'));
  expect(screen.getByTestId('pending-btn')).toBeInTheDocument();
});

test('C13. Accept + Decline shown for incoming pending', async () => {
  getNetworkingUserConnection.mockResolvedValue(PENDING_RECV);
  await renderView();
  await waitFor(() => screen.getByTestId('accept-btn'));
  expect(screen.getByTestId('accept-btn')).toBeInTheDocument();
  expect(screen.getByTestId('reject-btn')).toBeInTheDocument();
});

test('C14. Connected + Remove shown for accepted', async () => {
  getNetworkingUserConnection.mockResolvedValue(ACCEPTED);
  await renderView();
  await waitFor(() => screen.getByTestId('connected-btn'));
  expect(screen.getByTestId('remove-btn')).toBeInTheDocument();
});

test('C15. Edit Profile button shown for own profile', async () => {
  const ownUser = { id: 'target-001', first_name: 'John', last_name: 'Doe' };
  await act(async () => { render(<UserProfileView userId="target-001" currentUser={ownUser} />); });
  await waitFor(() => screen.getByTestId('edit-profile-btn'));
  expect(screen.getByTestId('edit-profile-btn')).toBeInTheDocument();
  // No connect button
  expect(screen.queryByTestId('connect-btn')).not.toBeInTheDocument();
});

// ─── D. Connection actions ────────────────────────────────────────────────────

test('D16. Connect calls sendConnectionRequest with userId', async () => {
  getNetworkingUserConnection.mockResolvedValue(NO_CONN);
  await renderView();
  await waitFor(() => screen.getByTestId('connect-btn'));
  await act(async () => { fireEvent.click(screen.getByTestId('connect-btn')); });
  expect(sendConnectionRequest).toHaveBeenCalledWith('target-001');
});

test('D17. After Connect, status changes to Pending', async () => {
  getNetworkingUserConnection.mockResolvedValue(NO_CONN);
  await renderView();
  await waitFor(() => screen.getByTestId('connect-btn'));
  await act(async () => { fireEvent.click(screen.getByTestId('connect-btn')); });
  await waitFor(() => screen.getByTestId('pending-btn'));
  expect(screen.getByTestId('pending-btn')).toBeInTheDocument();
});

test('D18. Accept calls acceptConnectionRequest with connId', async () => {
  getNetworkingUserConnection.mockResolvedValue(PENDING_RECV);
  await renderView();
  await waitFor(() => screen.getByTestId('accept-btn'));
  await act(async () => { fireEvent.click(screen.getByTestId('accept-btn')); });
  expect(acceptConnectionRequest).toHaveBeenCalledWith('conn-1');
});

test('D19. Reject calls rejectConnectionRequest with connId', async () => {
  getNetworkingUserConnection.mockResolvedValue(PENDING_RECV);
  await renderView();
  await waitFor(() => screen.getByTestId('reject-btn'));
  await act(async () => { fireEvent.click(screen.getByTestId('reject-btn')); });
  expect(rejectConnectionRequest).toHaveBeenCalledWith('conn-1');
});

test('D20. Remove calls removeConnection with connId', async () => {
  getNetworkingUserConnection.mockResolvedValue(ACCEPTED);
  await renderView();
  await waitFor(() => screen.getByTestId('remove-btn'));
  await act(async () => { fireEvent.click(screen.getByTestId('remove-btn')); });
  expect(removeConnection).toHaveBeenCalledWith('conn-1');
});

// ─── E. Security ──────────────────────────────────────────────────────────────

test('E21. email is not rendered', async () => {
  getPublicProfile.mockResolvedValue({
    ...makeProfile(),
    user: { ...makeProfile().user, email: 'secret@example.com' },
  });
  await renderView();
  await waitFor(() => screen.getByTestId('profile-name'));
  expect(screen.queryByText('secret@example.com')).not.toBeInTheDocument();
});

test('E22. password_hash is not rendered', async () => {
  getPublicProfile.mockResolvedValue({
    ...makeProfile(),
    user: { ...makeProfile().user, password_hash: 'bcrypt-hash-never-render' },
  });
  await renderView();
  await waitFor(() => screen.getByTestId('profile-name'));
  expect(screen.queryByText('bcrypt-hash-never-render')).not.toBeInTheDocument();
});

test('E23. own profile detected from currentUser.id === userId', async () => {
  const ownUser = { id: 'target-001', first_name: 'John', last_name: 'Doe' };
  await act(async () => { render(<UserProfileView userId="target-001" currentUser={ownUser} />); });
  await waitFor(() => screen.getByTestId('edit-profile-btn'));
  // getNetworkingUserConnection must NOT have been called for own profile
  expect(getNetworkingUserConnection).not.toHaveBeenCalled();
});
