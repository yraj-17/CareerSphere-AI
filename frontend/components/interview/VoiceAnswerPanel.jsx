'use client';

import React, { useCallback, useEffect, useRef, useState } from 'react';
import { AlertTriangle, CheckCircle2, Loader2, Mic, RotateCcw, Square, X } from 'lucide-react';
import useAudioRecorder from '@/hooks/useAudioRecorder';
import { extractErrorMessage, transcribeInterviewAudio } from '@/services/api';
import { apiErrorDetail, formatClock } from '@/components/interview/interviewConstants';

/**
 * Record → transcribe → review. The approved transcript is submitted by the
 * parent through the same answer endpoint as text mode. This is not a real-time
 * conversation: each answer is recorded, then transcribed.
 */
export default function VoiceAnswerPanel({ interviewId, maxSeconds = 180, maxBytes, disabled, onTranscript, onUnavailable }) {
  const recorder = useAudioRecorder({ maxSeconds, maxBytes });
  const [transcribeState, setTranscribeState] = useState('idle'); // idle | working | done | error
  const [transcribeError, setTranscribeError] = useState('');
  const [unavailable, setUnavailable] = useState(false);
  const transcribedBlobRef = useRef(null);

  const transcribe = useCallback(
    async (blob) => {
      setTranscribeState('working');
      setTranscribeError('');
      try {
        const result = await transcribeInterviewAudio(interviewId, blob);
        transcribedBlobRef.current = blob;
        setTranscribeState('done');
        onTranscript(result.transcript);
      } catch (error) {
        if (apiErrorDetail(error).stage === 'transcription_unavailable') {
          setUnavailable(true);
          onUnavailable?.();
        }
        setTranscribeError(extractErrorMessage(error));
        setTranscribeState('error');
      }
    },
    [interviewId, onTranscript, onUnavailable]
  );

  const { status, recording } = recorder;
  useEffect(() => {
    if (status === 'recorded' && recording?.blob && transcribedBlobRef.current !== recording.blob && transcribeState === 'idle') {
      transcribe(recording.blob);
    }
  }, [status, recording, transcribe, transcribeState]);

  const startRecording = () => {
    setTranscribeState('idle');
    setTranscribeError('');
    transcribedBlobRef.current = null;
    recorder.start();
  };

  if (unavailable || !recorder.supported) {
    return (
      <div className="flex gap-2 rounded-xl border border-amber-200 bg-amber-50 p-3 text-sm text-amber-900" role="status">
        <AlertTriangle className="mt-0.5 h-4 w-4 shrink-0" aria-hidden="true" />
        <span>
          {unavailable
            ? 'Voice transcription is unavailable right now. Type your answer below instead.'
            : 'This browser cannot record audio. Type your answer below instead.'}
        </span>
      </div>
    );
  }

  return (
    <div className="rounded-xl border border-slate-200 bg-slate-50 p-4" aria-label="Voice answer recorder">
      {recorder.status === 'idle' && transcribeState !== 'done' && (
        <div className="flex flex-col gap-3 sm:flex-row sm:items-center sm:justify-between">
          <p className="text-sm text-slate-600">
            Record your answer (up to {Math.floor(maxSeconds / 60)} minutes). You&apos;ll review the transcript before submitting.
          </p>
          <button type="button" onClick={startRecording} disabled={disabled} className="btn-primary shrink-0">
            <Mic className="h-4 w-4" aria-hidden="true" />
            Start recording
          </button>
        </div>
      )}

      {recorder.status === 'requesting' && (
        <p className="flex items-center gap-2 text-sm text-slate-600" role="status">
          <Loader2 className="h-4 w-4 animate-spin" aria-hidden="true" />
          Waiting for microphone permission...
        </p>
      )}

      {recorder.status === 'recording' && (
        <div className="flex flex-col gap-3 sm:flex-row sm:items-center sm:justify-between">
          <p className="flex items-center gap-2 text-sm font-medium text-slate-900" role="status" aria-live="polite">
            <span className="h-2.5 w-2.5 animate-pulse rounded-full bg-red-600" aria-hidden="true" />
            Recording
            <span className="font-mono text-slate-600" aria-label="Elapsed recording time">
              {formatClock(recorder.elapsed)} / {formatClock(maxSeconds)}
            </span>
          </p>
          <div className="flex gap-2">
            <button type="button" onClick={recorder.cancel} className="btn-ghost">
              <X className="h-4 w-4" aria-hidden="true" />
              Cancel
            </button>
            <button type="button" onClick={recorder.stop} className="btn-primary">
              <Square className="h-4 w-4" aria-hidden="true" />
              Stop recording
            </button>
          </div>
        </div>
      )}

      {recorder.status === 'error' && (
        <div className="space-y-2" role="alert">
          <p className="flex items-start gap-2 text-sm text-red-700">
            <AlertTriangle className="mt-0.5 h-4 w-4 shrink-0" aria-hidden="true" />
            {recorder.error?.message}
          </p>
          {recorder.error?.code !== 'unsupported' && (
            <button type="button" onClick={startRecording} disabled={disabled} className="btn-outline">
              <RotateCcw className="h-4 w-4" aria-hidden="true" />
              Try again
            </button>
          )}
        </div>
      )}

      {recorder.status === 'recorded' && recorder.recording && (
        <div className="space-y-3">
          {/* Local playback only — the recording never leaves the browser except for transcription. */}
          <audio controls src={recorder.recording.url} className="w-full" aria-label="Playback of your recording" />
          {transcribeState === 'working' && (
            <p className="flex items-center gap-2 text-sm text-slate-600" role="status">
              <Loader2 className="h-4 w-4 animate-spin" aria-hidden="true" />
              Transcribing your answer...
            </p>
          )}
          {transcribeState === 'done' && (
            <p className="flex items-center gap-2 text-sm text-emerald-700" role="status">
              <CheckCircle2 className="h-4 w-4" aria-hidden="true" />
              Transcript ready. Review and edit it below before submitting.
            </p>
          )}
          {transcribeState === 'error' && (
            <div className="space-y-2" role="alert">
              <p className="text-sm text-red-700">{transcribeError}</p>
              <button type="button" onClick={() => transcribe(recorder.recording.blob)} disabled={disabled} className="btn-outline">
                <RotateCcw className="h-4 w-4" aria-hidden="true" />
                Retry transcription
              </button>
            </div>
          )}
          {transcribeState !== 'working' && (
            <button type="button" onClick={startRecording} disabled={disabled} className="btn-ghost">
              <Mic className="h-4 w-4" aria-hidden="true" />
              Record again
            </button>
          )}
        </div>
      )}
    </div>
  );
}
