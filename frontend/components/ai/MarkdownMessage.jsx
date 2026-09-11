'use client';

import React, { useMemo } from 'react';

function parseBlocks(text) {
  const source = text || '';
  const parts = [];
  const fence = /```([a-zA-Z0-9_-]*)\n?([\s\S]*?)```/g;
  let lastIndex = 0;
  let match;

  while ((match = fence.exec(source)) !== null) {
    if (match.index > lastIndex) {
      parts.push({ type: 'text', value: source.slice(lastIndex, match.index) });
    }
    parts.push({ type: 'code', language: match[1] || '', value: match[2].replace(/\n$/, '') });
    lastIndex = fence.lastIndex;
  }

  if (lastIndex < source.length) {
    parts.push({ type: 'text', value: source.slice(lastIndex) });
  }

  return parts.length ? parts : [{ type: 'text', value: source }];
}

function renderInline(text, keyPrefix) {
  const nodes = [];
  const pattern = /(`[^`]+`|\*\*[^*]+\*\*)/g;
  let last = 0;
  let match;
  let index = 0;

  while ((match = pattern.exec(text)) !== null) {
    if (match.index > last) {
      nodes.push(<React.Fragment key={`${keyPrefix}-t-${index}`}>{text.slice(last, match.index)}</React.Fragment>);
      index += 1;
    }
    const token = match[0];
    if (token.startsWith('`')) {
      nodes.push(
        <code
          key={`${keyPrefix}-c-${index}`}
          className="rounded bg-slate-950/80 px-1.5 py-0.5 font-mono text-[12px] text-cyan-200"
        >
          {token.slice(1, -1)}
        </code>
      );
    } else {
      nodes.push(
        <strong key={`${keyPrefix}-b-${index}`} className="font-semibold text-white">
          {token.slice(2, -2)}
        </strong>
      );
    }
    index += 1;
    last = pattern.lastIndex;
  }

  if (last < text.length) {
    nodes.push(<React.Fragment key={`${keyPrefix}-t-end`}>{text.slice(last)}</React.Fragment>);
  }

  return nodes;
}

function TextBlock({ value }) {
  const lines = value.replace(/\r\n/g, '\n').split('\n');
  const elements = [];
  let list = [];
  let listType = null;
  let paragraph = [];

  const flushParagraph = () => {
    if (!paragraph.length) return;
    const text = paragraph.join(' ').trim();
    if (text) {
      elements.push(
        <p key={`p-${elements.length}`} className="leading-relaxed">
          {renderInline(text, `p-${elements.length}`)}
        </p>
      );
    }
    paragraph = [];
  };

  const flushList = () => {
    if (!list.length) return;
    const Tag = listType === 'ol' ? 'ol' : 'ul';
    const cls = listType === 'ol' ? 'list-decimal pl-5 space-y-1' : 'list-disc pl-5 space-y-1';
    elements.push(
      <Tag key={`l-${elements.length}`} className={cls}>
        {list.map((item, idx) => (
          <li key={idx}>{renderInline(item, `li-${elements.length}-${idx}`)}</li>
        ))}
      </Tag>
    );
    list = [];
    listType = null;
  };

  lines.forEach((line) => {
    const bullet = line.match(/^\s*[-*]\s+(.+)$/);
    const numbered = line.match(/^\s*\d+\.\s+(.+)$/);
    if (bullet) {
      flushParagraph();
      if (listType && listType !== 'ul') flushList();
      listType = 'ul';
      list.push(bullet[1]);
      return;
    }
    if (numbered) {
      flushParagraph();
      if (listType && listType !== 'ol') flushList();
      listType = 'ol';
      list.push(numbered[1]);
      return;
    }
    if (!line.trim()) {
      flushParagraph();
      flushList();
      return;
    }
    flushList();
    paragraph.push(line.trim());
  });

  flushParagraph();
  flushList();
    return <div className="space-y-3">{elements}</div>;
}

export default function MarkdownMessage({ content }) {
  const blocks = useMemo(() => parseBlocks(content), [content]);

  return (
    <div className="space-y-3 text-sm sm:text-[15px] text-slate-200">
      {blocks.map((block, index) => {
        if (block.type === 'code') {
          return (
            <pre
              key={index}
              className="overflow-x-auto rounded-xl border border-white/10 bg-slate-950/90 p-3 font-mono text-xs text-slate-200"
            >
              <code>{block.value}</code>
            </pre>
          );
        }
        return <TextBlock key={index} value={block.value} />;
      })}
    </div>
  );
}
