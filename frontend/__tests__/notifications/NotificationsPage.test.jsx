import React from 'react';
import { fireEvent, render, screen, waitFor } from '@testing-library/react';

const mockPush = jest.fn();

jest.mock('next/navigation', () => ({
  useRouter: () => ({ push: mockPush }),
}));

jest.mock('@/services/api', () => ({
  listNotifications: jest.fn(),
  markAllNotificationsRead: jest.fn(),
  markNotificationRead: jest.fn(),
}));

import {
  listNotifications,
  markAllNotificationsRead,
  markNotificationRead,
} from '@/services/api';
import NotificationsPage from '@/components/notifications/NotificationsPage';

const NOTIFICATION = {
  id: 'n1',
  type: 'CONNECTION_REQUEST',
  actor: {
    id: 'u2',
    username: 'priya',
    first_name: 'Priya',
    last_name: 'Sharma',
    name: 'Priya Sharma',
    profile_photo_url: 'https://cdn.example.com/priya.jpg',
  },
  message: 'Priya Sharma sent you a connection request.',
  action_url: '/dashboard/networking/my-network?tab=requests',
  is_read: false,
  created_at: new Date().toISOString(),
};

describe('NotificationsPage', () => {
  beforeEach(() => {
    jest.clearAllMocks();
    listNotifications.mockResolvedValue({ notifications: [NOTIFICATION], total: 1 });
    markAllNotificationsRead.mockResolvedValue({ success: true, updated: 1 });
    markNotificationRead.mockResolvedValue({ success: true, updated: 1 });
  });

  test('renders notifications and supports unread filter', async () => {
    render(<NotificationsPage />);

    expect(await screen.findByText(/priya sharma sent you a connection request/i)).toBeInTheDocument();
    fireEvent.click(screen.getByText('Unread'));

    await waitFor(() => {
      expect(listNotifications).toHaveBeenLastCalledWith({ limit: 30, offset: 0, unreadOnly: true });
    });
  });

  test('clicking notification marks it read and navigates', async () => {
    render(<NotificationsPage />);

    fireEvent.click(await screen.findByText(/priya sharma sent you a connection request/i));

    await waitFor(() => expect(markNotificationRead).toHaveBeenCalledWith('n1'));
    expect(mockPush).toHaveBeenCalledWith('/dashboard/networking/my-network?tab=requests');
  });

  test('mark all read updates notifications', async () => {
    render(<NotificationsPage />);

    fireEvent.click(await screen.findByRole('button', { name: /mark all read/i }));

    await waitFor(() => expect(markAllNotificationsRead).toHaveBeenCalledTimes(1));
  });

  test('renders empty and error states', async () => {
    listNotifications.mockResolvedValueOnce({ notifications: [], total: 0 });
    const { rerender } = render(<NotificationsPage />);

    expect(await screen.findByText('No notifications')).toBeInTheDocument();

    listNotifications.mockRejectedValueOnce(new Error('boom'));
    rerender(<NotificationsPage />);
    fireEvent.click(screen.getByText('Unread'));

    expect(await screen.findByText(/unable to load notifications/i)).toBeInTheDocument();
  });
});
