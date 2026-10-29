'use client';

import { useCallback, useEffect, useRef, useState } from 'react';

const MIME_CANDIDATES = ['audio/webm;codecs=opus', 'audio/webm', 'audio/ogg;codecs=opus', 'audio/mp4'];
const MIN_RECORDING_BYTES = 1024;

export function isRecordingSupported() {
  return (
    typeof window !== 'undefined' &&
    typeof window.MediaRecorder !== 'undefined' &&
    Boolean(navigator?.mediaDevices?.getUserMedia)
  );
}

function pickMimeType() {
  if (typeof window.MediaRecorder?.isTypeSupported !== 'function') return '';
  return MIME_CANDIDATES.find((type) => window.MediaRecorder.isTypeSupported(type)) || '';
}

function describeError(error) {
  if (error?.name === 'NotAllowedError' || error?.name === 'SecurityError') {
    return { code: 'denied', message: 'Microphone access was blocked. Allow it in your browser settings or type your answer.' };
  }
  if (error?.name === 'NotFoundError' || error?.name === 'OverconstrainedError') {
    return { code: 'no-device', message: 'No microphone was found. Connect one or type your answer.' };
  }
  return { code: 'failed', message: 'Recording could not start. Please try again or type your answer.' };
}

/**
 * Browser microphone recording via MediaRecorder.
 * Permission is requested only when start() is called. Audio stays in memory
 * until the caller uploads it; the microphone is released as soon as recording ends.
 *
 * status: idle | requesting | recording | recorded | error
 */
export default function useAudioRecorder({ maxSeconds = 180, maxBytes = 8 * 1024 * 1024 } = {}) {
  const [status, setStatus] = useState('idle');
  const [elapsed, setElapsed] = useState(0);
  const [error, setError] = useState(null);
  const [recording, setRecording] = useState(null); // { blob, url }

  const recorderRef = useRef(null);
  const streamRef = useRef(null);
  const chunksRef = useRef([]);
  const timerRef = useRef(null);
  const discardRef = useRef(false);
  const urlRef = useRef(null);

  const releaseStream = useCallback(() => {
    window.clearInterval(timerRef.current);
    timerRef.current = null;
    streamRef.current?.getTracks().forEach((track) => track.stop());
    streamRef.current = null;
  }, []);

  const clearRecording = useCallback(() => {
    if (urlRef.current) URL.revokeObjectURL(urlRef.current);
    urlRef.current = null;
    setRecording(null);
  }, []);

  const stop = useCallback(() => {
    const recorder = recorderRef.current;
    if (recorder && recorder.state !== 'inactive') recorder.stop();
  }, []);

  const start = useCallback(async () => {
    if (!isRecordingSupported()) {
      setError({ code: 'unsupported', message: 'This browser does not support audio recording. Please type your answer.' });
      setStatus('error');
      return;
    }
    clearRecording();
    setError(null);
    setElapsed(0);
    setStatus('requesting');
    try {
      const stream = await navigator.mediaDevices.getUserMedia({ audio: true });
      streamRef.current = stream;
      const mimeType = pickMimeType();
      const recorder = mimeType ? new window.MediaRecorder(stream, { mimeType }) : new window.MediaRecorder(stream);
      recorderRef.current = recorder;
      chunksRef.current = [];
      discardRef.current = false;

      recorder.ondataavailable = (event) => {
        if (event.data && event.data.size > 0) chunksRef.current.push(event.data);
      };
      recorder.onstop = () => {
        releaseStream();
        if (discardRef.current) {
          chunksRef.current = [];
          setStatus('idle');
          return;
        }
        const blob = new Blob(chunksRef.current, { type: recorder.mimeType || mimeType || 'audio/webm' });
        chunksRef.current = [];
        if (blob.size < MIN_RECORDING_BYTES) {
          setError({ code: 'empty', message: 'The recording was empty. Please try again.' });
          setStatus('error');
          return;
        }
        if (blob.size > maxBytes) {
          setError({ code: 'too-large', message: 'The recording is too large. Please record a shorter answer.' });
          setStatus('error');
          return;
        }
        const url = URL.createObjectURL(blob);
        urlRef.current = url;
        setRecording({ blob, url });
        setStatus('recorded');
      };

      recorder.start(1000);
      setStatus('recording');
      const startedAt = Date.now();
      timerRef.current = window.setInterval(() => {
        const seconds = Math.floor((Date.now() - startedAt) / 1000);
        setElapsed(seconds);
        if (seconds >= maxSeconds) stop();
      }, 250);
    } catch (err) {
      releaseStream();
      setError(describeError(err));
      setStatus('error');
    }
  }, [clearRecording, maxBytes, maxSeconds, releaseStream, stop]);

  const cancel = useCallback(() => {
    discardRef.current = true;
    const recorder = recorderRef.current;
    if (recorder && recorder.state !== 'inactive') {
      recorder.stop();
    } else {
      releaseStream();
      setStatus('idle');
    }
    clearRecording();
    setElapsed(0);
    setError(null);
  }, [clearRecording, releaseStream]);

  const reset = useCallback(() => {
    clearRecording();
    setElapsed(0);
    setError(null);
    setStatus('idle');
  }, [clearRecording]);

  useEffect(
    () => () => {
      discardRef.current = true;
      const recorder = recorderRef.current;
      if (recorder && recorder.state !== 'inactive') recorder.stop();
      window.clearInterval(timerRef.current);
      streamRef.current?.getTracks().forEach((track) => track.stop());
      if (urlRef.current) URL.revokeObjectURL(urlRef.current);
    },
    []
  );

  return { status, elapsed, error, recording, start, stop, cancel, reset, supported: isRecordingSupported() };
}
