/**
 * PersonCard component tests — Phase 5.4
 *
 * Tests:
 *  1. Renders user name, username, headline, location
 *  2. Shows Connect button for status=none
 *  3. Shows Pending button (disabled) for status=pending
 *  4. Shows Connected button (disabled) for status=accepted
 *  5. Does NOT render email or password fields
 *  6. Connect button calls onConnect with correct userId
 *  7. Pending/accepted buttons do NOT call onConnect when clicked
 *  8. isConnecting=true shows "Sending…" text and disables button
 *  9. View Profile link points to correct href
 * 10. Falls back to initials avatar when no profile_photo_url
 * 11. Renders profile photo img when URL is provided
 */

import React from 'react';
import { render, screen, fireEvent } from '@testing-library/react';

// Mock next/link — renders a plain <a> for testability
jest.mock('next/link', () => {
  const Link = ({ children, href, ...props }) => (
    <a href={href} {...props}>
      {children}
    </a>
  );
  Link.displayName = 'MockLink';
  return Link;
});

// Mock framer-motion — render children directly, skip animations
jest.mock('framer-motion', () => ({
  motion: {
    article: ({ children, ...props }) => {
      // strip framer-only props so React doesn't warn
      const { initial, animate, transition, ...rest } = props;
      return <article {...rest}>{children}</article>;
    },
  },
  AnimatePresence: ({ children }) => <>{children}</>,
}));

import PersonCard from '@/components/networking/PersonCard';

const BASE_USER = {
  id: 'user-001',
  username: 'testuser',
  first_name: 'Alice',
  last_name: 'Smith',
  headline: 'Frontend Engineer at TechCo',
  location: 'Mumbai, India',
  profile_photo_url: null,
  connection_status: 'none',
};

describe('PersonCard', () => {
  test('1. renders user name, username, headline, and location', () => {
    render(<PersonCard user={BASE_USER} onConnect={jest.fn()} />);

    expect(screen.getByText('Alice Smith')).toBeInTheDocument();
    expect(screen.getByText('@testuser')).toBeInTheDocument();
    expect(screen.getByText('Frontend Engineer at TechCo')).toBeInTheDocument();
    expect(screen.getByText('Mumbai, India')).toBeInTheDocument();
  });

  test('2. shows enabled Connect button when status is none', () => {
    render(<PersonCard user={BASE_USER} onConnect={jest.fn()} />);
    const btn = screen.getByRole('button', { name: /connect/i });
    expect(btn).toBeInTheDocument();
    expect(btn).not.toBeDisabled();
  });

  test('3. shows disabled Pending button when status is pending', () => {
    const user = { ...BASE_USER, connection_status: 'pending' };
    render(<PersonCard user={user} onConnect={jest.fn()} />);
    const btn = screen.getByRole('button', { name: /pending/i });
    expect(btn).toBeDisabled();
  });

  test('4. shows disabled Connected button when status is accepted', () => {
    const user = { ...BASE_USER, connection_status: 'accepted' };
    render(<PersonCard user={user} onConnect={jest.fn()} />);
    const btn = screen.getByRole('button', { name: /connected/i });
    expect(btn).toBeDisabled();
  });

  test('5. does NOT render email, password, or other sensitive fields', () => {
    const user = {
      ...BASE_USER,
      email: 'alice@example.com',
      password_hash: 'should_not_appear',
    };
    render(<PersonCard user={user} onConnect={jest.fn()} />);
    // email field must not be visible
    expect(screen.queryByText('alice@example.com')).not.toBeInTheDocument();
    expect(screen.queryByText('should_not_appear')).not.toBeInTheDocument();
  });

  test('6. Connect button calls onConnect with the user id', () => {
    const onConnect = jest.fn();
    render(<PersonCard user={BASE_USER} onConnect={onConnect} />);
    fireEvent.click(screen.getByRole('button', { name: /connect/i }));
    expect(onConnect).toHaveBeenCalledTimes(1);
    expect(onConnect).toHaveBeenCalledWith('user-001');
  });

  test('7. Pending button click does NOT call onConnect', () => {
    const onConnect = jest.fn();
    const user = { ...BASE_USER, connection_status: 'pending' };
    render(<PersonCard user={user} onConnect={onConnect} />);
    fireEvent.click(screen.getByRole('button', { name: /pending/i }));
    expect(onConnect).not.toHaveBeenCalled();
  });

  test('7b. Connected button click does NOT call onConnect', () => {
    const onConnect = jest.fn();
    const user = { ...BASE_USER, connection_status: 'accepted' };
    render(<PersonCard user={user} onConnect={onConnect} />);
    fireEvent.click(screen.getByRole('button', { name: /connected/i }));
    expect(onConnect).not.toHaveBeenCalled();
  });

  test('8. isConnecting=true shows Sending… and disables Connect button', () => {
    render(<PersonCard user={BASE_USER} onConnect={jest.fn()} isConnecting />);
    // The aria-label is always "Connect with Alice Smith"; query by that,
    // then verify the visible text changed to "Sending…"
    const btn = screen.getByRole('button', { name: /connect with alice smith/i });
    expect(btn).toBeDisabled();
    expect(screen.getByText(/sending/i)).toBeInTheDocument();
  });

  test('9. View Profile link points to /dashboard/networking/user-001', () => {
    render(<PersonCard user={BASE_USER} onConnect={jest.fn()} />);
    const link = screen.getByRole('link', { name: /view profile/i });
    expect(link).toHaveAttribute('href', '/dashboard/networking/user-001');
  });

  test('10. renders initials avatar when no profile_photo_url', () => {
    render(<PersonCard user={BASE_USER} onConnect={jest.fn()} />);
    // Avatar initials: A + S
    expect(screen.getByText('AS')).toBeInTheDocument();
  });

  test('11. renders profile photo img when URL is provided', () => {
    const user = { ...BASE_USER, profile_photo_url: 'https://example.com/photo.jpg' };
    render(<PersonCard user={user} onConnect={jest.fn()} />);
    const img = screen.getByRole('img', { name: /alice smith/i });
    expect(img).toHaveAttribute('src', 'https://example.com/photo.jpg');
  });
});
