/**
 * Networking API service functions tests — Phase 5.4
 *
 * Tests:
 *  1.  getNetworkingUsers calls GET /api/networking/users with params
 *  2.  getNetworkingUsers passes q param only when non-empty
 *  3.  sendConnectionRequest calls POST /api/networking/connections/{userId}
 *  4.  getNetworkingUserConnection calls GET /api/networking/users/{id}/connection
 *  5.  getMyConnections calls GET /api/networking/connections
 *  6.  getIncomingRequests calls GET /api/networking/requests/incoming
 *  7.  getOutgoingRequests calls GET /api/networking/requests/outgoing
 *  8.  acceptConnectionRequest calls POST /api/networking/requests/{id}/accept
 *  9.  rejectConnectionRequest calls POST /api/networking/requests/{id}/reject
 * 10.  cancelConnectionRequest calls POST /api/networking/requests/{id}/cancel
 * 11.  removeConnection calls DELETE /api/networking/connections/{id}
 */

// ─── Stable mock client shared across all tests ────────────────────────────────
// The mock must be defined BEFORE any imports so Jest hoisting works correctly.
// We export a shared object that axios.create() always returns, so the module
// under test and the tests reference exactly the same mock instance.

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

// Mock lib/auth so localStorage isn't touched
jest.mock('@/lib/auth', () => ({
  getStoredToken: jest.fn(() => 'test-jwt-token'),
  clearStoredAuth: jest.fn(),
}));

// Import the service AFTER the mocks are registered
const api = require('@/services/api');

// ─── Per-test reset ────────────────────────────────────────────────────────────
beforeEach(() => {
  jest.clearAllMocks();
  mockClient.get.mockResolvedValue({ data: {} });
  mockClient.post.mockResolvedValue({ data: {} });
  mockClient.delete.mockResolvedValue({ data: undefined });
});

// ─── Tests ─────────────────────────────────────────────────────────────────────

describe('Networking API functions', () => {
  test('1. getNetworkingUsers calls GET /api/networking/users', async () => {
    mockClient.get.mockResolvedValue({
      data: { users: [], total: 0, limit: 20, offset: 0 },
    });
    const result = await api.getNetworkingUsers({ limit: 20, offset: 0 });
    expect(mockClient.get).toHaveBeenCalledWith(
      '/api/networking/users',
      expect.objectContaining({ params: expect.objectContaining({ limit: 20, offset: 0 }) })
    );
    expect(result.total).toBe(0);
  });

  test('2. getNetworkingUsers passes q only when non-empty', async () => {
    mockClient.get.mockResolvedValue({
      data: { users: [], total: 0, limit: 20, offset: 0 },
    });

    // with q
    await api.getNetworkingUsers({ q: 'alice', limit: 20, offset: 0 });
    expect(mockClient.get.mock.calls[0][1].params.q).toBe('alice');

    jest.clearAllMocks();
    mockClient.get.mockResolvedValue({
      data: { users: [], total: 0, limit: 20, offset: 0 },
    });

    // without q — empty string should not be passed
    await api.getNetworkingUsers({ q: '', limit: 20, offset: 0 });
    expect(mockClient.get.mock.calls[0][1].params.q).toBeUndefined();
  });

  test('3. sendConnectionRequest POSTs to correct endpoint', async () => {
    mockClient.post.mockResolvedValue({ data: { id: 'c1', status: 'pending' } });
    const result = await api.sendConnectionRequest('user-xyz');
    expect(mockClient.post).toHaveBeenCalledWith(
      '/api/networking/connections/user-xyz'
    );
    expect(result.status).toBe('pending');
  });

  test('4. getNetworkingUserConnection calls correct endpoint', async () => {
    mockClient.get.mockResolvedValue({ data: { status: 'none' } });
    const result = await api.getNetworkingUserConnection('user-abc');
    expect(mockClient.get).toHaveBeenCalledWith(
      '/api/networking/users/user-abc/connection'
    );
    expect(result.status).toBe('none');
  });

  test('5. getMyConnections calls GET /api/networking/connections', async () => {
    mockClient.get.mockResolvedValue({ data: [] });
    await api.getMyConnections();
    expect(mockClient.get).toHaveBeenCalledWith('/api/networking/connections');
  });

  test('6. getIncomingRequests calls GET /api/networking/requests/incoming', async () => {
    mockClient.get.mockResolvedValue({ data: [] });
    await api.getIncomingRequests();
    expect(mockClient.get).toHaveBeenCalledWith(
      '/api/networking/requests/incoming'
    );
  });

  test('7. getOutgoingRequests calls GET /api/networking/requests/outgoing', async () => {
    mockClient.get.mockResolvedValue({ data: [] });
    await api.getOutgoingRequests();
    expect(mockClient.get).toHaveBeenCalledWith(
      '/api/networking/requests/outgoing'
    );
  });

  test('8. acceptConnectionRequest POSTs to /requests/{id}/accept', async () => {
    mockClient.post.mockResolvedValue({ data: { status: 'accepted' } });
    await api.acceptConnectionRequest('conn-111');
    expect(mockClient.post).toHaveBeenCalledWith(
      '/api/networking/requests/conn-111/accept'
    );
  });

  test('9. rejectConnectionRequest POSTs to /requests/{id}/reject', async () => {
    mockClient.post.mockResolvedValue({ data: { status: 'rejected' } });
    await api.rejectConnectionRequest('conn-222');
    expect(mockClient.post).toHaveBeenCalledWith(
      '/api/networking/requests/conn-222/reject'
    );
  });

  test('10. cancelConnectionRequest POSTs to /requests/{id}/cancel', async () => {
    mockClient.post.mockResolvedValue({ data: { status: 'cancelled' } });
    await api.cancelConnectionRequest('conn-333');
    expect(mockClient.post).toHaveBeenCalledWith(
      '/api/networking/requests/conn-333/cancel'
    );
  });

  test('11. removeConnection DELETEs /api/networking/connections/{id}', async () => {
    mockClient.delete.mockResolvedValue({ data: undefined });
    await api.removeConnection('conn-444');
    expect(mockClient.delete).toHaveBeenCalledWith(
      '/api/networking/connections/conn-444'
    );
  });
});
