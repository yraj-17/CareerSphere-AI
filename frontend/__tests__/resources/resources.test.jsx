import React from 'react';
import { fireEvent, render, screen, waitFor, within } from '@testing-library/react';

const mockPush = jest.fn();

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
  useRouter: () => ({ push: mockPush }),
}));

jest.mock('@/services/api', () => ({
  createResource: jest.fn(),
  deleteResource: jest.fn(),
  extractErrorMessage: jest.fn((err) => err?.message || err?.response?.data?.detail || ''),
  getMyNetworkConnections: jest.fn(),
  getOrCreateConversation: jest.fn(),
  getResource: jest.fn(),
  listResources: jest.fn(),
  saveResource: jest.fn(),
  shareResourceInConversation: jest.fn(),
  unsaveResource: jest.fn(),
  updateResource: jest.fn(),
}));

import {
  createResource,
  deleteResource,
  getMyNetworkConnections,
  getOrCreateConversation,
  getResource,
  listResources,
  saveResource,
  shareResourceInConversation,
  unsaveResource,
  updateResource,
} from '@/services/api';
import ResourceDetailPage from '@/components/resources/ResourceDetailPage';
import ResourcesPage from '@/components/resources/ResourcesPage';

const RESOURCE = {
  id: 'res-1',
  author_id: 'u1',
  author: {
    id: 'u1',
    username: 'raj',
    first_name: 'Raj',
    last_name: 'Yadav',
  },
  title: 'React Hooks Tutorial',
  description: 'A useful guide to useEffect and useMemo.',
  url: 'https://react.dev/learn',
  source_domain: 'react.dev',
  resource_type: 'TUTORIAL',
  category: 'frontend',
  tags: ['React', 'JavaScript'],
  is_owner: true,
  is_saved: false,
  save_count: 0,
  created_at: '2026-10-04T10:00:00Z',
};

describe('Resource Sharing frontend', () => {
  beforeEach(() => {
    jest.clearAllMocks();
    mockPush.mockClear();
    listResources.mockResolvedValue({ resources: [RESOURCE], total: 1, limit: 30, offset: 0 });
    getResource.mockResolvedValue(RESOURCE);
    createResource.mockResolvedValue(RESOURCE);
    updateResource.mockResolvedValue({ ...RESOURCE, title: 'Updated Resource' });
    deleteResource.mockResolvedValue({ success: true });
    saveResource.mockResolvedValue({ success: true, is_saved: true });
    unsaveResource.mockResolvedValue({ success: true, is_saved: false });
    getMyNetworkConnections.mockResolvedValue([
      {
        id: 'conn-1',
        other_user: {
          id: 'u2',
          username: 'priya',
          first_name: 'Priya',
          last_name: 'Sharma',
          headline: 'DevOps Engineer',
        },
      },
      {
        id: 'conn-2',
        other_user: {
          id: 'u3',
          username: 'amit',
          first_name: 'Amit',
          last_name: 'Patel',
          headline: 'Frontend Developer',
        },
      },
    ]);
    getOrCreateConversation.mockImplementation((userId) => Promise.resolve({ id: `conv-${userId}` }));
    shareResourceInConversation.mockResolvedValue({ id: 'msg-1', message_type: 'RESOURCE_SHARE' });
    jest.spyOn(window, 'confirm').mockReturnValue(true);
  });

  afterEach(() => {
    window.confirm.mockRestore?.();
  });

  test('renders the resources page with cards and discovery controls', async () => {
    render(<ResourcesPage />);

    expect(screen.getByRole('heading', { level: 1, name: /resources/i })).toBeInTheDocument();
    expect(screen.getByRole('button', { name: /share resource/i })).toBeInTheDocument();
    expect(screen.getByPlaceholderText(/search resources/i)).toBeInTheDocument();

    await waitFor(() => expect(screen.getByTestId('resources-grid')).toBeInTheDocument());
    expect(screen.getByRole('heading', { level: 2, name: /react hooks tutorial/i })).toBeInTheDocument();
    expect(screen.getByRole('link', { name: /^open$/i })).toHaveAttribute('href', 'https://react.dev/learn');
    expect(screen.getByRole('link', { name: /^view$/i })).toHaveAttribute('href', '/dashboard/resources/res-1');
  });

  test('search, saved tab, type filter, and category filter call the backend with server filters', async () => {
    render(<ResourcesPage />);
    await waitFor(() => expect(listResources).toHaveBeenCalled());

    fireEvent.change(screen.getByPlaceholderText(/search resources/i), { target: { value: 'hooks' } });
    await waitFor(() => expect(listResources).toHaveBeenLastCalledWith(expect.objectContaining({ q: 'hooks' })));

    fireEvent.click(screen.getByRole('tab', { name: /saved/i }));
    await waitFor(() => expect(listResources).toHaveBeenLastCalledWith(expect.objectContaining({ saved: true })));

    fireEvent.click(screen.getByRole('button', { name: /tutorials/i }));
    await waitFor(() => expect(listResources).toHaveBeenLastCalledWith(expect.objectContaining({ resourceType: 'TUTORIAL' })));

    fireEvent.click(screen.getByRole('button', { name: /frontend/i }));
    await waitFor(() => expect(listResources).toHaveBeenLastCalledWith(expect.objectContaining({ category: 'frontend' })));
  });

  test('saves and unsaves a resource from the card', async () => {
    render(<ResourcesPage />);
    await screen.findByText(/react hooks tutorial/i);

    fireEvent.click(screen.getByRole('button', { name: /save resource/i }));
    await waitFor(() => expect(saveResource).toHaveBeenCalledWith('res-1'));

    fireEvent.click(screen.getByRole('button', { name: /unsave resource/i }));
    await waitFor(() => expect(unsaveResource).toHaveBeenCalledWith('res-1'));
  });

  test('share modal loads connections, filters recipients, and sends optional message to each selected recipient', async () => {
    render(<ResourcesPage />);
    await screen.findByText(/react hooks tutorial/i);

    fireEvent.click(screen.getByRole('button', { name: /^share$/i }));
    const dialog = await screen.findByRole('dialog', { name: /share resource/i });
    expect(getMyNetworkConnections).toHaveBeenCalledTimes(1);
    expect(within(dialog).getByText(/priya sharma/i)).toBeInTheDocument();

    fireEvent.change(within(dialog).getByPlaceholderText(/search connections/i), { target: { value: 'priya' } });
    expect(within(dialog).getByText(/priya sharma/i)).toBeInTheDocument();
    expect(within(dialog).queryByText(/amit patel/i)).not.toBeInTheDocument();

    fireEvent.click(within(dialog).getByText(/priya sharma/i));
    fireEvent.change(within(dialog).getByPlaceholderText(/search connections/i), { target: { value: '' } });
    fireEvent.click(within(dialog).getByText(/amit patel/i));
    fireEvent.change(within(dialog).getByPlaceholderText(/check this resource out/i), {
      target: { value: 'Check this out for hooks.' },
    });
    fireEvent.click(within(dialog).getByRole('button', { name: /^send$/i }));

    await waitFor(() => expect(getOrCreateConversation).toHaveBeenCalledWith('u2'));
    expect(getOrCreateConversation).toHaveBeenCalledWith('u3');
    expect(shareResourceInConversation).toHaveBeenCalledWith('conv-u2', {
      resource_id: 'res-1',
      message: 'Check this out for hooks.',
    });
    expect(shareResourceInConversation).toHaveBeenCalledWith('conv-u3', {
      resource_id: 'res-1',
      message: 'Check this out for hooks.',
    });
    expect(shareResourceInConversation).toHaveBeenCalledTimes(2);
  });

  test('create form validates URL and submits normalized resource payload', async () => {
    render(<ResourcesPage />);
    fireEvent.click(screen.getByRole('button', { name: /share resource/i }));

    const dialog = screen.getByRole('dialog', { name: /share a resource/i });
    fireEvent.change(within(dialog).getByLabelText(/title/i), { target: { value: 'New Course' } });
    fireEvent.change(within(dialog).getByLabelText(/^url$/i), { target: { value: 'invalid-url' } });
    expect(within(dialog).getByRole('button', { name: /share resource/i })).toBeDisabled();

    fireEvent.change(within(dialog).getByLabelText(/^url$/i), { target: { value: 'https://example.com/course' } });
    fireEvent.change(within(dialog).getByLabelText(/description/i), { target: { value: 'A useful course.' } });
    fireEvent.change(within(dialog).getByPlaceholderText(/add tag/i), { target: { value: 'React' } });
    fireEvent.keyDown(within(dialog).getByPlaceholderText(/add tag/i), { key: 'Enter' });
    fireEvent.change(within(dialog).getByPlaceholderText(/add tag/i), { target: { value: 'react' } });
    fireEvent.keyDown(within(dialog).getByPlaceholderText(/add tag/i), { key: 'Enter' });
    fireEvent.click(within(dialog).getByRole('button', { name: /share resource/i }));

    await waitFor(() =>
      expect(createResource).toHaveBeenCalledWith(expect.objectContaining({
        title: 'New Course',
        url: 'https://example.com/course',
        tags: ['React'],
      }))
    );
  });

  test('owner controls edit and delete resources from the card', async () => {
    render(<ResourcesPage />);
    await screen.findByText(/react hooks tutorial/i);

    fireEvent.click(screen.getByRole('button', { name: /edit resource/i }));
    const dialog = screen.getByRole('dialog', { name: /edit resource/i });
    fireEvent.change(within(dialog).getByLabelText(/title/i), { target: { value: 'Updated Resource' } });
    fireEvent.click(within(dialog).getByRole('button', { name: /save changes/i }));
    await waitFor(() => expect(updateResource).toHaveBeenCalledWith('res-1', expect.objectContaining({ title: 'Updated Resource' })));

    fireEvent.click(screen.getByRole('button', { name: /delete resource/i }));
    await waitFor(() => expect(deleteResource).toHaveBeenCalledWith('res-1'));
  });

  test('detail page shows resource metadata, save state, and owner controls', async () => {
    render(<ResourceDetailPage resourceId="res-1" />);

    expect(await screen.findByRole('heading', { level: 1, name: /react hooks tutorial/i })).toBeInTheDocument();
    expect(screen.getByText(/react.dev/i)).toBeInTheDocument();
    expect(screen.getByRole('link', { name: /open resource/i })).toHaveAttribute('href', 'https://react.dev/learn');

    fireEvent.click(screen.getByRole('button', { name: /^save$/i }));
    await waitFor(() => expect(saveResource).toHaveBeenCalledWith('res-1'));

    fireEvent.click(screen.getByRole('button', { name: /^edit$/i }));
    expect(screen.getByRole('dialog', { name: /edit resource/i })).toBeInTheDocument();

    fireEvent.click(screen.getByRole('button', { name: /^delete$/i }));
    await waitFor(() => expect(deleteResource).toHaveBeenCalledWith('res-1'));
    expect(mockPush).toHaveBeenCalledWith('/dashboard/resources');
  });
});
