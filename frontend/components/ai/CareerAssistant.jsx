'use client';

import React, { useState } from 'react';
import { Sparkles, Send, Loader2, AlertCircle, Bot } from 'lucide-react';
import { chatWithAI, extractErrorMessage } from '@/services/api';

function getAIErrorMessage(error) {
  if (error?.code === 'ECONNABORTED') {
    return 'The AI request timed out. Please try again with a shorter question.';
  }

  if (!error?.response) {
    return 'Unable to reach the CareerSphere backend. Please try again later.';
  }

  if (error.response.status === 503) {
    return 'The AI service is currently unavailable. Please try again in a moment.';
  }

  return extractErrorMessage(error);
}

export default function CareerAssistant() {
  const [prompt, setPrompt] = useState('');
  const [response, setResponse] = useState('');
  const [error, setError] = useState('');
  const [fieldError, setFieldError] = useState('');
  const [isSubmitting, setIsSubmitting] = useState(false);

  const handlePromptChange = (event) => {
    setPrompt(event.target.value);
    if (fieldError) {
      setFieldError('');
    }
    if (error) {
      setError('');
    }
  };

  const handleSubmit = async (event) => {
    event.preventDefault();

    const trimmedPrompt = prompt.trim();
    if (!trimmedPrompt) {
      setFieldError('Please enter a career question before asking the AI.');
      setError('');
      return;
    }

    if (isSubmitting) {
      return;
    }

    setFieldError('');
    setError('');
    setIsSubmitting(true);

    try {
      const data = await chatWithAI(trimmedPrompt, false);

      if (!data || typeof data.response !== 'string') {
        setResponse('');
        setError('Received an unexpected response from the AI service. Please try again.');
        return;
      }

      setResponse(data.response);
    } catch (err) {
      setResponse('');
      setError(getAIErrorMessage(err));
    } finally {
      setIsSubmitting(false);
    }
  };

  return (
    <div className="space-y-6">
      <div>
        <div className="inline-flex items-center gap-2 px-3 py-1 rounded-full bg-accent/10 border border-accent/30 text-accent text-xs font-semibold mb-3">
          <Sparkles className="h-3.5 w-3.5" />
          <span>Career Intelligence</span>
        </div>
        <h1 className="text-3xl sm:text-4xl font-extrabold text-white tracking-tight">
          AI Career Assistant
        </h1>
        <p className="mt-2 text-base text-slate-400 max-w-2xl">
          Ask career-related questions about resumes, interviews, skills, and professional growth.
          Your prompt is sent to the CareerSphere backend, which generates a response with the local AI model.
        </p>
      </div>

      <div className="glass-card rounded-2xl p-6 sm:p-8 space-y-5">
        {error && (
          <div
            className="p-4 rounded-xl bg-rose-500/10 border border-rose-500/30 flex items-start gap-3 text-rose-300 text-sm animate-fade-in"
            role="alert"
          >
            <AlertCircle className="h-5 w-5 text-rose-400 shrink-0 mt-0.5" />
            <p className="font-medium">{error}</p>
          </div>
        )}

        <form onSubmit={handleSubmit} noValidate className="space-y-4">
          <div className="space-y-1.5">
            <label htmlFor="ai-prompt" className="block text-sm font-medium text-slate-200">
              Your question <span className="text-rose-400">*</span>
            </label>
            <textarea
              id="ai-prompt"
              name="prompt"
              rows={5}
              value={prompt}
              onChange={handlePromptChange}
              disabled={isSubmitting}
              placeholder="How can I improve my software engineering profile?"
              aria-invalid={fieldError ? 'true' : 'false'}
              aria-describedby={fieldError ? 'ai-prompt-error' : undefined}
              className={`block w-full rounded-xl bg-slate-950/80 border px-4 py-3 text-sm text-slate-100 placeholder-slate-500 resize-y min-h-[120px] transition-all duration-200 focus:outline-none focus:ring-2 ${
                fieldError
                  ? 'border-rose-500/80 focus:border-rose-500 focus:ring-rose-500/30'
                  : 'border-white/10 hover:border-white/20 focus:border-accent/80 focus:ring-accent/30'
              } ${isSubmitting ? 'opacity-60 cursor-not-allowed' : ''}`}
            />
            {fieldError && (
              <p id="ai-prompt-error" className="text-xs text-rose-400 mt-1 font-medium">
                {fieldError}
              </p>
            )}
          </div>

          <button
            type="submit"
            disabled={isSubmitting}
            className="inline-flex items-center justify-center gap-2 py-3 px-5 rounded-xl text-sm font-semibold text-black bg-accent hover:bg-accentSoft shadow-[0_8px_30px_rgba(255,143,50,0.35)] hover:shadow-[0_12px_40px_rgba(255,143,50,0.45)] hover:-translate-y-0.5 active:translate-y-0 transition-all duration-200 disabled:opacity-60 disabled:cursor-not-allowed disabled:transform-none"
          >
            {isSubmitting ? (
              <>
                <Loader2 className="h-4 w-4 animate-spin text-black" />
                <span>Asking AI...</span>
              </>
            ) : (
              <>
                <Send className="h-4 w-4" />
                <span>Ask AI</span>
              </>
            )}
          </button>
        </form>
      </div>

      {(isSubmitting || response) && (
        <div className="glass-card rounded-2xl p-6 sm:p-8 space-y-4 animate-fade-in">
          <div className="flex items-center gap-2 text-lg font-bold text-white">
            <Bot className="h-5 w-5 text-indigo-400" />
            <span>AI Career Assistant</span>
          </div>
          <div className="border-t border-slate-800/80 pt-4">
            {isSubmitting ? (
              <div className="flex items-center gap-3 text-sm text-slate-400">
                <Loader2 className="h-5 w-5 text-indigo-400 animate-spin shrink-0" />
                <span>Generating a response. This may take a little while on local hardware...</span>
              </div>
            ) : (
              <p className="text-sm sm:text-base text-slate-200 whitespace-pre-wrap leading-relaxed">
                {response}
              </p>
            )}
          </div>
        </div>
      )}
    </div>
  );
}
