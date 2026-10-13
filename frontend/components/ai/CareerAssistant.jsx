'use client';

import React, { useCallback, useEffect, useMemo, useRef, useState } from 'react';
import Link from 'next/link';
import {
  AlertCircle,
  ArrowUp,
  Bot,
  Loader2,
  PanelLeftOpen,
  Sparkles,
  UserCheck,
  X,
} from 'lucide-react';
import { useAuth } from '@/context/AuthContext';
import ProfileAvatar from '@/components/common/ProfileAvatar';
import {
  checkGrammar,
  createConversation,
  deleteConversation,
  extractErrorMessage,
  getConversation,
  getConversations,
  retryConversationMessage,
  sendConversationMessage,
  updateConversation,
} from '@/services/api';
import ConversationSidebar from '@/components/ai/ConversationSidebar';
import GrammarSuggestions from '@/components/ai/GrammarSuggestions';
import MarkdownMessage from '@/components/ai/MarkdownMessage';

const promptSuggestions = [
  'Help me prepare for a technical interview.',
  'Review my resume strategy.',
  'Build a practical career roadmap.',
  'Which skills should I learn next?',
];

function getAIErrorMessage(error) {
  if (error?.code === 'ECONNABORTED') {
    return 'The AI is taking longer than expected. Please try again.';
  }
  if (!error?.response) {
    return 'Unable to reach the CareerSphere backend. Please try again later.';
  }
  if (error.response.status === 503) {
    const detail = error.response.data?.detail;
    if (typeof detail === 'string' && detail.toLowerCase().includes('languagetool')) {
      return 'Grammar checking is currently unavailable. Please try again in a moment.';
    }
    if (typeof detail === 'string' && detail.toLowerCase().includes('taking longer')) {
      return detail;
    }
    return 'AI service is currently unavailable. Please try again later.';
  }
  if (error.response.status === 404) {
    return 'That conversation could not be found.';
  }
  return extractErrorMessage(error);
}

function getUserName(user) {
  return [user?.first_name, user?.last_name].filter(Boolean).join(' ') || user?.username || 'Profile';
}

export default function CareerAssistant() {
  const { user } = useAuth();
  const [conversations, setConversations] = useState([]);
  const [activeConversationId, setActiveConversationId] = useState(null);
  const [messages, setMessages] = useState([]);
  const [title, setTitle] = useState('New chat');
  const [prompt, setPrompt] = useState('');
  const [useProfile, setUseProfile] = useState(false);
  const [error, setError] = useState('');
  const [fieldError, setFieldError] = useState('');
  const [listError, setListError] = useState('');
  const [isListLoading, setIsListLoading] = useState(true);
  const [isMessagesLoading, setIsMessagesLoading] = useState(false);
  const [isSubmitting, setIsSubmitting] = useState(false);
  const [canRetry, setCanRetry] = useState(false);
  const [sidebarOpen, setSidebarOpen] = useState(() => (
    typeof window === 'undefined' ? true : window.innerWidth >= 1024
  ));
  const [grammarResult, setGrammarResult] = useState(null);
  const [isCheckingGrammar, setIsCheckingGrammar] = useState(false);
  const [grammarError, setGrammarError] = useState('');
  const [pendingDelete, setPendingDelete] = useState(null);
  const messagesEndRef = useRef(null);
  const messagesViewportRef = useRef(null);
  const composerRef = useRef(null);
  const shouldStickToBottomRef = useRef(true);

  const userName = getUserName(user);
  const userInitial = (user?.first_name?.[0] || user?.username?.[0] || 'U').toUpperCase();

  const upsertConversation = useCallback((summary) => {
    if (!summary?.id) return;
    setConversations((current) => {
      const previous = current.find((item) => item.id === summary.id);
      const remaining = current.filter((item) => item.id !== summary.id);
      return [{ ...previous, ...summary }, ...remaining];
    });
  }, []);

  const loadConversations = useCallback(async () => {
    setIsListLoading(true);
    setListError('');
    try {
      const data = await getConversations();
      setConversations(Array.isArray(data) ? data : []);
    } catch (err) {
      setListError(getAIErrorMessage(err));
    } finally {
      setIsListLoading(false);
    }
  }, []);

  useEffect(() => {
    loadConversations();
  }, [loadConversations]);

  useEffect(() => {
    if (!shouldStickToBottomRef.current) return;
    requestAnimationFrame(() => messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' }));
  }, [messages, isSubmitting]);

  useEffect(() => {
    document.body.style.overflow = sidebarOpen && window.innerWidth < 1024 ? 'hidden' : '';
    return () => {
      document.body.style.overflow = '';
    };
  }, [sidebarOpen]);

  useEffect(() => {
    const handleKeyDown = (event) => {
      if (event.key === 'Escape') {
        if (pendingDelete) setPendingDelete(null);
        else if (window.innerWidth < 1024 && sidebarOpen) setSidebarOpen(false);
      }
    };
    document.addEventListener('keydown', handleKeyDown);
    return () => document.removeEventListener('keydown', handleKeyDown);
  }, [pendingDelete, sidebarOpen]);

  const startNewChat = () => {
    setActiveConversationId(null);
    setMessages([]);
    setTitle('New chat');
    setError('');
    setFieldError('');
    setCanRetry(false);
    setUseProfile(false);
    setGrammarResult(null);
    setGrammarError('');
    if (window.innerWidth < 1024) setSidebarOpen(false);
    shouldStickToBottomRef.current = true;
    requestAnimationFrame(() => composerRef.current?.focus());
  };

  const openConversation = async (conversationId) => {
    if (!conversationId || isSubmitting) return;
    setActiveConversationId(conversationId);
    if (window.innerWidth < 1024) setSidebarOpen(false);
    setIsMessagesLoading(true);
    setError('');
    setCanRetry(false);
    shouldStickToBottomRef.current = true;
    try {
      const data = await getConversation(conversationId);
      setTitle(data.title || 'Conversation');
      setMessages(Array.isArray(data.messages) ? data.messages : []);
      upsertConversation(data);
      const last = data.messages?.[data.messages.length - 1];
      setCanRetry(last?.role === 'user');
    } catch (err) {
      setError(getAIErrorMessage(err));
    } finally {
      setIsMessagesLoading(false);
    }
  };

  const handleConversationUpdate = async (conversationId, changes) => {
    const previous = conversations.find((item) => item.id === conversationId);
    const optimistic = { ...previous, ...changes };
    upsertConversation(optimistic);
    try {
      const updated = await updateConversation(conversationId, changes);
      upsertConversation(updated);
    } catch (err) {
      if (previous) upsertConversation(previous);
      setError(getAIErrorMessage(err));
      throw err;
    }
  };

  const handleRename = async (conversationId, nextTitle) => {
    try {
      const updated = await updateConversation(conversationId, { title: nextTitle });
      upsertConversation(updated);
      if (activeConversationId === conversationId) setTitle(updated.title);
    } catch (err) {
      setError(getAIErrorMessage(err));
      throw err;
    }
  };

  const handleDeleteRequest = (conversation) => {
    if (!isSubmitting) setPendingDelete(conversation);
  };

  const confirmDelete = async () => {
    if (!pendingDelete || isSubmitting) return;
    const conversationId = pendingDelete.id;
    try {
      await deleteConversation(conversationId);
      setConversations((current) => current.filter((item) => item.id !== conversationId));
      if (activeConversationId === conversationId) startNewChat();
      setPendingDelete(null);
    } catch (err) {
      setError(getAIErrorMessage(err));
      setPendingDelete(null);
    }
  };

  const applySendPayload = (payload) => {
    if (payload?.conversation) {
      upsertConversation(payload.conversation);
      setActiveConversationId(payload.conversation.id);
      setTitle(payload.conversation.title || 'Conversation');
    }

    setMessages((current) => {
      const withoutOptimistic = current.filter((item) => !item.id?.startsWith?.('temp-'));
      const next = [...withoutOptimistic];
      if (payload?.user_message && !next.some((item) => item.id === payload.user_message.id)) {
        next.push(payload.user_message);
      }
      if (payload?.assistant_message) next.push(payload.assistant_message);
      return next;
    });

    if (payload?.error) {
      setError(payload.error);
      setCanRetry(true);
      return;
    }

    setError('');
    setCanRetry(!payload?.assistant_message);
  };

  const handleSubmit = async (event) => {
    event.preventDefault();
    const trimmedPrompt = prompt.trim();
    if (!trimmedPrompt) {
      setFieldError('Please enter a career question before asking the AI.');
      setError('');
      return;
    }
    if (isSubmitting) return;

    setFieldError('');
    setError('');
    setCanRetry(false);
    setIsSubmitting(true);
    setGrammarResult(null);
    setGrammarError('');
    shouldStickToBottomRef.current = true;

    const optimistic = {
      id: `temp-${Date.now()}`,
      conversation_id: activeConversationId || 'pending',
      role: 'user',
      content: trimmedPrompt,
      created_at: new Date().toISOString(),
    };
    setMessages((current) => [...current, optimistic]);
    setPrompt('');

    try {
      const payload = activeConversationId
        ? await sendConversationMessage(activeConversationId, trimmedPrompt, useProfile)
        : await createConversation(trimmedPrompt, useProfile);
      applySendPayload(payload);
    } catch (err) {
      setMessages((current) => current.filter((item) => item.id !== optimistic.id));
      setPrompt(trimmedPrompt);
      setError(getAIErrorMessage(err));
    } finally {
      setIsSubmitting(false);
    }
  };

  const handleRetry = async () => {
    if (!activeConversationId || isSubmitting) return;
    setIsSubmitting(true);
    setError('');
    shouldStickToBottomRef.current = true;
    try {
      const payload = await retryConversationMessage(activeConversationId);
      applySendPayload(payload);
    } catch (err) {
      setError(getAIErrorMessage(err));
      setCanRetry(true);
    } finally {
      setIsSubmitting(false);
    }
  };

  const handleGrammarCheck = async () => {
    const text = prompt.trim();
    if (!text) {
      setFieldError('Enter a message to check before using grammar suggestions.');
      return;
    }
    if (isCheckingGrammar || isSubmitting) return;

    setGrammarError('');
    setGrammarResult(null);
    setIsCheckingGrammar(true);
    try {
      const result = await checkGrammar(text);
      setGrammarResult(result);
    } catch (err) {
      setGrammarError(getAIErrorMessage(err));
    } finally {
      setIsCheckingGrammar(false);
    }
  };

  const applyGrammarCorrections = () => {
    if (!grammarResult?.corrected_text) return;
    setPrompt(grammarResult.corrected_text);
    setGrammarResult(null);
    requestAnimationFrame(() => composerRef.current?.focus());
  };

  const handlePromptChange = (event) => {
    setPrompt(event.target.value);
    if (fieldError) setFieldError('');
    event.target.style.height = 'auto';
    event.target.style.height = `${Math.min(event.target.scrollHeight, 160)}px`;
  };

  const emptyState = useMemo(
    () => !isMessagesLoading && messages.length === 0 && !isSubmitting,
    [isMessagesLoading, messages.length, isSubmitting]
  );

  return (
    <div data-testid="ai-chat-shell" className="flex h-[100dvh] min-h-0 w-full overflow-hidden bg-white text-slate-900">
      <aside className={`hidden h-full shrink-0 overflow-hidden border-r border-slate-200 bg-slate-50 transition-[width] duration-200 lg:block ${sidebarOpen ? 'w-[280px]' : 'w-0 border-r-0'}`}>
        <div className="flex h-full w-[280px] flex-col">
          <div className="min-h-0 flex-1">
            <ConversationSidebar
              conversations={conversations}
              activeConversationId={activeConversationId}
              isLoading={isListLoading}
              onNewChat={startNewChat}
              onSelect={openConversation}
              onRename={handleRename}
              onUpdate={handleConversationUpdate}
              onDelete={handleDeleteRequest}
              onCollapse={() => setSidebarOpen(false)}
            />
          </div>
          {listError ? <p className="border-t border-red-100 bg-red-50 px-4 py-3 text-xs text-red-700">{listError}</p> : null}
        </div>
      </aside>

      {sidebarOpen ? (
        <div className="fixed inset-0 z-40 lg:hidden" role="dialog" aria-modal="true" aria-label="Conversation history">
          <button type="button" className="absolute inset-0 bg-black/40" aria-label="Close conversations" onClick={() => setSidebarOpen(false)} />
          <div className="absolute inset-y-0 left-0 flex w-[min(280px,88vw)] flex-col shadow-[16px_0_32px_rgba(11,42,91,0.14)]">
            <div className="min-h-0 flex-1">
              <ConversationSidebar
                conversations={conversations}
                activeConversationId={activeConversationId}
                isLoading={isListLoading}
                onNewChat={startNewChat}
                onSelect={openConversation}
                onRename={handleRename}
                onUpdate={handleConversationUpdate}
                onDelete={handleDeleteRequest}
                onClose={() => setSidebarOpen(false)}
                onCollapse={() => setSidebarOpen(false)}
              />
            </div>
            {listError ? <p className="border-t border-red-100 bg-red-50 px-4 py-3 text-xs text-red-700">{listError}</p> : null}
          </div>
        </div>
      ) : null}

      <section className="flex min-h-0 min-w-0 flex-1 flex-col">
        <header className="flex h-14 shrink-0 items-center justify-between gap-3 border-b border-slate-200 bg-white px-3 sm:px-5">
          <div className="flex min-w-0 items-center gap-2">
            {!sidebarOpen ? (
              <button type="button" onClick={() => setSidebarOpen(true)} aria-label="Show conversation history" title="Open sidebar" className="flex h-9 w-9 shrink-0 items-center justify-center rounded-lg text-slate-500 hover:bg-brand-50 hover:text-brand-600 focus:outline-none focus-visible:ring-2 focus-visible:ring-brand-200">
                <PanelLeftOpen className="h-5 w-5" />
              </button>
            ) : null}
            <div className="min-w-0">
              <p className="truncate text-sm font-semibold text-slate-900">{title}</p>
              <p className="hidden truncate text-[11px] text-slate-500 sm:block">Career assistant</p>
            </div>
          </div>
          <div className="flex items-center gap-2">
            <span className="hidden items-center gap-1.5 rounded-full bg-emerald-50 px-2.5 py-1 text-[11px] font-medium text-emerald-700 sm:inline-flex">
              <span className="h-1.5 w-1.5 rounded-full bg-emerald-500" /> AI ready
            </span>
            <Link href="/dashboard/profile" aria-label={`Open ${userName} profile`} className="rounded-full focus:outline-none focus-visible:ring-2 focus-visible:ring-brand-200">
              <ProfileAvatar src={user?.profile_photo_url || user?.profile_photo?.url} name={userName} username={user?.username} alt={userName} fallback={userInitial} className="h-8 w-8" />
            </Link>
          </div>
        </header>

        <div ref={messagesViewportRef} onScroll={(event) => {
          const element = event.currentTarget;
          const distanceFromBottom = element.scrollHeight - element.scrollTop - element.clientHeight;
          shouldStickToBottomRef.current = distanceFromBottom < 120;
        }} className="min-h-0 flex-1 overflow-y-auto bg-white">
          <div className="mx-auto flex min-h-full w-full max-w-[850px] flex-col px-4 py-8 sm:px-6 sm:py-10">
            {isMessagesLoading ? (
              <div className="flex flex-1 items-center justify-center gap-3 text-sm text-slate-500">
                <Loader2 className="h-5 w-5 animate-spin text-brand-500" /> Loading conversation...
              </div>
            ) : emptyState ? (
              <div className="flex flex-1 flex-col items-center justify-center py-8 text-center">
                <div className="flex h-12 w-12 items-center justify-center rounded-xl bg-brand-50 text-brand-600">
                  <Sparkles className="h-6 w-6" />
                </div>
                <h1 className="mt-5 text-2xl font-semibold tracking-tight text-slate-900 sm:text-3xl">How can I help with your career today?</h1>
                <p className="mt-3 max-w-lg text-sm leading-6 text-slate-500">Ask about resumes, interviews, skills, career planning, or job opportunities.</p>
                <div className="mt-7 grid w-full max-w-2xl gap-2 sm:grid-cols-2">
                  {promptSuggestions.map((suggestion) => (
                    <button key={suggestion} type="button" onClick={() => {
                      setPrompt(suggestion);
                      requestAnimationFrame(() => composerRef.current?.focus());
                    }} className="rounded-lg border border-slate-200 bg-white px-3.5 py-3 text-left text-sm text-slate-700 transition-colors hover:border-brand-200 hover:bg-brand-50 hover:text-brand-700 focus:outline-none focus-visible:ring-2 focus-visible:ring-brand-200">
                      {suggestion}
                    </button>
                  ))}
                </div>
              </div>
            ) : (
              <div className="space-y-8">
                {messages.map((message) => {
                  const isUser = message.role === 'user';
                  return (
                    <article key={message.id} className={`flex gap-3 ${isUser ? 'justify-end' : 'justify-start'}`}>
                      {!isUser ? <div className="chat-inverse mt-0.5 flex h-7 w-7 shrink-0 items-center justify-center rounded-md bg-brand-500"><Bot className="h-4 w-4" /></div> : null}
                      <div className={`min-w-0 ${isUser ? 'max-w-[82%]' : 'max-w-[760px] flex-1'}`}>
                        <div className={`mb-1 text-[11px] font-semibold uppercase tracking-[0.14em] ${isUser ? 'text-right text-slate-400' : 'text-brand-600'}`}>{isUser ? 'You' : 'CareerSphere AI'}</div>
                        {isUser ? (
                          <p className="chat-inverse whitespace-pre-wrap rounded-2xl rounded-tr-md bg-brand-500 px-4 py-3 text-sm leading-6 shadow-sm">{message.content}</p>
                        ) : (
                          <MarkdownMessage content={message.content} />
                        )}
                      </div>
                    </article>
                  );
                })}

                {isSubmitting ? (
                  <div className="flex items-center gap-3 text-sm text-slate-500">
                    <div className="flex h-7 w-7 items-center justify-center rounded-md bg-brand-50 text-brand-600"><Bot className="h-4 w-4" /></div>
                    <Loader2 className="h-4 w-4 animate-spin text-brand-500" /> AI is thinking...
                  </div>
                ) : null}
                <div ref={messagesEndRef} />
              </div>
            )}
          </div>
        </div>

        <div className="shrink-0 border-t border-slate-200 bg-white px-3 pb-[max(0.75rem,env(safe-area-inset-bottom))] pt-3 sm:px-5 sm:pt-4">
          <div className="mx-auto max-w-[850px]">
            {error ? (
              <div className="mb-3 flex items-start gap-3 rounded-lg border border-red-200 bg-red-50 p-3 text-sm text-red-700" role="alert">
                <AlertCircle className="mt-0.5 h-4 w-4 shrink-0" />
                <div className="flex-1">
                  <p className="font-medium">{error}</p>
                  {canRetry && activeConversationId ? <button type="button" onClick={handleRetry} disabled={isSubmitting} className="mt-1 text-xs font-semibold underline-offset-2 hover:underline disabled:opacity-60">Retry AI response</button> : null}
                </div>
                <button type="button" onClick={() => setError('')} className="rounded p-1 text-red-500 hover:bg-red-100" aria-label="Dismiss error"><X className="h-4 w-4" /></button>
              </div>
            ) : null}

            <GrammarSuggestions
              result={grammarResult}
              isChecking={isCheckingGrammar}
              error={grammarError}
              onApply={applyGrammarCorrections}
              onDismiss={() => {
                setGrammarResult(null);
                setGrammarError('');
              }}
            />

            <form onSubmit={handleSubmit} noValidate className="rounded-xl border border-slate-300 bg-white shadow-[0_8px_24px_rgba(16,47,107,0.08)] focus-within:border-brand-400 focus-within:ring-2 focus-within:ring-brand-100">
              <label htmlFor="ai-prompt" className="sr-only">Ask CareerSphere AI</label>
              <textarea
                id="ai-prompt"
                ref={composerRef}
                rows={1}
                value={prompt}
                disabled={isSubmitting}
                placeholder="Ask about resumes, interviews, skills, or career planning..."
                onChange={handlePromptChange}
                onKeyDown={(event) => {
                  if (event.key === 'Enter' && !event.shiftKey) {
                    event.preventDefault();
                    event.currentTarget.form?.requestSubmit();
                  }
                }}
                className="block max-h-40 min-h-11 w-full resize-none overflow-y-auto rounded-t-xl border-0 bg-transparent px-4 py-3 text-sm leading-6 text-slate-900 outline-none placeholder:text-slate-400 focus:ring-0 disabled:cursor-not-allowed disabled:opacity-60"
              />
              {fieldError ? <p className="px-4 pb-2 text-xs font-medium text-red-600">{fieldError}</p> : null}
              <div className="flex items-center justify-between gap-2 border-t border-slate-100 px-3 py-2">
                <div className="flex min-w-0 items-center gap-1.5">
                  <button type="button" onClick={() => setUseProfile((prev) => !prev)} disabled={isSubmitting} aria-pressed={useProfile} title="Use profile context for personalized responses" className={`inline-flex items-center gap-1.5 rounded-md px-2 py-1.5 text-xs font-medium transition-colors disabled:opacity-50 ${useProfile ? 'bg-brand-50 text-brand-700' : 'text-slate-500 hover:bg-slate-100 hover:text-slate-700'}`}>
                    <UserCheck className="h-3.5 w-3.5" /> <span className="hidden sm:inline">{useProfile ? 'Using profile' : 'Use profile'}</span>
                  </button>
                  <button type="button" onClick={handleGrammarCheck} disabled={isSubmitting || isCheckingGrammar} className="rounded-md px-2 py-1.5 text-xs font-medium text-slate-500 transition-colors hover:bg-slate-100 hover:text-slate-700 disabled:opacity-50">Grammar check</button>
                </div>
                <button type="submit" disabled={isSubmitting || !prompt.trim()} aria-label={isSubmitting ? 'Sending message' : 'Send message'} className="chat-inverse flex h-9 w-9 shrink-0 items-center justify-center rounded-lg bg-brand-500 transition-colors hover:bg-brand-600 disabled:cursor-not-allowed disabled:bg-slate-200 disabled:text-slate-400">
                  {isSubmitting ? <Loader2 className="h-4 w-4 animate-spin" /> : <ArrowUp className="h-4 w-4" />}
                </button>
              </div>
            </form>
            <p className="mt-2 text-center text-[11px] text-slate-400">CareerSphere AI can make mistakes. Review important career decisions.</p>
          </div>
        </div>
      </section>

      {pendingDelete ? (
        <div className="fixed inset-0 z-[100] flex items-center justify-center bg-black/40 p-4" role="dialog" aria-modal="true" aria-labelledby="delete-conversation-title">
          <div className="w-full max-w-sm rounded-xl border border-slate-200 bg-white p-5 shadow-[0_20px_50px_rgba(11,42,91,0.2)]">
            <h2 id="delete-conversation-title" className="text-base font-semibold text-slate-900">Delete conversation?</h2>
            <p className="mt-2 text-sm leading-6 text-slate-500">This will permanently delete “{pendingDelete.title || 'New conversation'}” and its messages.</p>
            <div className="mt-5 flex justify-end gap-2">
              <button type="button" onClick={() => setPendingDelete(null)} className="rounded-lg border border-slate-300 px-3.5 py-2 text-sm font-medium text-slate-700 hover:bg-slate-50">Cancel</button>
              <button type="button" onClick={confirmDelete} className="chat-inverse rounded-lg bg-red-600 px-3.5 py-2 text-sm font-semibold hover:bg-red-700">Delete</button>
            </div>
          </div>
        </div>
      ) : null}
    </div>
  );
}
