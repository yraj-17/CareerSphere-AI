import React from 'react';
import { fireEvent, render, screen, waitFor } from '@testing-library/react';
import HomeFeedPage from '@/components/home/HomeFeedPage';

const mockPush = jest.fn();

jest.mock('next/navigation', () => ({
  useRouter: () => ({ push: mockPush }),
}));

jest.mock('@/context/AuthContext', () => ({
  useAuth: () => ({
    user: { id: 'user-1', first_name: 'Raj', last_name: 'Yadav', username: 'raj', created_at: '2026-01-01T00:00:00Z' },
    isAuthenticated: true,
    isLoading: false,
  }),
}));

jest.mock('@/services/api', () => ({
  createPost: jest.fn(),
  createPostComment: jest.fn(),
  deleteMedia: jest.fn(),
  deletePost: jest.fn(),
  deletePostComment: jest.fn(),
  extractErrorMessage: (error) => error?.message || 'Request failed',
  getMyProfile: jest.fn(() => Promise.resolve({ headline: 'Product builder', profile_photo: null })),
  getNetworkingUsers: jest.fn(() => Promise.resolve({ users: [] })),
  listPostComments: jest.fn(() => Promise.resolve({ comments: [] })),
  listPosts: jest.fn(() => Promise.resolve({ total: 0, offset: 0, posts: [] })),
  listResources: jest.fn(() => Promise.resolve({ resources: [] })),
  likePost: jest.fn(),
  sendConnectionRequest: jest.fn(),
  unlikePost: jest.fn(),
  updatePost: jest.fn(),
  uploadMedia: jest.fn(),
}));

describe('HomeFeedPage', () => {
  it('renders the Home feed and composer', async () => {
    render(<HomeFeedPage />);
    expect(screen.getByRole('heading', { name: 'Home' })).toBeInTheDocument();
    fireEvent.click(screen.getByRole('button', { name: /share something with your network/i }));
    expect(screen.getByRole('textbox', { name: 'Post content' })).toBeInTheDocument();
    await waitFor(() => expect(screen.getByText('Share your first update')).toBeInTheDocument());
  });

  it('validates an empty post before calling the API', async () => {
    render(<HomeFeedPage />);
    fireEvent.click(screen.getByRole('button', { name: /share something with your network/i }));
    fireEvent.click(screen.getByRole('button', { name: /publish/i }));
    expect(await screen.findByRole('alert')).toHaveTextContent('Write something before publishing');
  });
});
