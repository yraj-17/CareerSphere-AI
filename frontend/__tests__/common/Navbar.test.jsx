import React from 'react';
import { fireEvent, render, screen, waitFor, within } from '@testing-library/react';

const mockLogout = jest.fn();
const mockPush = jest.fn();
let mockPathname = '/dashboard';
let mockAuthState = {
  isAuthenticated: true,
  user: {
    first_name: 'Raj',
    last_name: 'Yadav',
    username: 'raj',
  },
};

jest.mock('next/link', () => {
  const Link = ({ children, href, ...props }) => (
    <a href={href} {...props}>
      {children}
    </a>
  );
  Link.displayName = 'MockLink';
  return Link;
});

jest.mock('next/navigation', () => ({
  usePathname: () => mockPathname,
  useRouter: () => ({ push: mockPush }),
}));

jest.mock('@/context/AuthContext', () => ({
  useAuth: () => ({
    ...mockAuthState,
    logout: mockLogout,
  }),
}));

jest.mock('@/services/api', () => ({
  getUnreadCount: jest.fn(),
  getNotificationUnreadCount: jest.fn(),
  listNotifications: jest.fn(),
  markAllNotificationsRead: jest.fn(),
  markNotificationRead: jest.fn(),
}));

import {
  getNotificationUnreadCount,
  getUnreadCount,
  listNotifications,
  markAllNotificationsRead,
  markNotificationRead,
} from '@/services/api';
import Navbar from '@/components/common/Navbar';

describe('Navbar', () => {
  beforeEach(() => {
    mockLogout.mockClear();
    mockPush.mockClear();
    getUnreadCount.mockResolvedValue({ unread_count: 0 });
    getNotificationUnreadCount.mockResolvedValue({ unread_count: 0 });
    listNotifications.mockResolvedValue({ notifications: [], total: 0 });
    markAllNotificationsRead.mockResolvedValue({ success: true, updated: 0 });
    markNotificationRead.mockResolvedValue({ success: true, updated: 1 });
    mockPathname = '/dashboard';
    mockAuthState = {
      isAuthenticated: true,
      user: {
        first_name: 'Raj',
        last_name: 'Yadav',
        username: 'raj',
      },
    };
    document.body.style.overflow = '';
  });

  test('renders authenticated navigation with preserved routes', () => {
    render(<Navbar />);

    const primaryNav = screen.getByRole('navigation', { name: /primary navigation/i });

    expect(within(primaryNav).getByRole('link', { name: /^dashboard$/i })).toHaveAttribute('href', '/dashboard');
    expect(within(primaryNav).getByRole('link', { name: /ai career assistant/i })).toHaveAttribute('href', '/dashboard/ai');
    expect(within(primaryNav).getByRole('link', { name: /skill analysis/i })).toHaveAttribute('href', '/dashboard/skill-analysis');
    expect(within(primaryNav).getByRole('link', { name: /career matching/i })).toHaveAttribute('href', '/dashboard/career-matching');
    expect(within(primaryNav).getByRole('link', { name: /messages/i })).toHaveAttribute('href', '/dashboard/messaging');
  });

  test('opens Connect & Explore dropdown with existing and upcoming destinations', () => {
    render(<Navbar />);

    fireEvent.click(screen.getByRole('button', { name: /connect & explore menu/i }));

    expect(screen.getByRole('menuitem', { name: /discover people/i })).toHaveAttribute('href', '/dashboard/networking');
    expect(screen.getByRole('menuitem', { name: /my network/i })).toHaveAttribute('href', '/dashboard/networking/my-network');
    expect(screen.getByRole('menuitem', { name: /requests/i })).toHaveAttribute('href', '/dashboard/networking/my-network?tab=requests');
    expect(screen.getByRole('menuitem', { name: /communities/i })).toHaveAttribute('href', '/dashboard/communities');
    expect(screen.getByRole('menuitem', { name: /resources/i })).toHaveAttribute('href', '/dashboard/resources');

    fireEvent.keyDown(document, { key: 'Escape' });
    expect(screen.queryByRole('menuitem', { name: /discover people/i })).not.toBeInTheDocument();
  });

  test('keeps global search local and typeable', () => {
    render(<Navbar />);

    const searchInput = screen.getByPlaceholderText(/search people, skills, careers/i);
    fireEvent.change(searchInput, { target: { value: 'mentor' } });

    expect(searchInput).toHaveValue('mentor');
  });

  test('uses profile dropdown for profile navigation and logout', () => {
    render(<Navbar />);

    fireEvent.click(screen.getByRole('button', { name: /user profile menu/i }));

    expect(screen.getByRole('link', { name: /^profile$/i })).toHaveAttribute('href', '/dashboard/profile');
    fireEvent.click(screen.getByRole('menuitem', { name: /logout/i }));

    expect(mockLogout).toHaveBeenCalledTimes(1);
  });

  test('shows separate message and notification unread badges', async () => {
    getUnreadCount.mockResolvedValue({ unread_count: 3 });
    getNotificationUnreadCount.mockResolvedValue({ unread_count: 2 });

    render(<Navbar />);

    expect(await screen.findByLabelText(/3 unread direct messages/i)).toHaveTextContent('3');
    expect((await screen.findAllByLabelText(/2 unread notifications/i))[0]).toHaveTextContent('2');
  });

  test('opens notification dropdown and marks all read', async () => {
    getNotificationUnreadCount.mockResolvedValue({ unread_count: 1 });
    listNotifications.mockResolvedValue({
      notifications: [
        {
          id: 'n1',
          type: 'CONNECTION_REQUEST',
          actor: { id: 'u2', first_name: 'Priya', last_name: 'Sharma', name: 'Priya Sharma' },
          message: 'Priya Sharma sent you a connection request.',
          action_url: '/dashboard/networking/my-network?tab=requests',
          is_read: false,
          created_at: new Date().toISOString(),
        },
      ],
      total: 1,
    });

    render(<Navbar />);
    fireEvent.click(screen.getAllByRole('button', { name: /notifications/i })[0]);

    expect(await screen.findByText(/priya sharma sent you a connection request/i)).toBeInTheDocument();
    fireEvent.click(screen.getByRole('button', { name: /mark all read/i }));

    await waitFor(() => expect(markAllNotificationsRead).toHaveBeenCalledTimes(1));
  });

  test('clicking a notification marks it read and navigates', async () => {
    listNotifications.mockResolvedValue({
      notifications: [
        {
          id: 'n1',
          type: 'CONNECTION_ACCEPTED',
          actor: { id: 'u2', first_name: 'Priya', last_name: 'Sharma', name: 'Priya Sharma' },
          message: 'Priya Sharma accepted your connection request.',
          action_url: '/dashboard/networking/my-network',
          is_read: false,
          created_at: new Date().toISOString(),
        },
      ],
      total: 1,
    });

    render(<Navbar />);
    fireEvent.click(screen.getAllByRole('button', { name: /notifications/i })[0]);
    fireEvent.click(await screen.findByText(/accepted your connection request/i));

    await waitFor(() => expect(markNotificationRead).toHaveBeenCalledWith('n1'));
    expect(mockPush).toHaveBeenCalledWith('/dashboard/networking/my-network');
  });

  test('notification dropdown shows empty and error states', async () => {
    render(<Navbar />);
    fireEvent.click(screen.getAllByRole('button', { name: /notifications/i })[0]);
    expect(await screen.findByText('No notifications yet.')).toBeInTheDocument();

    listNotifications.mockRejectedValueOnce(new Error('boom'));
    fireEvent.click(screen.getAllByRole('button', { name: /notifications/i })[0]);
    fireEvent.click(screen.getAllByRole('button', { name: /notifications/i })[0]);
    expect(await screen.findByText(/unable to load notifications/i)).toBeInTheDocument();
  });

  test('shows authenticated user profile image when available', () => {
    mockAuthState.user.profile_photo_url = 'https://cdn.example.com/raj-avatar.jpg';

    render(<Navbar />);

    expect(screen.getAllByAltText('Raj Yadav')[0]).toHaveAttribute('src', 'https://cdn.example.com/raj-avatar.jpg');
  });

  test('shows authenticated user initial when no profile image exists', () => {
    render(<Navbar />);

    const userButton = screen.getByRole('button', { name: /user profile menu/i });
    expect(within(userButton).getByText('R')).toBeInTheDocument();
    expect(within(userButton).queryByRole('img')).not.toBeInTheDocument();
  });

  test('falls back to authenticated user initial when profile image fails to load', () => {
    mockAuthState.user.profile_photo_url = 'https://cdn.example.com/broken-avatar.jpg';

    render(<Navbar />);

    const userButton = screen.getByRole('button', { name: /user profile menu/i });
    fireEvent.error(within(userButton).getByRole('img', { name: 'Raj Yadav' }));

    expect(within(userButton).getByText('R')).toBeInTheDocument();
  });

  test('opens and closes mobile navigation drawer', () => {
    render(<Navbar />);

    fireEvent.click(screen.getByRole('button', { name: /open navigation menu/i }));
    expect(screen.getByRole('dialog', { name: /navigation menu/i })).toBeInTheDocument();
    expect(document.body.style.overflow).toBe('hidden');
    expect(screen.getByRole('link', { name: /communities/i })).toHaveAttribute('href', '/dashboard/communities');
    expect(screen.getAllByText(/connect & explore/i).length).toBeGreaterThan(0);
    expect(screen.getByRole('link', { name: /resources/i })).toHaveAttribute('href', '/dashboard/resources');
    expect(screen.getByRole('link', { name: /notifications/i })).toHaveAttribute('href', '/dashboard/notifications');

    fireEvent.keyDown(document, { key: 'Escape' });
    expect(screen.queryByRole('dialog', { name: /navigation menu/i })).not.toBeInTheDocument();
    expect(document.body.style.overflow).toBe('');
  });

  test('keeps public auth links for unauthenticated pages', () => {
    mockAuthState = {
      isAuthenticated: false,
      user: null,
    };
    mockPathname = '/login';

    render(<Navbar />);

    expect(screen.getByRole('link', { name: /careersphere ai dashboard/i })).toHaveAttribute('href', '/');
    expect(screen.getByRole('link', { name: /login/i })).toHaveAttribute('href', '/login');
    expect(screen.getByRole('link', { name: /create account/i })).toHaveAttribute('href', '/signup');
  });
});
