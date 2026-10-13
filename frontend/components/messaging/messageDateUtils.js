export function parseMessageTimestamp(value) {
  if (value instanceof Date) {
    return Number.isNaN(value.getTime()) ? null : value;
  }

  if (typeof value !== 'string' && typeof value !== 'number') return null;

  const timestamp = new Date(value);
  return Number.isNaN(timestamp.getTime()) ? null : timestamp;
}

export function getLocalDateKey(value) {
  const date = parseMessageTimestamp(value);
  if (!date) return null;

  const month = String(date.getMonth() + 1).padStart(2, '0');
  const day = String(date.getDate()).padStart(2, '0');
  return `${date.getFullYear()}-${month}-${day}`;
}

function localDayNumber(date) {
  return Date.UTC(date.getFullYear(), date.getMonth(), date.getDate()) / 86_400_000;
}

export function formatMessageTime(value) {
  const date = parseMessageTimestamp(value);
  if (!date) return '';

  return date.toLocaleTimeString([], {
    hour: '2-digit',
    minute: '2-digit',
  });
}

export function formatDateSeparatorLabel(value, now = new Date()) {
  const date = parseMessageTimestamp(value);
  const reference = parseMessageTimestamp(now) || new Date();
  if (!date) return null;

  const dayDifference = localDayNumber(reference) - localDayNumber(date);
  if (dayDifference === 0) return 'Today';
  if (dayDifference === 1) return 'Yesterday';
  if (dayDifference >= 2 && dayDifference <= 6) {
    return date.toLocaleDateString([], { weekday: 'long' });
  }

  return date.toLocaleDateString([], {
    day: 'numeric',
    month: 'long',
    year: 'numeric',
  });
}

export function compareMessages(a, b) {
  const aDate = parseMessageTimestamp(a?.created_at);
  const bDate = parseMessageTimestamp(b?.created_at);

  if (!aDate && !bDate) return 0;
  if (!aDate) return 1;
  if (!bDate) return -1;

  const timestampDifference = aDate.getTime() - bDate.getTime();
  if (timestampDifference !== 0) return timestampDifference;

  return String(a?.id ?? '').localeCompare(String(b?.id ?? ''));
}
