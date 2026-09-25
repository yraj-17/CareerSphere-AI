'use client';

/**
 * TypingIndicator — shows the animated "…is typing" dots.
 *
 * Props:
 *   name {string} — first name of the person typing (optional)
 */

import React from 'react';

export default function TypingIndicator({ name }) {
  return (
    <div data-testid="typing-indicator" className="flex justify-start px-4 py-1">
      <div className="flex items-center gap-2 bg-white/[0.06] border border-white/10 rounded-2xl rounded-bl-sm px-3.5 py-2">
        {/* Three animated dots */}
        <span className="flex items-center gap-1" aria-label={`${name || 'Someone'} is typing`}>
          {[0, 1, 2].map((i) => (
            <span
              key={i}
              className="h-1.5 w-1.5 rounded-full bg-slate-400 inline-block"
              style={{
                animation: `typingBounce 1.2s ease-in-out ${i * 0.2}s infinite`,
              }}
            />
          ))}
        </span>
        {name && (
          <span className="text-xs text-slate-400 ml-0.5">{name} is typing</span>
        )}
      </div>

      <style jsx>{`
        @keyframes typingBounce {
          0%, 80%, 100% { transform: translateY(0); opacity: 0.4; }
          40% { transform: translateY(-5px); opacity: 1; }
        }
      `}</style>
    </div>
  );
}
