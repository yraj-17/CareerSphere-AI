/**
 * Messaging UI — Frontend Test Suite
 *
 * 15 tests covering the requirements from Phase 5.8.6 spec.
 */

import React from 'react';
import { render, screen, fireEvent, waitFor, act } from '@testing-library/react';
import userEvent from '@testing-library/user-event';

const mockSendMessageRead = jest.fn();

// ─── Mocks ────────────────────────────────────────────────────────────────────

jest.mock('@/services/api', () => ({
  listConversations: jest.fn(),
  listMessages: jest.fn(),
  markMessagesRead: jest.fn(),
  markMessagesDelivered: jest.fn(),
  getOrCreateConversation: jest.fn(),
  getPinnedMessage: jest.fn(),
  deleteMessageForEveryone: jest.fn(),
  extractErrorMessage: jest.fn((e) => e?.message || 'Error'),
}));

jest.mock('@/lib/auth', () => ({
  getStoredToken: jest.fn(() => 'test-jwt-token'),
}));

jest.mock('@/hooks/useMessagingWebSocket', () => ({
  WS_STATE: {
    IDLE: 'idle',
    CONNECTING: 'connecting',
    CONNECTED: 'connected',
    DISCONNECTED: 'disconnected',
    FAILED: 'failed',
  },
  useMessagingWebSocket: jest.fn(() => ({
    wsState: 'connected',
    sendMessage: jest.fn(() => true),
    sendTypingStart: jest.fn(),
    sendTypingStop: jest.fn(),
    sendMessageRead: mockSendMessageRead,
  })),
}));

// next/navigation
jest.mock('next/navigation', () => ({
  useRouter: () => ({ push: jest.fn() }),
  usePathname: () => '/dashboard/messaging',
  useSearchParams: () => ({ get: jest.fn(() => null) }),
}));

// framer-motion: render children directly
jest.mock('framer-motion', () => ({
  motion: {
    div: ({ children, ...p }) => <div {...p}>{children}</div>,
    article: ({ children, ...p }) => <article {...p}>{children}</article>,
  },
  AnimatePresence: ({ children }) => <>{children}</>,
}));

// next/link
jest.mock('next/link', () => {
  const Link = ({ children, href, ...p }) => <a href={href} {...p}>{children}</a>;
  Link.displayName = 'Link';
  return Link;
});

// ─── Component imports ────────────────────────────────────────────────────────

import ConversationList from '@/components/messaging/ConversationList';
import ChatWindow from '@/components/messaging/ChatWindow';
import MessageBubble from '@/components/messaging/MessageBubble';
import TypingIndicator from '@/components/messaging/TypingIndicator';
import MessagingPage from '@/components/messaging/MessagingPage';
import { WS_STATE, useMessagingWebSocket } from '@/hooks/useMessagingWebSocket';
import {
  deleteMessageForEveryone,
  getPinnedMessage,
  listConversations,
  listMessages,
  markMessagesRead,
} from '@/services/api';

beforeEach(() => {
  jest.clearAllMocks();
});

// ─── Fixtures ─────────────────────────────────────────────────────────────────

const CURRENT_USER = { id: 'user-a', first_name: 'Alice', last_name: 'A' };

const OTHER_USER = { id: 'user-b', first_name: 'Bob', last_name: 'B' };

const CONV = {
  conversation_id: 'conv-1',
  other_user: OTHER_USER,
  latest_message_content: 'Hello!',
  latest_message_at: new Date().toISOString(),
  latest_message_sender_id: 'user-b',
  unread_count: 2,
  updated_at: new Date().toISOString(),
};

const MESSAGE_FROM_OTHER = {
  id: 'msg-1',
  conversation_id: 'conv-1',
  sender_id: 'user-b',
  content: 'Hello!',
  created_at: new Date().toISOString(),
  delivered_at: null,
  read_at: null,
};

const MESSAGE_FROM_SELF = {
  id: 'msg-2',
  conversation_id: 'conv-1',
  sender_id: 'user-a',
  content: 'Hey there',
  created_at: new Date().toISOString(),
  delivered_at: new Date().toISOString(),
  read_at: null,
};

// ─────────────────────────────────────────────────────────────────────────────
// 1. Conversation list renders
// ─────────────────────────────────────────────────────────────────────────────
test('1. ConversationList renders conversation items', () => {
  render(
    <ConversationList
      conversations={[CONV]}
      currentUserId={CURRENT_USER.id}
      onSelect={jest.fn()}
    />
  );
  expect(screen.getByTestId('conversation-list')).toBeInTheDocument();
  expect(screen.getByTestId('conversation-item')).toBeInTheDocument();
  expect(screen.getByText('Bob B')).toBeInTheDocument();
});

// ─────────────────────────────────────────────────────────────────────────────
// 2. Empty conversation state
// ─────────────────────────────────────────────────────────────────────────────
test('2. ConversationList shows empty state when no conversations', () => {
  render(
    <ConversationList
      conversations={[]}
      currentUserId={CURRENT_USER.id}
      onSelect={jest.fn()}
    />
  );
  expect(screen.getByText(/no conversations yet/i)).toBeInTheDocument();
});

// ─────────────────────────────────────────────────────────────────────────────
// 3. Conversation opens on click
// ─────────────────────────────────────────────────────────────────────────────
test('3. Clicking a conversation calls onSelect', () => {
  const onSelect = jest.fn();
  render(
    <ConversationList
      conversations={[CONV]}
      currentUserId={CURRENT_USER.id}
      onSelect={onSelect}
    />
  );
  fireEvent.click(screen.getByTestId('conversation-item'));
  expect(onSelect).toHaveBeenCalledWith(CONV);
});

// ─────────────────────────────────────────────────────────────────────────────
// 4. Message history renders
// ─────────────────────────────────────────────────────────────────────────────
test('4. ChatWindow renders message history', () => {
  render(
    <ChatWindow
      conversation={CONV}
      currentUser={CURRENT_USER}
      wsState="connected"
      messages={[MESSAGE_FROM_OTHER, MESSAGE_FROM_SELF]}
      onSend={jest.fn()}
    />
  );
  expect(screen.getByText('Hello!')).toBeInTheDocument();
  expect(screen.getByText('Hey there')).toBeInTheDocument();
  expect(screen.getAllByTestId('message-bubble')).toHaveLength(2);
});

// ─────────────────────────────────────────────────────────────────────────────
// 5. Send button disabled when input is empty
// ─────────────────────────────────────────────────────────────────────────────
test('5. Send button is disabled when input is empty', () => {
  render(
    <ChatWindow
      conversation={CONV}
      currentUser={CURRENT_USER}
      wsState="connected"
      messages={[]}
      onSend={jest.fn()}
    />
  );
  const btn = screen.getByTestId('send-button');
  expect(btn).toBeDisabled();
});

// ─────────────────────────────────────────────────────────────────────────────
// 6. Send button enabled when input has text + WS connected
// ─────────────────────────────────────────────────────────────────────────────
test('6. Send button enables when text entered and WS connected', async () => {
  const user = userEvent.setup();
  render(
    <ChatWindow
      conversation={CONV}
      currentUser={CURRENT_USER}
      wsState="connected"
      messages={[]}
      onSend={jest.fn(() => true)}
    />
  );
  const input = screen.getByTestId('message-input');
  await user.type(input, 'Hi there');
  expect(screen.getByTestId('send-button')).not.toBeDisabled();
});

// ─────────────────────────────────────────────────────────────────────────────
// 7. New message event updates UI (via MessagingPage)
// ─────────────────────────────────────────────────────────────────────────────
test('7. MessagingPage calls listMessages when a conversation is selected', async () => {
  listConversations.mockResolvedValue({
    conversations: [{
      id: CONV.conversation_id,
      other_participant: CONV.other_user,
      latest_message: {
        id: MESSAGE_FROM_OTHER.id,
        sender_id: MESSAGE_FROM_OTHER.sender_id,
        content: MESSAGE_FROM_OTHER.content,
        created_at: MESSAGE_FROM_OTHER.created_at,
      },
      unread_count: CONV.unread_count,
      updated_at: CONV.updated_at,
    }],
    limit: 50,
    offset: 0,
  });
  listMessages.mockResolvedValue({ messages: [MESSAGE_FROM_OTHER], total: 1 });
  markMessagesRead.mockResolvedValue({ updated: 1 });

  render(<MessagingPage currentUser={CURRENT_USER} initialConvId="conv-1" />);

  await waitFor(() => {
    expect(listMessages).toHaveBeenCalledWith('conv-1', expect.objectContaining({ limit: 50 }));
  });
  await waitFor(() => {
    expect(mockSendMessageRead.mock.calls.length).toBeGreaterThanOrEqual(2);
  });
});

// ─────────────────────────────────────────────────────────────────────────────
// 8. Typing indicator shows when isTyping=true
// ─────────────────────────────────────────────────────────────────────────────
test('8. TypingIndicator renders when isTyping is true', () => {
  render(<TypingIndicator name="Bob" />);
  expect(screen.getByTestId('typing-indicator')).toBeInTheDocument();
  expect(screen.getByLabelText(/is typing/i)).toBeInTheDocument();
});

// ─────────────────────────────────────────────────────────────────────────────
// 9. Typing indicator hidden when isTyping=false
// ─────────────────────────────────────────────────────────────────────────────
test('9. ChatWindow does not show typing indicator when isTyping=false', () => {
  render(
    <ChatWindow
      conversation={CONV}
      currentUser={CURRENT_USER}
      wsState="connected"
      messages={[]}
      isTyping={false}
      onSend={jest.fn()}
    />
  );
  expect(screen.queryByTestId('typing-indicator')).not.toBeInTheDocument();
});

// ─────────────────────────────────────────────────────────────────────────────
// 10. Read state: read messages show double-check in cyan
// ─────────────────────────────────────────────────────────────────────────────
test('10. Read message shows read status indicator', () => {
  const readMsg = { ...MESSAGE_FROM_SELF, read_at: new Date().toISOString() };
  render(
    <MessageBubble
      message={readMsg}
      isMine={true}
    />
  );
  expect(screen.getByTitle('Read')).toBeInTheDocument();
});

// ─────────────────────────────────────────────────────────────────────────────
// 11. Unread count displayed in conversation list
// ─────────────────────────────────────────────────────────────────────────────
test('11. Conversation list shows unread count badge', () => {
  render(
    <ConversationList
      conversations={[CONV]}
      unreadMap={{ 'conv-1': 3 }}
      currentUserId={CURRENT_USER.id}
      onSelect={jest.fn()}
    />
  );
  expect(screen.getByText('3')).toBeInTheDocument();
});

// ─────────────────────────────────────────────────────────────────────────────
// 12. WS disconnect shows reconnecting banner
// ─────────────────────────────────────────────────────────────────────────────
test('12. ChatWindow shows reconnecting banner when WS is disconnected', () => {
  render(
    <ChatWindow
      conversation={CONV}
      currentUser={CURRENT_USER}
      wsState="disconnected"
      messages={[]}
      onSend={jest.fn()}
    />
  );
  expect(screen.getByText(/reconnecting/i)).toBeInTheDocument();
});

// ─────────────────────────────────────────────────────────────────────────────
// 13. Mobile back navigation
// ─────────────────────────────────────────────────────────────────────────────
test('13. ChatWindow back button calls onBack', () => {
  const onBack = jest.fn();
  render(
    <ChatWindow
      conversation={CONV}
      currentUser={CURRENT_USER}
      wsState="connected"
      messages={[]}
      onSend={jest.fn()}
      onBack={onBack}
    />
  );
  fireEvent.click(screen.getByLabelText(/back to conversations/i));
  expect(onBack).toHaveBeenCalled();
});

// ─────────────────────────────────────────────────────────────────────────────
// 14. No selected conversation shows placeholder
// ─────────────────────────────────────────────────────────────────────────────
test('14. ChatWindow shows placeholder when no conversation selected', () => {
  render(
    <ChatWindow
      conversation={null}
      currentUser={CURRENT_USER}
      wsState="idle"
      messages={[]}
      onSend={jest.fn()}
    />
  );
  expect(screen.getByText(/select a conversation/i)).toBeInTheDocument();
});

// ─────────────────────────────────────────────────────────────────────────────
// 15. Message length validation (4,000 char limit)
// ─────────────────────────────────────────────────────────────────────────────
test('15. Send button disabled when message exceeds 4000 characters', async () => {
  const user = userEvent.setup();
  render(
    <ChatWindow
      conversation={CONV}
      currentUser={CURRENT_USER}
      wsState="connected"
      messages={[]}
      onSend={jest.fn()}
    />
  );
  const input = screen.getByTestId('message-input');
  // Exactly 4000 chars — within limit, button should be enabled
  fireEvent.change(input, { target: { value: 'a'.repeat(4000) } });
  expect(screen.getByTestId('send-button')).not.toBeDisabled();

  // 4001 chars — exceeds limit, button must be disabled
  fireEvent.change(input, { target: { value: 'a'.repeat(4001) } });
  expect(screen.getByTestId('send-button')).toBeDisabled();
});

test('16. Copy action writes only message content and shows feedback', async () => {
  const writeText = jest.fn().mockResolvedValue(undefined);
  Object.defineProperty(navigator, 'clipboard', {
    configurable: true,
    value: { writeText },
  });

  render(<MessageBubble message={MESSAGE_FROM_SELF} isMine={true} />);
  fireEvent.click(screen.getByLabelText('Message actions'));
  fireEvent.click(screen.getByRole('button', { name: 'Copy Text' }));

  await waitFor(() => expect(writeText).toHaveBeenCalledWith('Hey there'));
  expect(screen.getByRole('status')).toHaveTextContent('Copied');
});

test('17. Delete for everyone immediately sanitizes the sender conversation preview', async () => {
  listConversations.mockResolvedValue({
    conversations: [{
      id: CONV.conversation_id,
      other_participant: CONV.other_user,
      latest_message: {
        id: MESSAGE_FROM_SELF.id,
        sender_id: MESSAGE_FROM_SELF.sender_id,
        content: MESSAGE_FROM_SELF.content,
        created_at: MESSAGE_FROM_SELF.created_at,
      },
      unread_count: 0,
      updated_at: CONV.updated_at,
    }],
  });
  listMessages.mockResolvedValue({ messages: [MESSAGE_FROM_SELF], total: 1 });
  markMessagesRead.mockResolvedValue({ updated: 0 });
  getPinnedMessage.mockResolvedValue({ success: true, message: null });
  deleteMessageForEveryone.mockResolvedValue({ success: true });

  render(<MessagingPage currentUser={CURRENT_USER} initialConvId="conv-1" />);
  await screen.findByText(MESSAGE_FROM_SELF.content, { exact: true });

  fireEvent.click(screen.getByLabelText('Message actions'));
  fireEvent.click(screen.getByRole('button', { name: 'Delete for Everyone' }));
  fireEvent.click(screen.getByTestId('confirm-delete-btn'));

  await waitFor(() => {
    expect(screen.queryByText(MESSAGE_FROM_SELF.content, { exact: true })).not.toBeInTheDocument();
  });
  expect(screen.getByText('🚫 This message was deleted')).toBeInTheDocument();
  expect(deleteMessageForEveryone).toHaveBeenCalledWith(MESSAGE_FROM_SELF.id);
});

test('18. Resource-share message renders a resource preview card', () => {
  const resourceMessage = {
    ...MESSAGE_FROM_OTHER,
    id: 'msg-resource-1',
    content: 'This helped me understand hooks.',
    message_type: 'RESOURCE_SHARE',
    resource_id: 'res-1',
    resource: {
      id: 'res-1',
      title: 'React Hooks Deep Dive',
      description: 'A practical guide to useEffect and custom hooks.',
      resource_type: 'ARTICLE',
      category: 'frontend',
      source_domain: 'example.com',
      tags: ['React', 'Hooks'],
    },
  };

  render(<MessageBubble message={resourceMessage} isMine={false} />);

  expect(screen.getByText('This helped me understand hooks.')).toBeInTheDocument();
  expect(screen.getByText('React Hooks Deep Dive')).toBeInTheDocument();
  expect(screen.getByText('A practical guide to useEffect and custom hooks.')).toBeInTheDocument();
  expect(screen.getByText('React')).toBeInTheDocument();
  expect(screen.getByText('Hooks')).toBeInTheDocument();
  expect(screen.getByRole('link', { name: /open resource/i })).toHaveAttribute(
    'href',
    '/dashboard/resources/res-1'
  );
});

test('19. Resource-share message renders deleted resource fallback safely', () => {
  const resourceMessage = {
    ...MESSAGE_FROM_OTHER,
    id: 'msg-resource-deleted',
    content: '',
    message_type: 'RESOURCE_SHARE',
    resource_id: null,
    resource: null,
  };

  render(<MessageBubble message={resourceMessage} isMine={false} />);

  expect(screen.getByText('Resource no longer available.')).toBeInTheDocument();
  expect(screen.getByText('The original shared resource was deleted.')).toBeInTheDocument();
  expect(screen.queryByRole('link', { name: /open resource/i })).not.toBeInTheDocument();
});
