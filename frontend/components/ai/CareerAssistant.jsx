'use client';

import React, { useCallback, useEffect, useMemo, useRef, useState } from 'react';
import {
  AlertCircle,
  Bot,
  Loader2,
  Menu,
  PanelLeft,
  Send,
  Sparkles,
  SpellCheck,
  UserCheck,
} from 'lucide-react';
import {
  checkGrammar,
  createConversation,
  deleteConversation,
  extractErrorMessage,
  getConversation,
  getConversations,
  retryConversationMessage,
  sendConversationMessage,
} from '@/services/api';
import ConversationSidebar from '@/components/ai/ConversationSidebar';
import GrammarSuggestions from '@/components/ai/GrammarSuggestions';
import MarkdownMessage from '@/components/ai/MarkdownMessage';

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

export default function CareerAssistant() {
  const [conversations, setConversations] = useState([]);
  const [activeConversationId, setActiveConversationId] = useState(null);
  const [messages, setMessages] = useState([]);
  const [title, setTitle] = useState('New conversation');
  const [prompt, setPrompt] = useState('');
  const [useProfile, setUseProfile] = useState(false);
  const [error, setError] = useState('');
  const [fieldError, setFieldError] = useState('');
  const [listError, setListError] = useState('');
  const [isListLoading, setIsListLoading] = useState(true);
  const [isMessagesLoading, setIsMessagesLoading] = useState(false);
  const [isSubmitting, setIsSubmitting] = useState(false);
  const [canRetry, setCanRetry] = useState(false);
  const [sidebarOpen, setSidebarOpen] = useState(false);
  const [grammarResult, setGrammarResult] = useState(null);
  const [isCheckingGrammar, setIsCheckingGrammar] = useState(false);
  const [grammarError, setGrammarError] = useState('');
  const messagesEndRef = useRef(null);
  const composerRef = useRef(null);

  const upsertConversation = useCallback((summary) => {
    if (!summary?.id) return;
    setConversations((current) => {
      const remaining = current.filter((item) => item.id !== summary.id);
      return [summary, ...remaining];
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
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' });
  }, [messages, isSubmitting]);

  const startNewChat = () => {
    setActiveConversationId(null);
    setMessages([]);
    setTitle('New conversation');
    setError('');
    setFieldError('');
    setCanRetry(false);
    setUseProfile(false);
    setGrammarResult(null);
    setGrammarError('');
    setSidebarOpen(false);
    composerRef.current?.focus();
  };

  const openConversation = async (conversationId) => {
    if (!conversationId || isSubmitting) return;
    setActiveConversationId(conversationId);
    setSidebarOpen(false);
    setIsMessagesLoading(true);
    setError('');
    setCanRetry(false);
    try {
      const data = await getConversation(conversationId);
      setTitle(data.title || 'Conversation');
      setMessages(Array.isArray(data.messages) ? data.messages : []);
      const last = data.messages?.[data.messages.length - 1];
      setCanRetry(last?.role === 'user');
    } catch (err) {
      setError(getAIErrorMessage(err));
    } finally {
      setIsMessagesLoading(false);
    }
  };

  const handleDelete = async (conversationId) => {
    if (!conversationId || isSubmitting) return;
    const target = conversations.find((item) => item.id === conversationId);
    const confirmed = window.confirm(
      `Delete “${target?.title || 'this conversation'}”? This cannot be undone.`
    );
    if (!confirmed) return;

    try {
      await deleteConversation(conversationId);
      setConversations((current) => current.filter((item) => item.id !== conversationId));
      if (activeConversationId === conversationId) {
        startNewChat();
      }
    } catch (err) {
      setError(getAIErrorMessage(err));
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
      if (payload?.assistant_message) {
        next.push(payload.assistant_message);
      }
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
    composerRef.current?.focus();
  };

  const emptyState = useMemo(
    () => !isMessagesLoading && messages.length === 0 && !isSubmitting,
    [isMessagesLoading, messages.length, isSubmitting]
  );

  return (
    <div className="flex min-h-0 flex-1 overflow-hidden rounded-[2.2rem] border border-white/10 bg-white/[0.04] backdrop-blur-2xl shadow-glow">
      <aside className="hidden w-80 shrink-0 border-r border-white/10 bg-slate-950/60 lg:flex lg:flex-col">
        <ConversationSidebar
          conversations={conversations}
          activeConversationId={activeConversationId}
          isLoading={isListLoading}
          onNewChat={startNewChat}
          onSelect={openConversation}
          onDelete={handleDelete}
        />
        {listError ? <p className="px-4 pb-4 text-xs text-rose-300">{listError}</p> : null}
      </aside>

      {sidebarOpen ? (
        <div className="fixed inset-0 z-40 lg:hidden">
          <button
            type="button"
            className="absolute inset-0 bg-slate-950/80 backdrop-blur-sm"
            aria-label="Close conversations"
            onClick={() => setSidebarOpen(false)}
          />
          <div className="absolute inset-y-0 left-0 flex w-[min(20rem,88vw)] flex-col border-r border-white/10 bg-slate-950/95 backdrop-blur-2xl shadow-2xl">
            <ConversationSidebar
              conversations={conversations}
              activeConversationId={activeConversationId}
              isLoading={isListLoading}
              onNewChat={startNewChat}
              onSelect={openConversation}
              onDelete={handleDelete}
              onClose={() => setSidebarOpen(false)}
            />
          </div>
        </div>
      ) : null}

      <section className="flex min-w-0 flex-1 flex-col">
        <div className="flex items-start justify-between gap-3 border-b border-white/10 px-4 py-4 sm:px-6 bg-slate-950/30 backdrop-blur-md">
          <div className="min-w-0">
            <div className="mb-2 inline-flex items-center gap-2 rounded-full border border-accent/30 bg-accent/10 px-3 py-1 text-xs font-semibold uppercase tracking-[0.2em] text-accent">
              <Sparkles className="h-3.5 w-3.5 text-accent" />
              Career Intelligence
            </div>
            <h1 className="truncate text-xl font-extrabold tracking-tight text-white sm:text-2xl">
              AI Career Assistant
            </h1>
            <p className="mt-1 truncate text-sm text-slate-400">{title}</p>
            <p className="mt-1 text-xs text-slate-500">
              {useProfile
                ? '👤 Personalizing with your CareerSphere profile'
                : 'General mode — enable "Use My Profile" to personalize responses'}
            </p>
          </div>
          <button
            type="button"
            onClick={() => setSidebarOpen(true)}
            className="inline-flex items-center gap-2 rounded-full border border-white/10 bg-white/5 px-3.5 py-2 text-xs font-semibold text-slate-200 hover:border-accent/40 hover:text-white transition-all lg:hidden"
          >
            <Menu className="h-4 w-4" />
            Chats
          </button>
        </div>

        <div className="min-h-0 flex-1 overflow-y-auto px-4 py-5 sm:px-6">
          {isMessagesLoading ? (
            <div className="flex h-full min-h-[12rem] items-center justify-center gap-3 text-sm text-slate-400">
              <Loader2 className="h-5 w-5 animate-spin text-accent" />
              Loading conversation...
            </div>
          ) : emptyState ? (
            <div className="mx-auto flex max-w-xl flex-col items-center py-12 text-center">
              <div className="mb-4 flex h-14 w-14 items-center justify-center rounded-2xl border border-accent/30 bg-accent/10 shadow-[0_0_30px_rgba(255,143,50,0.2)]">
                <PanelLeft className="h-6 w-6 text-accent" />
              </div>
              <h2 className="text-lg font-semibold text-white">Start a career conversation</h2>
              <p className="mt-2 text-sm leading-relaxed text-slate-400">
                Ask about resumes, interviews, skills, or career planning. Your chats are saved to your
                account so you can come back and continue later.
              </p>
            </div>
          ) : (
            <div className="mx-auto flex max-w-3xl flex-col gap-4">
              {messages.map((message) => {
                const isUser = message.role === 'user';
                return (
                  <div key={message.id} className={`flex ${isUser ? 'justify-end' : 'justify-start'}`}>
                    <div
                      className={`max-w-[92%] rounded-2xl border px-4 py-3 sm:max-w-[80%] ${
                        isUser
                          ? 'border-accent/30 bg-accent/15 text-slate-100 shadow-[0_4px_20px_rgba(255,143,50,0.12)]'
                          : 'border-white/10 bg-white/[0.05] text-slate-100 backdrop-blur-md shadow-sm'
                      }`}
                    >
                      <p className="mb-2 text-[11px] font-semibold uppercase tracking-[0.16em] text-slate-400">
                        {isUser ? 'You' : 'CareerSphere AI'}
                      </p>
                      {isUser ? (
                        <p className="whitespace-pre-wrap text-sm leading-relaxed text-slate-100">
                          {message.content}
                        </p>
                      ) : (
                        <MarkdownMessage content={message.content} />
                      )}
                    </div>
                  </div>
                );
              })}

              {isSubmitting ? (
                <div className="flex justify-start">
                  <div className="flex max-w-[80%] items-center gap-3 rounded-2xl border border-white/10 bg-white/[0.05] backdrop-blur-md px-4 py-3 text-sm text-slate-300 shadow-sm">
                    <Bot className="h-4 w-4 text-accent" />
                    <Loader2 className="h-4 w-4 animate-spin text-accent" />
                    AI is thinking...
                  </div>
                </div>
              ) : null}
              <div ref={messagesEndRef} />
            </div>
          )}
        </div>

        <div className="border-t border-white/10 px-4 py-4 sm:px-6 bg-slate-950/20">
          <div className="mx-auto max-w-3xl space-y-3">
            {error ? (
              <div
                className="flex items-start gap-3 rounded-2xl border border-rose-500/30 bg-rose-500/10 p-3 text-sm text-rose-300"
                role="alert"
              >
                <AlertCircle className="mt-0.5 h-5 w-5 shrink-0 text-rose-400" />
                <div className="flex-1">
                  <p className="font-medium">{error}</p>
                  {canRetry && activeConversationId ? (
                    <button
                      type="button"
                      onClick={handleRetry}
                      disabled={isSubmitting}
                      className="mt-2 text-xs font-semibold text-rose-100 underline-offset-2 hover:underline disabled:opacity-60"
                    >
                      Retry AI response
                    </button>
                  ) : null}
                </div>
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

            <form onSubmit={handleSubmit} noValidate className="space-y-3">
              <label htmlFor="ai-prompt" className="sr-only">
                Ask anything
              </label>
              <textarea
                id="ai-prompt"
                ref={composerRef}
                rows={3}
                value={prompt}
                disabled={isSubmitting}
                placeholder="Ask anything about resumes, interviews, skills, or career planning..."
                onChange={(event) => {
                  setPrompt(event.target.value);
                  if (fieldError) setFieldError('');
                }}
                onKeyDown={(event) => {
                  if (event.key === 'Enter' && !event.shiftKey) {
                    event.preventDefault();
                    event.currentTarget.form?.requestSubmit();
                  }
                }}
                className={`block min-h-[92px] w-full resize-y rounded-2xl border bg-slate-950/80 px-4 py-3 text-sm text-slate-100 placeholder-slate-500 transition-all duration-200 focus:outline-none focus:ring-2 ${
                  fieldError
                    ? 'border-rose-500/80 focus:border-rose-500 focus:ring-rose-500/30'
                    : 'border-white/10 hover:border-white/20 focus:border-accent/80 focus:ring-accent/30'
                } ${isSubmitting ? 'cursor-not-allowed opacity-60' : ''}`}
              />
              {fieldError ? <p className="text-xs font-medium text-rose-400">{fieldError}</p> : null}

              <div className="flex flex-col-reverse gap-2 sm:flex-row sm:items-center sm:justify-end">
                <button
                  type="button"
                  onClick={() => setUseProfile((prev) => !prev)}
                  disabled={isSubmitting}
                  aria-pressed={useProfile}
                  title={useProfile ? 'Disable profile context' : 'Enable profile context for personalized responses'}
                  className={`inline-flex items-center justify-center gap-2 rounded-full border px-4 py-2 text-xs font-semibold transition-all disabled:cursor-not-allowed disabled:opacity-60 ${
                    useProfile
                      ? 'border-accent/60 bg-accent/20 text-accent shadow-[0_0_16px_rgba(255,143,50,0.2)] hover:bg-accent/30'
                      : 'border-white/10 bg-white/5 text-slate-400 hover:border-white/20 hover:text-slate-200'
                  }`}
                >
                  <UserCheck className={`h-4 w-4 ${useProfile ? 'text-accent' : 'text-slate-400'}`} />
                  Use My Profile
                  <span
                    className={`ml-0.5 inline-flex h-4 w-7 items-center rounded-full transition-colors ${
                      useProfile ? 'bg-accent' : 'bg-white/15'
                    }`}
                    aria-hidden="true"
                  >
                    <span
                      className={`inline-block h-3 w-3 rounded-full bg-white shadow transition-transform ${
                        useProfile ? 'translate-x-3.5' : 'translate-x-0.5'
                      }`}
                    />
                  </span>
                </button>
                <button
                  type="button"
                  onClick={handleGrammarCheck}
                  disabled={isSubmitting || isCheckingGrammar}
                  className="inline-flex items-center justify-center gap-2 rounded-full border border-white/10 bg-white/5 px-4 py-2 text-xs font-semibold text-slate-200 hover:border-cyan/40 hover:bg-cyan/10 hover:text-white transition-all disabled:cursor-not-allowed disabled:opacity-60"
                >
                  {isCheckingGrammar ? (
                    <Loader2 className="h-4 w-4 animate-spin text-cyan" />
                  ) : (
                    <SpellCheck className="h-4 w-4 text-cyan" />
                  )}
                  Check Grammar
                </button>
                <button
                  type="submit"
                  disabled={isSubmitting}
                  className="inline-flex items-center justify-center gap-2 rounded-full bg-accent px-5 py-2 text-xs font-semibold text-black shadow-[0_8px_30px_rgba(255,143,50,0.35)] hover:bg-accentSoft transition-all disabled:cursor-not-allowed disabled:opacity-60"
                >
                  {isSubmitting ? (
                    <>
                      <Loader2 className="h-4 w-4 animate-spin text-black" />
                      Sending...
                    </>
                  ) : (
                    <>
                      <Send className="h-4 w-4" />
                      Send
                    </>
                  )}
                </button>
              </div>
            </form>
          </div>
        </div>
      </section>
    </div>
  );
}
