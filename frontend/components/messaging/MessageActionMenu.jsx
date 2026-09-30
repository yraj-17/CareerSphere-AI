'use client';

/**
 * MessageActionMenu — contextual action menu for a single message bubble.
 *
 * Renders as a polished popover triggered by hovering/long-pressing a message.
 *
 * Actions:
 *   Reply    — always visible
 *   Copy     — always visible
 *   Star     — always visible (toggle)
 *   Pin      — always visible (toggle)
 *   Forward  — always visible
 *   Delete for me      — always visible
 *   Delete for everyone — only visible to message sender
 *
 * Design:
 *   - Dark glassmorphism panel with smooth fade-in
 *   - Compact icon+label layout
 *   - Danger actions visually separated with rose accent
 *   - Fully accessible with aria-labels and keyboard support
 */

import React, { useCallback, useRef, useEffect } from 'react';
import {
  Reply,
  Copy,
  Star,
  Pin,
  Share2,
  Trash2,
  CheckCircle,
  PinOff,
  StarOff,
} from 'lucide-react';

function MenuItem({ icon: Icon, label, onClick, danger = false, disabled = false, id }) {
  return (
    <button
      id={id}
      onClick={onClick}
      disabled={disabled}
      aria-label={label}
      className={`
        flex items-center gap-2.5 w-full px-3 py-2 text-xs rounded-lg
        transition-all duration-150 group
        ${danger
          ? 'text-rose-400 hover:bg-rose-500/15 hover:text-rose-300'
          : 'text-slate-300 hover:bg-white/10 hover:text-white'
        }
        ${disabled ? 'opacity-40 cursor-not-allowed pointer-events-none' : 'cursor-pointer'}
      `}
    >
      <Icon className="h-3.5 w-3.5 flex-shrink-0" />
      <span className="font-medium">{label}</span>
    </button>
  );
}

function Divider() {
  return <div className="h-px bg-white/10 my-1 mx-2" />;
}

export default function MessageActionMenu({
  message,
  isMine,
  isOpen,
  position = 'bottom',   // 'top' | 'bottom'
  onClose,
  onReply,
  onCopy,
  onStar,
  onPin,
  onForward,
  onDeleteForMe,
  onDeleteForEveryone,
}) {
  const menuRef = useRef(null);

  // Close on outside click
  useEffect(() => {
    if (!isOpen) return;
    const handleClick = (e) => {
      if (menuRef.current && !menuRef.current.contains(e.target)) {
        onClose?.();
      }
    };
    const handleKeyDown = (e) => {
      if (e.key === 'Escape') onClose?.();
    };
    document.addEventListener('mousedown', handleClick);
    document.addEventListener('keydown', handleKeyDown);
    return () => {
      document.removeEventListener('mousedown', handleClick);
      document.removeEventListener('keydown', handleKeyDown);
    };
  }, [isOpen, onClose]);

  if (!isOpen) return null;

  const isStarred = message?.is_starred;
  const isPinned = message?.is_pinned;
  const isDeleted = message?.is_deleted_for_everyone;

  const posClass = position === 'top'
    ? 'bottom-full mb-1'
    : 'top-full mt-1';

  const alignClass = isMine ? 'right-0' : 'left-0';

  return (
    <div
      ref={menuRef}
      data-testid="message-action-menu"
      className={`
        absolute ${posClass} ${alignClass} z-50
        w-44 py-1.5 px-1
        bg-slate-900/95 backdrop-blur-xl
        border border-white/10 rounded-2xl
        shadow-[0_8px_32px_rgba(0,0,0,0.5)]
        animate-in fade-in zoom-in-95 duration-100
      `}
      role="menu"
      aria-label="Message actions"
    >
      {/* Reply */}
      <MenuItem
        id={`msg-action-reply-${message?.id}`}
        icon={Reply}
        label="Reply"
        onClick={() => { onReply?.(); onClose?.(); }}
        disabled={isDeleted}
      />

      {/* Copy */}
      <MenuItem
        id={`msg-action-copy-${message?.id}`}
        icon={Copy}
        label="Copy Text"
        onClick={() => { onCopy?.(); onClose?.(); }}
        disabled={isDeleted}
      />

      {/* Star / Unstar */}
      <MenuItem
        id={`msg-action-star-${message?.id}`}
        icon={isStarred ? StarOff : Star}
        label={isStarred ? 'Unstar' : 'Star'}
        onClick={() => { onStar?.(); onClose?.(); }}
        disabled={isDeleted}
      />

      {/* Pin / Unpin */}
      <MenuItem
        id={`msg-action-pin-${message?.id}`}
        icon={isPinned ? PinOff : Pin}
        label={isPinned ? 'Unpin' : 'Pin'}
        onClick={() => { onPin?.(); onClose?.(); }}
        disabled={isDeleted}
      />

      {/* Forward */}
      <MenuItem
        id={`msg-action-forward-${message?.id}`}
        icon={Share2}
        label="Forward"
        onClick={() => { onForward?.(); onClose?.(); }}
        disabled={isDeleted}
      />

      <Divider />

      {/* Delete for me */}
      <MenuItem
        id={`msg-action-delete-me-${message?.id}`}
        icon={Trash2}
        label="Delete for Me"
        onClick={() => { onDeleteForMe?.(); onClose?.(); }}
        danger
      />

      {/* Delete for everyone — only sender */}
      {isMine && !isDeleted && (
        <MenuItem
          id={`msg-action-delete-all-${message?.id}`}
          icon={Trash2}
          label="Delete for Everyone"
          onClick={() => { onDeleteForEveryone?.(); onClose?.(); }}
          danger
        />
      )}
    </div>
  );
}
