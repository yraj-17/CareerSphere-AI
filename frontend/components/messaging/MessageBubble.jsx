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
import Link from 'next/link';
import { CheckCheck, Check, ExternalLink, MoreVertical, Star, Pin, Share2, Reply } from 'lucide-react';
import MessageActionMenu from '@/components/messaging/MessageActionMenu';
import { formatMessageTime } from '@/components/messaging/messageDateUtils';

// ─── Utilities ────────────────────────────────────────────────────────────────

// ─── Sub-components ───────────────────────────────────────────────────────────

function DeliveryStatus({ message, isMine }) {
  if (message.read_at) {
    return (
      <span className={`flex items-center gap-0.5 ${isMine ? 'text-white/80' : 'text-brand-500'}`} title="Read">
        <CheckCheck className="h-3 w-3" />
      </span>
    );
  }
  if (message.delivered_at) {
    return (
      <span className={`flex items-center gap-0.5 ${isMine ? 'text-white/70' : 'text-slate-400'}`} title="Delivered">
        <CheckCheck className="h-3 w-3" />
      </span>
    );
  }
  return (
    <span className={`flex items-center gap-0.5 ${isMine ? 'text-white/70' : 'text-slate-500'}`} title="Sent">
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
          ? 'bg-white/15 border-white/30 hover:bg-white/20'
          : 'bg-brand-50 border-brand-200 hover:bg-brand-100'
        }
      `}
    >
      <p className={`mb-0.5 text-[10px] font-semibold ${isMine ? 'text-white/75' : 'text-brand-700'}`}>
        <Reply className="h-2.5 w-2.5 inline mr-1" />
        Replied to message
      </p>
      <p className={`truncate text-[11px] ${isMine ? 'text-white/80' : 'text-slate-600'} ${isDeleted ? 'italic' : ''}`}>
        {preview}
      </p>
    </button>
  );
}

function ForwardedBadge({ isMine }) {
  return (
    <div className={`mb-1 flex items-center gap-1 text-[10px] ${isMine ? 'text-white/70' : 'text-slate-500'}`}>
      <Share2 className="h-2.5 w-2.5" />
      <span>Forwarded</span>
    </div>
  );
}

function ResourceShareCard({ resource, isMine }) {
  if (!resource) {
    return (
      <div className={`mt-2 rounded-2xl border px-3 py-3 text-sm ${
        isMine ? 'border-white/25 bg-white/10 text-white/85' : 'border-slate-200 bg-slate-50 text-slate-700'
      }`}>
        <p className="font-semibold">Resource no longer available.</p>
        <p className="mt-1 text-xs opacity-70">The original shared resource was deleted.</p>
      </div>
    );
  }

  return (
    <div className={`mt-2 min-w-[230px] overflow-hidden rounded-2xl border ${
      isMine ? 'border-white/25 bg-white/10' : 'border-slate-200 bg-white'
    }`}>
      <div className="p-3">
        <p className={`text-[10px] font-bold uppercase tracking-[0.16em] ${isMine ? 'text-white/80' : 'text-brand-600'}`}>
          {resource.resource_type?.replaceAll('_', ' ') || 'Resource'}
        </p>
        <h3 className={`mt-1 line-clamp-2 text-sm font-bold ${isMine ? 'chat-inverse' : 'text-slate-900'}`}>
          {resource.title}
        </h3>
        {resource.description && (
          <p className={`mt-1 line-clamp-2 text-xs leading-relaxed ${isMine ? 'text-white/80' : 'text-slate-600'}`}>
            {resource.description}
          </p>
        )}
        <div className="mt-2 flex flex-wrap gap-1.5">
          {(resource.tags || []).slice(0, 3).map((tag) => (
            <span key={tag.toLowerCase()} className={`rounded-full px-2 py-0.5 text-[10px] ${
              isMine ? 'bg-white/15 text-white/80' : 'bg-slate-100 text-slate-600'
            }`}>
              {tag}
            </span>
          ))}
        </div>
        <p className={`mt-2 truncate text-[10px] ${isMine ? 'text-white/70' : 'text-slate-500'}`}>
          {[resource.category, resource.source_domain].filter(Boolean).join(' · ')}
        </p>
      </div>
      <Link
        href={`/dashboard/resources/${resource.id}`}
        className={`flex items-center justify-center gap-2 border-t px-3 py-2 text-xs font-bold ${
          isMine
            ? 'border-white/20 text-white hover:bg-white/10'
            : 'border-slate-200 text-brand-600 hover:bg-brand-50'
        }`}
      >
        Open Resource
        <ExternalLink className="h-3 w-3" />
      </Link>
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
  const isResourceShare = message?.message_type === 'RESOURCE_SHARE';

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
      className={`group relative flex ${isMine ? 'justify-end' : 'justify-start'} px-4 sm:px-6`}
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
                ? 'bg-slate-100 border border-slate-200 text-slate-500 italic rounded-br-sm'
                : 'bg-slate-100 border border-slate-200 text-slate-500 italic rounded-bl-sm'
              : isMine
                ? 'chat-inverse bg-brand-500 rounded-br-sm shadow-[0_2px_10px_rgba(16,47,107,0.18)]'
                : 'bg-slate-100 text-slate-800 border border-slate-200 rounded-bl-sm'
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
          {message.content && <span>{message.content}</span>}
          {isResourceShare && !isDeleted && (
            <ResourceShareCard resource={message.resource} isMine={isMine} />
          )}

          {/* Keep metadata inside the bubble, like WhatsApp. */}
          <span
            className={`ml-2 inline-flex translate-y-[2px] items-center gap-1 align-baseline text-[10px] leading-none ${
              isDeleted ? 'text-slate-400' : isMine ? 'text-white/70' : 'text-slate-500'
            }`}
          >
            {isStarred && !isDeleted && (
              <Star
                className="h-3 w-3 fill-yellow-400 text-yellow-500 drop-shadow-[0_1px_1px_rgba(161,98,7,0.25)]"
                aria-label="Starred"
                role="img"
              />
            )}
            <span>{formatMessageTime(message.created_at)}</span>
            {isMine && showStatus && !isDeleted && <DeliveryStatus message={message} isMine={isMine} />}
          </span>

          {/* Hover action button */}
          {!isDeleted && (
            <button
              onClick={handleLongPress}
              data-testid={`message-menu-trigger-${message?.id}`}
              aria-label="Message actions"
              className={`
                absolute top-1/2 -translate-y-1/2
                ${isMine ? '-left-8' : '-right-8'}
                h-6 w-6 rounded-full bg-white border border-slate-200
                flex items-center justify-center
                opacity-100 transition-opacity duration-150
                md:opacity-0 md:group-hover:opacity-100
                shadow-sm hover:bg-slate-100 focus:outline-none focus-visible:ring-2 focus-visible:ring-brand-200
              `}
            >
              <MoreVertical className="h-4 w-4 text-slate-400" aria-hidden="true" />
            </button>
          )}

        </div>

        {copied && !isDeleted && (
          <span role="status" className="mt-1 text-[11px] text-emerald-600">Copied</span>
        )}

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
