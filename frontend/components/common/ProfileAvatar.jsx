'use client';

import React, { useEffect, useState } from 'react';

function initialsFromName({ name, firstName, lastName, username, fallback = 'U' }) {
  const source = name || [firstName, lastName].filter(Boolean).join(' ') || username || fallback;
  const initials = source
    .split(' ')
    .filter(Boolean)
    .slice(0, 2)
    .map((part) => part[0])
    .join('')
    .toUpperCase();

  return initials || fallback;
}

export default function ProfileAvatar({
  src,
  name,
  firstName,
  lastName,
  username,
  alt,
  fallback,
  className = 'h-8 w-8',
  fallbackClassName = 'border border-accent/35 bg-accent/15 text-xs font-bold uppercase text-accent',
  imageClassName = '',
}) {
  const [failed, setFailed] = useState(false);
  const displayName = name || [firstName, lastName].filter(Boolean).join(' ') || username || 'User';
  const initials = fallback || initialsFromName({ name, firstName, lastName, username });
  const showImage = Boolean(src) && !failed;

  useEffect(() => {
    setFailed(false);
  }, [src]);

  return (
    <span
      className={`flex shrink-0 items-center justify-center overflow-hidden rounded-full ${className} ${
        showImage ? '' : fallbackClassName
      }`}
    >
      {showImage ? (
        // eslint-disable-next-line @next/next/no-img-element
        <img
          src={src}
          alt={alt || displayName}
          className={`h-full w-full object-cover ${imageClassName}`}
          onError={() => setFailed(true)}
        />
      ) : (
        <span aria-label={displayName}>{initials}</span>
      )}
    </span>
  );
}
