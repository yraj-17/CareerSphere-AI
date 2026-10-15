import React from 'react';
import { fireEvent, render, screen, waitFor } from '@testing-library/react';

const mockPush = jest.fn();
const mockCheckAuth = jest.fn();

jest.mock('next/navigation', () => ({
  useRouter: () => ({ push: mockPush }),
}));

jest.mock('@/context/AuthContext', () => ({
  useAuth: () => ({
    isAuthenticated: true,
    isLoading: false,
    checkAuth: mockCheckAuth,
  }),
}));

jest.mock('@/services/api', () => ({
  changePassword: jest.fn(),
  checkUsername: jest.fn(),
  deleteMedia: jest.fn(),
  extractErrorMessage: jest.fn((error) => error?.message || 'Request failed.'),
  getMyProfile: jest.fn(),
  updateMyAccount: jest.fn(),
  updateMyProfile: jest.fn(),
  uploadMedia: jest.fn(),
}));

import {
  changePassword,
  checkUsername,
  getMyProfile,
  updateMyAccount,
  updateMyProfile,
  uploadMedia,
} from '@/services/api';
import AccountSettingsPage from '@/components/settings/AccountSettingsPage';

const PROFILE = {
  user: {
    id: 'u1',
    first_name: 'Raj',
    last_name: 'Yadav',
    username: 'raj',
    email: 'raj@example.com',
  },
  headline: 'Software Developer',
  location: 'Mumbai',
  about: 'Building CareerSphere AI.',
  profile_photo_media_id: null,
  profile_photo: null,
  skills: [{ id: 's1', name: 'React' }],
  education: [],
  experience: [],
  projects: [],
  certifications: [],
  career_preferences: {},
  completeness: { percentage: 20, completed: ['Basic information'], missing: ['Skills'] },
};

describe('AccountSettingsPage', () => {
  beforeEach(() => {
    jest.clearAllMocks();
    getMyProfile.mockResolvedValue(PROFILE);
    checkUsername.mockResolvedValue({ username: 'raj_dev', available: true, message: 'Username is available.' });
    updateMyAccount.mockResolvedValue({ ...PROFILE.user, username: 'raj_dev' });
    updateMyProfile.mockResolvedValue(PROFILE);
    uploadMedia.mockResolvedValue({ id: 'media-2' });
    changePassword.mockResolvedValue({ message: 'Password updated successfully.' });
  });

  test('loads account settings and saves personal account changes', async () => {
    render(<AccountSettingsPage />);

    expect(await screen.findByRole('heading', { name: 'Settings' })).toBeInTheDocument();
    fireEvent.change(screen.getByLabelText(/username/i), { target: { value: 'raj_dev' } });
    fireEvent.click(screen.getByRole('button', { name: /save changes/i }));

    await waitFor(() => {
      expect(updateMyAccount).toHaveBeenCalledWith({
        first_name: 'Raj',
        last_name: 'Yadav',
        username: 'raj_dev',
      });
      expect(updateMyProfile).toHaveBeenCalledWith({
        headline: 'Software Developer',
        location: 'Mumbai',
        about: 'Building CareerSphere AI.',
      });
    });
  });

  test('shows duplicate username validation from the backend', async () => {
    checkUsername.mockResolvedValueOnce({ available: false, message: 'This username is already taken.' });
    render(<AccountSettingsPage />);

    await screen.findByRole('heading', { name: 'Settings' });
    fireEvent.change(screen.getByLabelText(/username/i), { target: { value: 'existing_user' } });
    fireEvent.click(screen.getByRole('button', { name: /save changes/i }));

    expect((await screen.findAllByText('This username is already taken.')).length).toBeGreaterThan(0);
    expect(updateMyAccount).not.toHaveBeenCalled();
  });

  test('changes password through the existing authentication endpoint', async () => {
    render(<AccountSettingsPage />);

    await screen.findByRole('heading', { name: 'Settings' });
    fireEvent.change(screen.getByLabelText(/current password/i), { target: { value: 'Password123' } });
    fireEvent.change(screen.getAllByLabelText(/new password/i)[0], { target: { value: 'NewPassword456' } });
    fireEvent.change(screen.getByLabelText(/confirm new password/i), { target: { value: 'NewPassword456' } });
    fireEvent.click(screen.getByRole('button', { name: /update password/i }));

    await waitFor(() => {
      expect(changePassword).toHaveBeenCalledWith({
        current_password: 'Password123',
        new_password: 'NewPassword456',
      });
    });
  });

  test('uploads a new profile photo through the existing media flow', async () => {
    render(<AccountSettingsPage />);

    await screen.findByRole('heading', { name: 'Settings' });
    const file = new File(['avatar'], 'avatar.png', { type: 'image/png' });
    fireEvent.change(screen.getByLabelText(/upload photo/i), { target: { files: [file], value: '' } });

    await waitFor(() => {
      expect(uploadMedia).toHaveBeenCalledWith(file, 'profile_image');
      expect(updateMyProfile).toHaveBeenCalledWith({ profile_photo_media_id: 'media-2' });
    });
  });
});
