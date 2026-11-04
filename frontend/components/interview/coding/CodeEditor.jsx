'use client';

import dynamic from 'next/dynamic';
import EditorLoading from '@/components/interview/coding/EditorLoading';

/** Monaco touches `window`, so it is loaded only in the browser — never during server rendering. */
const CodeEditor = dynamic(() => import('@/components/interview/coding/MonacoCodeEditor'), {
  ssr: false,
  loading: EditorLoading,
});

export default CodeEditor;
