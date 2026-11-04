'use client';

/**
 * Monaco Editor, self-hosted: the AMD bundle is served from /monaco/vs (copied from
 * node_modules by scripts/copy-monaco.js), so no CDN is involved. Load this module only
 * on the client (CodeEditor.jsx wraps it in next/dynamic with ssr: false).
 */
import React, { useCallback, useEffect, useRef } from 'react';
import Editor, { loader } from '@monaco-editor/react';
import EditorLoading from '@/components/interview/coding/EditorLoading';

export const MONACO_BASE_PATH = '/monaco/vs';
loader.config({ paths: { vs: MONACO_BASE_PATH } });

export const THEME_NAME = 'careersphere-dark';

/** CareerSphere navy/amber palette on top of Monaco's dark base theme. */
export function defineCareerSphereTheme(monaco) {
  monaco.editor.defineTheme(THEME_NAME, {
    base: 'vs-dark',
    inherit: true,
    rules: [
      { token: 'comment', foreground: '7C8BA1', fontStyle: 'italic' },
      { token: 'keyword', foreground: 'D6B875' },
      { token: 'string', foreground: '9BD3AE' },
      { token: 'number', foreground: 'F2A37B' },
      { token: 'type', foreground: '8CC8FF' },
    ],
    colors: {
      'editor.background': '#101B2D',
      'editor.foreground': '#E6EAF2',
      'editorLineNumber.foreground': '#4F5E78',
      'editorLineNumber.activeForeground': '#C6A15B',
      'editor.lineHighlightBackground': '#17243A',
      'editor.selectionBackground': '#C6A15B44',
      'editorCursor.foreground': '#D6B875',
      'editorIndentGuide.background1': '#22324D',
      'editorBracketMatch.border': '#C6A15B',
      'editorGutter.background': '#101B2D',
    },
  });
}

export function editorOptions({ fontSize = 14, wordWrap = false, readOnly = false, tabSize = 4 } = {}) {
  return {
    fontSize,
    fontFamily: "'JetBrains Mono', 'Fira Code', Consolas, 'Courier New', monospace",
    lineNumbers: 'on',
    automaticLayout: true, // follows panel resizing
    autoIndent: 'full',
    tabSize,
    insertSpaces: true,
    detectIndentation: false,
    matchBrackets: 'always',
    bracketPairColorization: { enabled: true },
    guides: { bracketPairs: true, indentation: true },
    folding: true,
    showFoldingControls: 'mouseover',
    formatOnPaste: true,
    autoClosingBrackets: 'languageDefined',
    autoClosingQuotes: 'languageDefined',
    minimap: { enabled: false },
    scrollBeyondLastLine: false,
    wordWrap: wordWrap ? 'on' : 'off',
    renderWhitespace: 'selection',
    smoothScrolling: true,
    readOnly,
    padding: { top: 12, bottom: 12 },
    ariaLabel: 'Code editor',
  };
}

/** Monaco ships a built-in formatter only for these of our languages. */
export const FORMATTABLE_LANGUAGES = new Set(['javascript']);

export default function MonacoCodeEditor({
  path,
  language,
  value,
  onChange,
  readOnly = false,
  fontSize = 14,
  wordWrap = false,
  onRunShortcut,
  onEditorReady,
}) {
  const runRef = useRef(onRunShortcut);
  useEffect(() => {
    runRef.current = onRunShortcut;
  }, [onRunShortcut]);

  const handleMount = useCallback(
    (editor, monaco) => {
      // Ctrl/Cmd + Enter runs the code (never submits).
      editor.addCommand(monaco.KeyMod.CtrlCmd | monaco.KeyCode.Enter, () => runRef.current?.());
      onEditorReady?.(editor);
    },
    [onEditorReady]
  );

  return (
    <Editor
      // One model per question + language: switching keeps each buffer and its undo history.
      path={path}
      language={language}
      value={value}
      theme={THEME_NAME}
      beforeMount={defineCareerSphereTheme}
      onMount={handleMount}
      onChange={(next) => onChange?.(next ?? '')}
      options={editorOptions({ fontSize, wordWrap, readOnly, tabSize: language === 'javascript' ? 2 : 4 })}
      loading={<EditorLoading />}
      height="100%"
    />
  );
}
