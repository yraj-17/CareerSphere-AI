const mockClient = {
  get: jest.fn(),
  post: jest.fn(),
  delete: jest.fn(),
  patch: jest.fn(),
  put: jest.fn(),
  interceptors: {
    request: { use: jest.fn() },
    response: { use: jest.fn() },
  },
  defaults: { headers: { common: {} } },
};

jest.mock('axios', () => {
  const mock = {
    create: jest.fn(() => mockClient),
    interceptors: {
      request: { use: jest.fn() },
      response: { use: jest.fn() },
    },
  };
  return { ...mock, default: mock };
});

jest.mock('@/lib/auth', () => ({
  getStoredToken: jest.fn(() => 'test-jwt-token'),
  clearStoredAuth: jest.fn(),
}));

const api = require('@/services/api');

beforeEach(() => {
  jest.clearAllMocks();
  mockClient.get.mockResolvedValue({ data: {} });
  mockClient.post.mockResolvedValue({ data: {} });
  mockClient.patch.mockResolvedValue({ data: {} });
  mockClient.delete.mockResolvedValue({ data: {} });
});

describe('Resources API functions', () => {
  test('listResources calls GET /api/resources with filters', async () => {
    await api.listResources({
      q: 'react',
      resourceType: 'TUTORIAL',
      category: 'frontend',
      tag: 'hooks',
      saved: true,
      sort: 'newest',
      limit: 30,
      offset: 5,
    });

    expect(mockClient.get).toHaveBeenCalledWith('/api/resources', {
      params: {
        q: 'react',
        resource_type: 'TUTORIAL',
        category: 'frontend',
        tag: 'hooks',
        saved: true,
        sort: 'newest',
        limit: 30,
        offset: 5,
      },
    });
  });

  test('listResources omits empty optional filters', async () => {
    await api.listResources({ q: ' ', resourceType: 'all', category: 'all', tag: '' });

    expect(mockClient.get).toHaveBeenCalledWith('/api/resources', {
      params: {
        saved: false,
        sort: 'newest',
        limit: 20,
        offset: 0,
      },
    });
  });

  test('getResource calls detail endpoint', async () => {
    await api.getResource('res-1');
    expect(mockClient.get).toHaveBeenCalledWith('/api/resources/res-1');
  });

  test('createResource posts payload', async () => {
    const payload = { title: 'Resource', url: 'https://example.com', resource_type: 'ARTICLE' };
    await api.createResource(payload);
    expect(mockClient.post).toHaveBeenCalledWith('/api/resources', payload);
  });

  test('updateResource patches payload', async () => {
    await api.updateResource('res-1', { title: 'Updated' });
    expect(mockClient.patch).toHaveBeenCalledWith('/api/resources/res-1', { title: 'Updated' });
  });

  test('deleteResource deletes resource', async () => {
    await api.deleteResource('res-1');
    expect(mockClient.delete).toHaveBeenCalledWith('/api/resources/res-1');
  });

  test('save and unsave resource use bookmark endpoints', async () => {
    await api.saveResource('res-1');
    await api.unsaveResource('res-1');

    expect(mockClient.post).toHaveBeenCalledWith('/api/resources/res-1/save');
    expect(mockClient.delete).toHaveBeenCalledWith('/api/resources/res-1/save');
  });

  test('shareResourceInConversation posts resource share payload', async () => {
    await api.shareResourceInConversation('conv-1', {
      resource_id: 'res-1',
      message: 'Check this out',
    });

    expect(mockClient.post).toHaveBeenCalledWith(
      '/api/messaging/conversations/conv-1/resource-share',
      { resource_id: 'res-1', message: 'Check this out' }
    );
  });
});
