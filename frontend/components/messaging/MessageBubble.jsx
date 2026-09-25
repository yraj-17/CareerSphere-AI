'use client';

/**
 * MessageBubble — renders a single chat message.
 *
 * Props:
 *   message     {object}  — { id, sender_id, content, created_at, delivered_at, read_at }
 *   isMine      {boolean} — true if sender_id === current user
 *   showStatus  {boolean} — show delivery/read ticks (only for own messages)
 */

import React from 'react';
import { CheckCheck, Check } from 'lucide-react';

function formatTime(iso) {
  if (!iso) return '';
  try {
    return new Date(iso).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' });
  } catch {
    return '';
  }
}

function DeliveryStatus({ message }) {
  if (message.read_at) {
    return (
      <span className="flex items-center gap-0.5 text-cyan" title="Read">
        <CheckCheck className="h-3 w-3" />
      </span>
    );
  }
  if (message.delivered_at) {
    return (
      <span className="flex items-center gap-0.5 text-slate-400" title="Delivered">
        <CheckCheck className="h-3 w-3" />
      </span>
    );
  }
  return (
    <span className="flex items-center gap-0.5 text-slate-500" title="Sent">
      <Check className="h-3 w-3" />
    </span>
  );
}

export default function MessageBubble({ message, isMine, showStatus = true }) {
  return (
    <div
      data-testid="message-bubble"
      className={`flex ${isMine ? 'justify-end' : 'justify-start'} px-4`}
    >
      <div className={`max-w-[75%] sm:max-w-[65%] flex flex-col ${isMine ? 'items-end' : 'items-start'}`}>
        <div
          className={`px-4 py-2.5 rounded-2xl text-sm leading-relaxed break-words whitespace-pre-wrap ${
            isMine
              ? 'bg-accent text-black rounded-br-sm shadow-[0_2px_12px_rgba(255,143,50,0.3)]'
              : 'bg-white/[0.08] text-slate-100 border border-white/10 rounded-bl-sm'
          }`}
        >
          {message.content}
        </div>

        <div className={`flex items-center gap-1.5 mt-1 text-[11px] text-slate-500 ${isMine ? 'flex-row-reverse' : 'flex-row'}`}>
          <span>{formatTime(message.created_at)}</span>
          {isMine && showStatus && <DeliveryStatus message={message} />}
        </div>
      </div>
    </div>
  );
}
