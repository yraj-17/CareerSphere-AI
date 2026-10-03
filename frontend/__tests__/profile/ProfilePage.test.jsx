import React from 'react';
import { render, screen, waitFor } from '@testing-library/react';

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
  addCertification: jest.fn(),
  addEducation: jest.fn(),
  addExperience: jest.fn(),
  addProject: jest.fn(),
  addSkill: jest.fn(),
  deleteCertification: jest.fn(),
  deleteEducation: jest.fn(),
  deleteExperience: jest.fn(),
  deleteProject: jest.fn(),
  deleteSkill: jest.fn(),
  extractErrorMessage: jest.fn((err) => err?.message || 'Request failed.'),
  getMyProfile: jest.fn(),
  optimizeMyProfile: jest.fn(),
  updateCareerPreferences: jest.fn(),
  updateCertification: jest.fn(),
  updateEducation: jest.fn(),
  updateExperience: jest.fn(),
  updateMyProfile: jest.fn(),
  updateProject: jest.fn(),
  uploadMedia: jest.fn(),
}));

import { getMyProfile } from '@/services/api';
import ProfilePage from '@/components/profile/ProfilePage';

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
  profile_photo_media_id: 'media-1',
  profile_photo: {
    id: 'media-1',
    url: 'https://cdn.example.com/profile-photo.jpg',
  },
  completeness: {
    percentage: 80,
    completed: ['Basic info'],
    missing: ['Experience'],
  },
  skills: [],
  experience: [],
  education: [],
  projects: [],
  certifications: [],
  career_preferences: {},
};

describe('ProfilePage', () => {
  beforeEach(() => {
    jest.clearAllMocks();
    getMyProfile.mockResolvedValue(PROFILE);
  });

  test('displays the existing uploaded profile photo', async () => {
    const { container } = render(<ProfilePage />);

    expect(await screen.findByRole('heading', { name: /raj yadav/i })).toBeInTheDocument();

    await waitFor(() => {
      expect(container.querySelector('img[src="https://cdn.example.com/profile-photo.jpg"]')).toBeInTheDocument();
    });
  });
});
