import React from 'react';
import { fireEvent, render, screen, waitFor, within } from '@testing-library/react';

jest.mock('next/link', () => {
  const Link = ({ children, href, ...props }) => (
    <a href={href} {...props}>
      {children}
    </a>
  );
  Link.displayName = 'MockLink';
  return Link;
});

jest.mock('@/services/api', () => ({
  listCommunities: jest.fn(),
  getCommunity: jest.fn(),
  createCommunity: jest.fn(),
  joinCommunity: jest.fn(),
  leaveCommunity: jest.fn(),
  listCommunityPosts: jest.fn(),
  createCommunityPost: jest.fn(),
  setCommunityPostReaction: jest.fn(),
  listCommunityPostComments: jest.fn(),
  createCommunityPostComment: jest.fn(),
  deleteCommunityPost: jest.fn(),
  listCommunityMembers: jest.fn(),
  extractErrorMessage: jest.fn((err) => err?.message || 'Request failed.'),
}));

import {
  createCommunity,
  createCommunityPost,
  createCommunityPostComment,
  deleteCommunityPost,
  getCommunity,
  joinCommunity,
  leaveCommunity,
  listCommunityPostComments,
  listCommunities,
  listCommunityMembers,
  listCommunityPosts,
  setCommunityPostReaction,
} from '@/services/api';
import CommunitiesPage from '@/components/communities/CommunitiesPage';
import CommunityDetailPage from '@/components/communities/CommunityDetailPage';

const COMMUNITIES = [
  {
    id: 'ai-ml',
    name: 'AI & Machine Learning',
    description: 'Discuss model building, RAG, and applied ML.',
    category: 'ai_ml',
    tags: ['AI', 'RAG'],
    member_count: 2431,
    joined: false,
  },
  {
    id: 'career-growth',
    name: 'Career Growth Circle',
    description: 'Professional growth, interviews, and portfolio reviews.',
    category: 'career',
    tags: ['Jobs'],
    member_count: 87,
    joined: true,
  },
];

beforeEach(() => {
  jest.clearAllMocks();
  document.body.style.overflow = '';
  listCommunities.mockResolvedValue({ communities: COMMUNITIES });
  getCommunity.mockResolvedValue({ ...COMMUNITIES[0], joined: true, visibility: 'public', created_at: '2026-10-02' });
  listCommunityPosts.mockResolvedValue({
    posts: [
      {
        id: 'post-1',
        community_id: 'ai-ml',
        content: 'Has anyone worked with RAG using Qdrant?',
        author: { id: 'u1', first_name: 'Raj', last_name: 'Yadav' },
        like_count: 24,
        reaction_counts: { LIKE: 24, LOVE: 0, CELEBRATE: 0, SUPPORT: 0, INSIGHTFUL: 0, FUNNY: 0 },
        total_reactions: 24,
        my_reaction: null,
        comment_count: 8,
        can_delete: true,
        created_at: '2h ago',
      },
    ],
  });
  setCommunityPostReaction.mockResolvedValue({
    post_id: 'post-1',
    my_reaction: 'LIKE',
    counts: { LIKE: 25, LOVE: 0, CELEBRATE: 0, SUPPORT: 0, INSIGHTFUL: 0, FUNNY: 0 },
    total: 25,
  });
  listCommunityPostComments.mockResolvedValue({
    comments: [
      {
        id: 'comment-1',
        post_id: 'post-1',
        content: 'Good point.',
        author: { id: 'u2', first_name: 'User', last_name: 'One' },
      },
    ],
    total: 1,
  });
  createCommunityPostComment.mockResolvedValue({
    id: 'comment-2',
    post_id: 'post-1',
    content: 'I agree.',
    author: { id: 'u3', first_name: 'Test', last_name: 'User' },
  });
  deleteCommunityPost.mockResolvedValue({ success: true, post_id: 'post-1' });
  listCommunityMembers.mockResolvedValue({
    members: [
      { id: 'u1', first_name: 'Raj', last_name: 'Yadav', headline: 'Software Developer' },
    ],
  });
  joinCommunity.mockResolvedValue({ success: true });
  leaveCommunity.mockResolvedValue({ success: true });
  createCommunity.mockRejectedValue({ response: { status: 404 } });
  createCommunityPost.mockRejectedValue({ response: { status: 404 } });
});

describe('CommunitiesPage', () => {
  test('renders the communities page with discover controls and cards', async () => {
    render(<CommunitiesPage />);

    expect(screen.getByRole('heading', { level: 1, name: /communities/i })).toBeInTheDocument();
    expect(screen.getByRole('button', { name: /create community/i })).toBeInTheDocument();
    expect(screen.getByPlaceholderText(/search communities/i)).toBeInTheDocument();
    expect(screen.getByRole('tab', { name: /discover/i })).toHaveAttribute('aria-selected', 'true');

    await waitFor(() => expect(screen.getByTestId('communities-grid')).toBeInTheDocument());
    expect(screen.getByRole('link', { name: /^ai & machine learning$/i })).toHaveAttribute('href', '/dashboard/communities/ai-ml');
    expect(screen.getByText(/2,431 members/i)).toBeInTheDocument();
  });

  test('supports search, category filters, and my communities tab', async () => {
    render(<CommunitiesPage />);
    await waitFor(() => screen.getByTestId('communities-grid'));

    fireEvent.change(screen.getByPlaceholderText(/search communities/i), { target: { value: 'career' } });
    await waitFor(() => {
      expect(screen.queryByRole('link', { name: /^ai & machine learning$/i })).not.toBeInTheDocument();
      expect(screen.getByRole('link', { name: /^career growth circle$/i })).toBeInTheDocument();
    });

    fireEvent.click(screen.getByRole('button', { name: /ai & machine learning/i }));
    expect(await screen.findByTestId('communities-empty')).toBeInTheDocument();

    fireEvent.click(screen.getByRole('tab', { name: /my communities/i }));
    fireEvent.change(screen.getByPlaceholderText(/search communities/i), { target: { value: '' } });
    await waitFor(() => expect(listCommunities).toHaveBeenCalledWith(expect.objectContaining({ membership: 'joined' })));
  });

  test('join button calls the join API and leave uses confirmation', async () => {
    render(<CommunitiesPage />);
    await waitFor(() => screen.getByTestId('communities-grid'));

    fireEvent.click(screen.getByRole('button', { name: /join community/i }));
    await waitFor(() => expect(joinCommunity).toHaveBeenCalledWith('ai-ml'));

    const joinedButtons = screen.getAllByRole('button', { name: /^joined$/i });
    fireEvent.click(joinedButtons[joinedButtons.length - 1]);
    expect(screen.getByRole('dialog', { name: /leave community/i })).toBeInTheDocument();
    fireEvent.click(screen.getByRole('button', { name: /^leave$/i }));
    await waitFor(() => expect(leaveCommunity).toHaveBeenCalledWith('career-growth'));
  });

  test('create community modal validates fields and reports missing backend', async () => {
    render(<CommunitiesPage />);

    fireEvent.click(screen.getByRole('button', { name: /create community/i }));
    const dialog = screen.getByRole('dialog', { name: /create community/i });
    fireEvent.click(within(dialog).getByRole('button', { name: /create community/i }));

    expect(await screen.findByText(/community name is required/i)).toBeInTheDocument();
    expect(screen.getByText(/description is required/i)).toBeInTheDocument();

    fireEvent.change(within(dialog).getByLabelText(/community name/i), { target: { value: 'Cloud Builders' } });
    fireEvent.change(within(dialog).getByLabelText(/description/i), { target: { value: 'A community for cloud engineers.' } });
    fireEvent.click(within(dialog).getByRole('button', { name: /create community/i }));

    expect(await screen.findByText(/community creation is waiting for backend integration/i)).toBeInTheDocument();
  });

  test('shows backend-not-connected empty state when community endpoints are missing', async () => {
    listCommunities.mockRejectedValueOnce({ response: { status: 404 } });

    render(<CommunitiesPage />);

    expect(await screen.findByText(/communities backend is not connected yet/i)).toBeInTheDocument();
    expect(screen.getByText(/no communities found/i)).toBeInTheDocument();
  });
});

describe('CommunityDetailPage', () => {
  test('renders community detail header, posts tab, and post UI', async () => {
    render(<CommunityDetailPage communityId="ai-ml" />);

    expect(await screen.findByRole('heading', { name: /ai & machine learning/i })).toBeInTheDocument();
    expect(screen.getByText(/2,431 members/i)).toBeInTheDocument();
    expect(screen.getByRole('tab', { name: /posts/i })).toHaveAttribute('aria-selected', 'true');
    expect(await screen.findByText(/has anyone worked with rag/i)).toBeInTheDocument();
    expect(screen.getByPlaceholderText(/share something with your community/i)).toBeInTheDocument();
  });

  test('community post shows author profile image when available', async () => {
    listCommunityPosts.mockResolvedValueOnce({
      posts: [
        {
          id: 'post-1',
          community_id: 'ai-ml',
          content: 'Profile image should render.',
          author: {
            id: 'u1',
            first_name: 'Raj',
            last_name: 'Yadav',
            profile_photo_url: 'https://cdn.example.com/raj.jpg',
          },
          total_reactions: 0,
          comment_count: 0,
          can_delete: false,
          created_at: '2h ago',
        },
      ],
    });

    render(<CommunityDetailPage communityId="ai-ml" />);

    expect(await screen.findByRole('img', { name: 'Raj Yadav' })).toHaveAttribute('src', 'https://cdn.example.com/raj.jpg');
    expect(screen.queryByText('RY')).not.toBeInTheDocument();
  });

  test('community post falls back to author initials when no profile image exists', async () => {
    render(<CommunityDetailPage communityId="ai-ml" />);

    await screen.findByText(/has anyone worked with rag/i);
    expect(screen.getByText('RY')).toBeInTheDocument();
  });

  test('different community post authors display their own images or initials', async () => {
    listCommunityPosts.mockResolvedValueOnce({
      posts: [
        {
          id: 'post-1',
          community_id: 'ai-ml',
          content: 'Raj has a photo.',
          author: {
            id: 'u1',
            first_name: 'Raj',
            last_name: 'Yadav',
            profile_photo_url: 'https://cdn.example.com/raj.jpg',
          },
          total_reactions: 0,
          comment_count: 0,
          can_delete: false,
          created_at: '2h ago',
        },
        {
          id: 'post-2',
          community_id: 'ai-ml',
          content: 'User One has no photo.',
          author: { id: 'u2', first_name: 'User', last_name: 'One' },
          total_reactions: 0,
          comment_count: 0,
          can_delete: false,
          created_at: '1h ago',
        },
      ],
    });

    render(<CommunityDetailPage communityId="ai-ml" />);

    expect(await screen.findByRole('img', { name: 'Raj Yadav' })).toHaveAttribute('src', 'https://cdn.example.com/raj.jpg');
    expect(screen.getByText('UO')).toBeInTheDocument();
  });

  test('broken community author image falls back to initials', async () => {
    listCommunityPosts.mockResolvedValueOnce({
      posts: [
        {
          id: 'post-1',
          community_id: 'ai-ml',
          content: 'Broken profile image should fallback.',
          author: {
            id: 'u1',
            first_name: 'Raj',
            last_name: 'Yadav',
            profile_photo_url: 'https://cdn.example.com/broken.jpg',
          },
          total_reactions: 0,
          comment_count: 0,
          can_delete: false,
          created_at: '2h ago',
        },
      ],
    });

    render(<CommunityDetailPage communityId="ai-ml" />);

    fireEvent.error(await screen.findByRole('img', { name: 'Raj Yadav' }));
    expect(screen.getByText('RY')).toBeInTheDocument();
  });

  test('reaction picker selects and removes reactions', async () => {
    render(<CommunityDetailPage communityId="ai-ml" />);
    await screen.findByText(/has anyone worked with rag/i);

    fireEvent.click(screen.getByRole('button', { name: /like 24/i }));
    fireEvent.click(screen.getByRole('button', { name: /love/i }));

    await waitFor(() => expect(setCommunityPostReaction).toHaveBeenCalledWith('post-1', 'LOVE'));
  });

  test('comments open, list existing comments, and submit a new comment', async () => {
    render(<CommunityDetailPage communityId="ai-ml" />);
    await screen.findByText(/has anyone worked with rag/i);

    fireEvent.click(screen.getByRole('button', { name: /^8$/i }));
    expect(await screen.findByText(/good point/i)).toBeInTheDocument();
    expect(listCommunityPostComments).toHaveBeenCalledWith('post-1');

    fireEvent.change(screen.getByPlaceholderText(/write a comment/i), { target: { value: 'I agree.' } });
    fireEvent.click(screen.getAllByRole('button', { name: /^post$/i }).pop());

    await waitFor(() => expect(createCommunityPostComment).toHaveBeenCalledWith('post-1', { content: 'I agree.' }));
    expect(await screen.findByText(/test user/i)).toBeInTheDocument();
  });

  test('community comments show author profile image when available', async () => {
    listCommunityPostComments.mockResolvedValueOnce({
      comments: [
        {
          id: 'comment-1',
          post_id: 'post-1',
          content: 'Good point.',
          author: {
            id: 'u2',
            first_name: 'User',
            last_name: 'One',
            profile_photo_url: 'https://cdn.example.com/user-one.jpg',
          },
        },
      ],
      total: 1,
    });

    render(<CommunityDetailPage communityId="ai-ml" />);
    await screen.findByText(/has anyone worked with rag/i);

    fireEvent.click(screen.getByRole('button', { name: /^8$/i }));

    expect(await screen.findByRole('img', { name: 'User One' })).toHaveAttribute('src', 'https://cdn.example.com/user-one.jpg');
  });

  test('share copies a stable community post URL when Web Share is unavailable', async () => {
    const writeText = jest.fn().mockResolvedValue(undefined);
    Object.assign(navigator, { clipboard: { writeText }, share: undefined });

    render(<CommunityDetailPage communityId="ai-ml" />);
    await screen.findByText(/has anyone worked with rag/i);

    fireEvent.click(screen.getByRole('button', { name: /share/i }));

    await waitFor(() => {
      expect(writeText).toHaveBeenCalledWith(expect.stringContaining('/dashboard/communities/ai-ml?post=post-1'));
    });
    expect(await screen.findByText(/link copied/i)).toBeInTheDocument();
  });

  test('delete option is visible for authorized users and removes the post after confirmation', async () => {
    render(<CommunityDetailPage communityId="ai-ml" />);
    await screen.findByText(/has anyone worked with rag/i);

    fireEvent.click(screen.getByRole('button', { name: /post options/i }));
    fireEvent.click(screen.getByRole('button', { name: /delete/i }));
    expect(screen.getByRole('dialog', { name: /delete post/i })).toBeInTheDocument();

    fireEvent.click(screen.getByRole('button', { name: /^delete$/i }));
    await waitFor(() => expect(deleteCommunityPost).toHaveBeenCalledWith('post-1'));
    await waitFor(() => expect(screen.queryByText(/has anyone worked with rag/i)).not.toBeInTheDocument());
  });

  test('delete option is hidden for unauthorized users', async () => {
    listCommunityPosts.mockResolvedValueOnce({
      posts: [
        {
          id: 'post-1',
          community_id: 'ai-ml',
          content: 'Has anyone worked with RAG using Qdrant?',
          author: { id: 'u1', first_name: 'Raj', last_name: 'Yadav' },
          total_reactions: 0,
          comment_count: 0,
          can_delete: false,
          created_at: '2h ago',
        },
      ],
    });

    render(<CommunityDetailPage communityId="ai-ml" />);
    await screen.findByText(/has anyone worked with rag/i);

    expect(screen.queryByRole('button', { name: /post options/i })).not.toBeInTheDocument();
  });

  test('renders about and members tabs with profile links', async () => {
    render(<CommunityDetailPage communityId="ai-ml" />);
    await screen.findByRole('heading', { name: /ai & machine learning/i });

    fireEvent.click(screen.getByRole('tab', { name: /about/i }));
    expect(screen.getByText(/about this community/i)).toBeInTheDocument();
    expect(screen.getByText(/public/i)).toBeInTheDocument();

    fireEvent.click(screen.getByRole('tab', { name: /members/i }));
    expect(await screen.findByText(/software developer/i)).toBeInTheDocument();
    expect(screen.getByRole('link', { name: /view profile/i })).toHaveAttribute('href', '/dashboard/networking/u1');
  });

  test('post composer validates text and reports missing backend', async () => {
    render(<CommunityDetailPage communityId="ai-ml" />);
    await screen.findByPlaceholderText(/share something with your community/i);

    fireEvent.click(screen.getByRole('button', { name: /^post$/i }));
    expect(screen.getByText(/write something or add at least one image before posting/i)).toBeInTheDocument();

    fireEvent.change(screen.getByPlaceholderText(/share something with your community/i), { target: { value: 'Hello community' } });
    fireEvent.click(screen.getByRole('button', { name: /^post$/i }));
    expect(await screen.findByText(/community posting is waiting for backend integration/i)).toBeInTheDocument();
  });

  test('shows backend-ready empty state when detail endpoint is missing', async () => {
    getCommunity.mockRejectedValueOnce({ response: { status: 404 } });

    render(<CommunityDetailPage communityId="missing" />);

    expect(await screen.findByText(/community backend is not connected yet/i)).toBeInTheDocument();
  });
});
