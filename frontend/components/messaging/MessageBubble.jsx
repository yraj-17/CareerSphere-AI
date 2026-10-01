'use client';

/**
 * MessageBubble — renders a single chat message with Phase 5.8 features.
 *
 * Props:
 *   message     {object}   — full DirectMessageResponse from API
 *   isMine      {boolean}  — true if sender_id === current user
 *   showStatus  {boolean}  — show delivery/read ticks (only for own messages)
 *   onReply     (message) => void
 *   onStar      (message) => void
 *   onPin       (message) => void
 *   onForward   (message) => void
 *   onDeleteForMe (message) => void
 *   onDeleteForEveryone (message) => void
 *   scrollRef   {React.RefObject}  — ref bag for scroll-to (keyed by msg.id)
 */

import React, { useState, useCallback, useEffect, useRef } from 'react';
import { CheckCheck, Check, Star, Pin, Share2, Reply } from 'lucide-react';
import MessageActionMenu from '@/components/messaging/MessageActionMenu';

// ─── Utilities ────────────────────────────────────────────────────────────────

function formatTime(iso) {
  if (!iso) return '';
  try {
    return new Date(iso).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' });
  } catch {
    return '';
  }
}

// ─── Sub-components ───────────────────────────────────────────────────────────

function DeliveryStatus({ message }) {
  if (message.read_at) {
    return (
      <span className="flex items-center gap-0.5 text-cyan-400" title="Read">
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

function ReplyPreview({ replyTo, isMine, onScrollTo }) {
  if (!replyTo) return null;
  const isDeleted = replyTo.is_deleted_for_everyone;
  const preview = isDeleted
    ? 'This message was deleted'
    : (replyTo.content || '').slice(0, 80) + ((replyTo.content?.length ?? 0) > 80 ? '…' : '');

  return (
    <button
      onClick={() => onScrollTo?.(replyTo.id)}
      className={`
        mb-1.5 px-2.5 py-1.5 rounded-xl text-left w-full max-w-full
        border-l-2 transition-colors
        ${isMine
          ? 'bg-black/20 border-black/40 hover:bg-black/30'
          : 'bg-white/5 border-accent/40 hover:bg-white/10'
        }
      `}
    >
      <p className={`text-[10px] font-semibold mb-0.5 ${isMine ? 'text-black/50' : 'text-accent/80'}`}>
        <Reply className="h-2.5 w-2.5 inline mr-1" />
        Replied to message
      </p>
      <p className={`text-[11px] truncate ${isMine ? 'text-black/60' : 'text-slate-400'} ${isDeleted ? 'italic' : ''}`}>
        {preview}
      </p>
    </button>
  );
}

function ForwardedBadge({ isMine }) {
  return (
    <div className={`flex items-center gap-1 mb-1 text-[10px] ${isMine ? 'text-black/40' : 'text-slate-500'}`}>
      <Share2 className="h-2.5 w-2.5" />
      <span>Forwarded</span>
    </div>
  );
}

// ─── Main component ───────────────────────────────────────────────────────────

export default function MessageBubble({
  message,
  isMine,
  showStatus = true,
  onReply,
  onStar,
  onPin,
  onForward,
  onDeleteForMe,
  onDeleteForEveryone,
  scrollRef,
}) {
  const [menuOpen, setMenuOpen] = useState(false);
  const [menuPosition, setMenuPosition] = useState('bottom');
  const [copied, setCopied] = useState(false);
  const bubbleRef = useRef(null);
  const copiedTimerRef = useRef(null);

  const isDeleted = message?.is_deleted_for_everyone;
  const isPinned = message?.is_pinned;
  const isStarred = message?.is_starred;
  const isForwarded = message?.is_forwarded;
  const hasReply = Boolean(message?.reply_to_message);

  const handleLongPress = useCallback(() => {
    // Detect if menu should open upward or downward
    if (bubbleRef.current) {
      const rect = bubbleRef.current.getBoundingClientRect();
      const spaceBelow = window.innerHeight - rect.bottom;
      setMenuPosition(spaceBelow < 220 ? 'top' : 'bottom');
    }
    setMenuOpen(true);
  }, []);

  const handleContextMenu = useCallback((e) => {
    e.preventDefault();
    handleLongPress();
  }, [handleLongPress]);

  const handleCopy = useCallback(async () => {
    if (!message?.content || isDeleted) return;
    try {
      await navigator.clipboard.writeText(message.content);
    } catch {
      // Fallback for non-secure contexts
      const el = document.createElement('textarea');
      el.value = message.content;
      document.body.appendChild(el);
      el.select();
      document.execCommand('copy');
      document.body.removeChild(el);
    }
    setCopied(true);
    clearTimeout(copiedTimerRef.current);
    copiedTimerRef.current = setTimeout(() => setCopied(false), 1600);
  }, [message?.content, isDeleted]);

  useEffect(() => () => clearTimeout(copiedTimerRef.current), []);

  const handleScrollTo = useCallback((msgId) => {
    const el = scrollRef?.current?.[msgId];
    el?.scrollIntoView({ behavior: 'smooth', block: 'center' });
  }, [scrollRef]);

  return (
    <div
      data-testid="message-bubble"
      data-message-id={message?.id}
      ref={(el) => {
        bubbleRef.current = el;
        if (scrollRef && message?.id) {
          scrollRef.current = scrollRef.current || {};
          scrollRef.current[message.id] = el;
        }
      }}
      className={`flex ${isMine ? 'justify-end' : 'justify-start'} px-4 group relative`}
    >
      <div className={`max-w-[75%] sm:max-w-[65%] flex flex-col ${isMine ? 'items-end' : 'items-start'} relative`}>
        {/* Pinned indicator */}
        {isPinned && (
          <div className={`flex items-center gap-1 mb-1 text-[10px] text-amber-400/70 ${isMine ? 'flex-row-reverse' : ''}`}>
            <Pin className="h-2.5 w-2.5" />
            <span>Pinned</span>
          </div>
        )}

        {/* Forwarded badge */}
        {isForwarded && !isDeleted && <ForwardedBadge isMine={isMine} />}

        {/* Message bubble */}
        <div
          className={`relative px-4 py-2.5 rounded-2xl text-sm leading-relaxed break-words whitespace-pre-wrap ${
            isDeleted
              ? isMine
                ? 'bg-white/[0.04] border border-white/10 text-slate-500 italic rounded-br-sm'
                : 'bg-white/[0.04] border border-white/10 text-slate-500 italic rounded-bl-sm'
              : isMine
                ? 'bg-accent text-black rounded-br-sm shadow-[0_2px_12px_rgba(255,143,50,0.3)]'
                : 'bg-white/[0.08] text-slate-100 border border-white/10 rounded-bl-sm'
          }`}
          onContextMenu={handleContextMenu}
        >
          {/* Reply preview */}
          {hasReply && !isDeleted && (
            <ReplyPreview
              replyTo={message.reply_to_message}
              isMine={isMine}
              onScrollTo={handleScrollTo}
            />
          )}

          {/* Content */}
          <span>{message.content}</span>

          {/* Hover action button */}
          {!isDeleted && (
            <button
              onClick={handleLongPress}
              data-testid={`message-menu-trigger-${message?.id}`}
              aria-label="Message actions"
              className={`
                absolute top-1/2 -translate-y-1/2
                ${isMine ? '-left-8' : '-right-8'}
                h-6 w-6 rounded-full bg-slate-800/90 border border-white/10
                flex items-center justify-center
                opacity-0 group-hover:opacity-100 transition-opacity duration-150
                shadow-sm hover:bg-slate-700
              `}
            >
              <span className="text-[10px] text-slate-300">···</span>
            </button>
          )}

          {/* Star badge */}
          {isStarred && !isDeleted && (
            <span className={`absolute -top-1.5 ${isMine ? '-left-1.5' : '-right-1.5'} text-[10px]`} title="Starred">
              ⭐
            </span>
          )}
        </div>

        {/* Timestamp + status */}
        <div className={`flex items-center gap-1.5 mt-1 text-[11px] text-slate-500 ${isMine ? 'flex-row-reverse' : 'flex-row'}`}>
          <span>{formatTime(message.created_at)}</span>
          {isMine && showStatus && !isDeleted && <DeliveryStatus message={message} />}
          {copied && !isDeleted && (
            <span role="status" className="text-emerald-400">Copied</span>
          )}
        </div>

        {/* Action menu */}
        <MessageActionMenu
          message={message}
          isMine={isMine}
          isOpen={menuOpen}
          position={menuPosition}
          onClose={() => setMenuOpen(false)}
          onReply={() => onReply?.(message)}
          onCopy={handleCopy}
          onStar={() => onStar?.(message)}
          onPin={() => onPin?.(message)}
          onForward={() => onForward?.(message)}
          onDeleteForMe={() => onDeleteForMe?.(message)}
          onDeleteForEveryone={() => onDeleteForEveryone?.(message)}
        />
      </div>
    </div>
  );
}
