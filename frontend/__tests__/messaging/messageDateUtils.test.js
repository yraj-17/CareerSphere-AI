import {
  compareMessages,
  formatDateSeparatorLabel,
  formatMessageTime,
  getLocalDateKey,
} from '@/components/messaging/messageDateUtils';

function localDate(year, month, day, hour = 12) {
  return new Date(year, month - 1, day, hour, 0, 0, 0);
}

describe('message date utilities', () => {
  const now = localDate(2026, 10, 13);

  test('labels message dates relative to the current local day', () => {
    expect(formatDateSeparatorLabel(localDate(2026, 10, 13, 9), now)).toBe('Today');
    expect(formatDateSeparatorLabel(localDate(2026, 10, 12, 9), now)).toBe('Yesterday');
    expect(formatDateSeparatorLabel(localDate(2026, 10, 10, 9), now)).toBe(
      localDate(2026, 10, 10).toLocaleDateString([], { weekday: 'long' }),
    );
    expect(formatDateSeparatorLabel(localDate(2026, 10, 1, 9), now)).toBe(
      localDate(2026, 10, 1).toLocaleDateString([], {
        day: 'numeric',
        month: 'long',
        year: 'numeric',
      }),
    );
  });

  test('keeps invalid timestamps out of visual date/time labels', () => {
    expect(getLocalDateKey('not-a-timestamp')).toBeNull();
    expect(formatDateSeparatorLabel('not-a-timestamp', now)).toBeNull();
    expect(formatMessageTime('not-a-timestamp')).toBe('');
  });

  test('sorts messages by persisted timestamp and uses IDs as a stable tie-breaker', () => {
    const first = localDate(2026, 10, 13, 9).toISOString();
    const second = localDate(2026, 10, 13, 10).toISOString();

    expect([
      { id: 'b', created_at: second },
      { id: 'a', created_at: first },
      { id: 'c', created_at: second },
    ].sort(compareMessages).map((message) => message.id)).toEqual(['a', 'b', 'c']);
    expect(compareMessages({ id: 'valid', created_at: first }, { id: 'missing' })).toBeLessThan(0);
  });
});
