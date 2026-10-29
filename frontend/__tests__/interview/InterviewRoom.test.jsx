import React from 'react';
import { act, fireEvent, render, screen, waitFor, within } from '@testing-library/react';

const mockPush = jest.fn();

jest.mock('next/link', () => {
  const Link = ({ children, href, ...props }) => (
    <a href={href} {...props}>
      {children}
    </a>
  );
  Link.displayName = 'MockLink';
  return Link;
});

jest.mock('next/navigation', () => ({
  useRouter: () => ({ push: mockPush }),
}));

jest.mock('@/services/api', () => ({
  completeInterview: jest.fn(),
  extractErrorMessage: jest.fn((err) => err?.response?.data?.detail?.message || err?.response?.data?.detail || err?.message || 'Error'),
  getInterview: jest.fn(),
  requestNextInterviewQuestion: jest.fn(),
  retryInterviewEvaluation: jest.fn(),
  submitInterviewAnswer: jest.fn(),
  transcribeInterviewAudio: jest.fn(),
}));

import {
  completeInterview,
  getInterview,
  requestNextInterviewQuestion,
  retryInterviewEvaluation,
  submitInterviewAnswer,
  transcribeInterviewAudio,
} from '@/services/api';
import InterviewRoom from '@/components/interview/InterviewRoom';

const Q1 = {
  id: 'q1',
  question_order: 1,
  question_text: 'How would you speed up a slow SQL query?',
  category: 'TECHNICAL',
  competency: 'SQL',
  difficulty: 'INTERMEDIATE',
  interviewer_context: null,
  created_at: '2026-10-29T10:00:00Z',
  answer: null,
};

const Q2 = { ...Q1, id: 'q2', question_order: 2, question_text: 'Explain eventual consistency.', competency: 'Distributed systems' };

const EVALUATED = {
  id: 'a1',
  question_id: 'q1',
  answer_text: 'Add an index.\nCheck the plan.',
  answer_source: 'TEXT',
  submitted_at: '2026-10-29T10:01:00Z',
  evaluation_status: 'COMPLETED',
  score: 77,
  evaluation: {
    score: 77,
    dimensions: { accuracy: 90, reasoning: 60, relevance: 80, clarity: 70, structure: null, reflection: null },
    strengths: ['Mentioned indexes'],
    improvements: ['Discuss trade-offs'],
    feedback: 'Solid start. Explain how you would verify the improvement.',
    key_points: ['EXPLAIN plans'],
  },
  can_retry_evaluation: false,
};

function makeInterview(overrides = {}) {
  const now = new Date();
  return {
    id: 'iv-1',
    target_role: 'Backend Engineer',
    interview_type: 'TECHNICAL',
    interaction_mode: 'TEXT',
    difficulty: 'INTERMEDIATE',
    duration_minutes: 15,
    status: 'IN_PROGRESS',
    started_at: now.toISOString(),
    deadline_at: new Date(now.getTime() + 15 * 60 * 1000).toISOString(),
    completed_at: null,
    final_score: null,
    question_count: 1,
    answered_count: 0,
    report_status: null,
    focus_areas: [],
    instructions: null,
    max_questions: 6,
    server_time: now.toISOString(),
    remaining_seconds: 900,
    current_question: Q1,
    can_request_next_question: false,
    questions: [Q1],
    ...overrides,
  };
}

function answeredInterview(answer = EVALUATED, overrides = {}) {
  const q1 = { ...Q1, answer };
  return makeInterview({
    answered_count: 1,
    current_question: null,
    can_request_next_question: true,
    questions: [q1],
    ...overrides,
  });
}

beforeEach(() => {
  jest.clearAllMocks();
  window.localStorage.clear();
});

test('renders the active question, timer, and progress', async () => {
  getInterview.mockResolvedValue(makeInterview());
  render(<InterviewRoom interviewId="iv-1" />);
  expect(await screen.findByText(Q1.question_text)).toBeInTheDocument();
  expect(screen.getByRole('timer')).toHaveTextContent(/1[45]:\d\d/);
  expect(screen.getByText('Question 1 of 6')).toBeInTheDocument();
  expect(screen.getByRole('progressbar', { name: /interview progress/i })).toHaveAttribute('aria-valuenow', '0');
  expect(screen.getByRole('button', { name: /submit answer/i })).toBeDisabled();
});

test('submits a text answer, shows per-answer feedback, and continues', async () => {
  getInterview.mockResolvedValue(makeInterview());
  const after = answeredInterview();
  submitInterviewAnswer.mockResolvedValue({ answer: EVALUATED, interview: after });
  const withNext = { ...after, question_count: 2, current_question: Q2, can_request_next_question: false, questions: [after.questions[0], Q2] };
  requestNextInterviewQuestion.mockResolvedValue(withNext);

  render(<InterviewRoom interviewId="iv-1" />);
  const editor = await screen.findByLabelText('Your answer');
  fireEvent.change(editor, { target: { value: 'Add an index.\nCheck the plan.' } });
  expect(screen.getByText('29/5000')).toBeInTheDocument();
  fireEvent.click(screen.getByRole('button', { name: /submit answer/i }));

  expect(await screen.findByLabelText('Answer feedback')).toBeInTheDocument();
  expect(submitInterviewAnswer).toHaveBeenCalledWith('iv-1', {
    questionId: 'q1',
    answerText: 'Add an index.\nCheck the plan.',
    answerSource: 'TEXT',
  });
  expect(screen.getByText('77')).toBeInTheDocument();
  expect(screen.getByText('Mentioned indexes')).toBeInTheDocument();
  expect(screen.getByText(/full report is available when the interview ends/i)).toBeInTheDocument();
  // The next question is prepared in the background while feedback is shown.
  await waitFor(() => expect(requestNextInterviewQuestion).toHaveBeenCalledWith('iv-1'));

  fireEvent.click(await screen.findByRole('button', { name: /next question/i }));
  expect(await screen.findByText(Q2.question_text)).toBeInTheDocument();
  const previous = screen.getByRole('heading', { name: /previous questions/i }).parentElement;
  expect(within(previous).getByText(/Q1\. SQL/)).toBeInTheDocument();
  expect(within(previous).getByText('77/100')).toBeInTheDocument();
});

test('shows a recoverable state when evaluation fails and retries it', async () => {
  const failed = { ...EVALUATED, evaluation_status: 'FAILED', score: null, evaluation: null, can_retry_evaluation: true };
  getInterview.mockResolvedValueOnce(answeredInterview(failed)).mockResolvedValue(answeredInterview());
  retryInterviewEvaluation.mockResolvedValue(EVALUATED);

  render(<InterviewRoom interviewId="iv-1" />);
  expect(await screen.findByText(/your answer was saved, but feedback isn't available yet/i)).toBeInTheDocument();
  fireEvent.click(screen.getByRole('button', { name: /retry evaluation/i }));
  await waitFor(() => expect(retryInterviewEvaluation).toHaveBeenCalledWith('iv-1', 'a1'));
  expect(await screen.findByLabelText('Answer feedback')).toBeInTheDocument();
});

test('recovers an answer the server saved even if the request failed', async () => {
  getInterview.mockResolvedValueOnce(makeInterview()).mockResolvedValue(answeredInterview());
  submitInterviewAnswer.mockRejectedValue(new Error('timeout'));
  render(<InterviewRoom interviewId="iv-1" />);
  fireEvent.change(await screen.findByLabelText('Your answer'), { target: { value: 'Add an index.' } });
  fireEvent.click(screen.getByRole('button', { name: /submit answer/i }));
  expect(await screen.findByLabelText('Answer feedback')).toBeInTheDocument();
  expect(screen.queryByRole('alert')).not.toBeInTheDocument();
});

test('ends the interview after confirmation and opens the report', async () => {
  getInterview.mockResolvedValue(answeredInterview());
  completeInterview.mockResolvedValue({ ...answeredInterview(), status: 'COMPLETED' });
  render(<InterviewRoom interviewId="iv-1" />);
  fireEvent.click(await screen.findByRole('button', { name: /end interview/i }));
  const dialog = screen.getByRole('dialog', { name: /end this interview/i });
  expect(within(dialog).getByText(/1 submitted answer will be included/i)).toBeInTheDocument();
  fireEvent.click(within(dialog).getByRole('button', { name: /keep going/i }));
  expect(completeInterview).not.toHaveBeenCalled();

  fireEvent.click(screen.getByRole('button', { name: /end interview/i }));
  fireEvent.click(within(screen.getByRole('dialog')).getByRole('button', { name: /end interview/i }));
  await waitFor(() => expect(mockPush).toHaveBeenCalledWith('/dashboard/interview/iv-1/results'));
});

test('offers to finish when the question limit is reached', async () => {
  getInterview.mockResolvedValue(answeredInterview(EVALUATED, { can_request_next_question: false, question_count: 6 }));
  completeInterview.mockResolvedValue({ ...answeredInterview(), status: 'COMPLETED' });
  render(<InterviewRoom interviewId="iv-1" />);
  expect(await screen.findByText(/reached the last question/i)).toBeInTheDocument();
  fireEvent.click(screen.getByRole('button', { name: /finish and view report/i }));
  await waitFor(() => expect(completeInterview).toHaveBeenCalledWith('iv-1'));
});

test('when time runs out the draft is saved and the interview ends', async () => {
  const now = new Date();
  const expiredClock = makeInterview({ server_time: now.toISOString(), deadline_at: now.toISOString() });
  window.localStorage.setItem('careersphere:interview-draft:q1', 'My last thoughts');
  getInterview.mockResolvedValue(expiredClock);
  submitInterviewAnswer.mockResolvedValue({ answer: EVALUATED, interview: answeredInterview() });
  completeInterview.mockResolvedValue({ ...answeredInterview(), status: 'EXPIRED' });

  render(<InterviewRoom interviewId="iv-1" />);
  await waitFor(() => expect(submitInterviewAnswer).toHaveBeenCalledWith('iv-1', expect.objectContaining({ answerText: 'My last thoughts' })));
  await waitFor(() => expect(completeInterview).toHaveBeenCalled());
  await waitFor(() => expect(mockPush).toHaveBeenCalledWith('/dashboard/interview/iv-1/results'));
});

test('renders the expired state for a session the server has closed', async () => {
  getInterview.mockResolvedValue(answeredInterview(EVALUATED, { status: 'EXPIRED' }));
  render(<InterviewRoom interviewId="iv-1" />);
  expect(await screen.findByText('Time limit reached')).toBeInTheDocument();
  expect(screen.getByRole('link', { name: /view report/i })).toHaveAttribute('href', '/dashboard/interview/iv-1/results');
  expect(screen.queryByLabelText('Your answer')).not.toBeInTheDocument();
});

test("shows not found for someone else's interview", async () => {
  getInterview.mockRejectedValue({ response: { status: 404, data: { detail: 'Interview not found.' } } });
  render(<InterviewRoom interviewId="other" />);
  expect(await screen.findByText('Interview not found')).toBeInTheDocument();
});

// ---------------------------------------------------------------------------
// Voice mode
// ---------------------------------------------------------------------------

class FakeMediaRecorder {
  static isTypeSupported() {
    return true;
  }

  constructor(stream, options = {}) {
    this.state = 'inactive';
    this.mimeType = options.mimeType || 'audio/webm';
  }

  start() {
    this.state = 'recording';
  }

  stop() {
    this.state = 'inactive';
    this.ondataavailable?.({ data: new Blob([new Uint8Array(4096)], { type: 'audio/webm' }) });
    this.onstop?.();
  }
}

function installMedia({ getUserMedia }) {
  window.MediaRecorder = FakeMediaRecorder;
  Object.defineProperty(navigator, 'mediaDevices', { value: { getUserMedia }, configurable: true });
  URL.createObjectURL = jest.fn(() => 'blob:recording');
  URL.revokeObjectURL = jest.fn();
}

function uninstallMedia() {
  delete window.MediaRecorder;
  Object.defineProperty(navigator, 'mediaDevices', { value: undefined, configurable: true });
}

afterEach(uninstallMedia);

test('voice mode records, transcribes, and lets the user review the transcript before submitting', async () => {
  const stopTrack = jest.fn();
  installMedia({ getUserMedia: jest.fn().mockResolvedValue({ getTracks: () => [{ stop: stopTrack }] }) });
  getInterview.mockResolvedValue(makeInterview({ interaction_mode: 'VOICE' }));
  transcribeInterviewAudio.mockResolvedValue({ transcript: 'I would add an index', duration_seconds: 4 });
  submitInterviewAnswer.mockResolvedValue({ answer: { ...EVALUATED, answer_source: 'VOICE' }, interview: answeredInterview(EVALUATED, { can_request_next_question: false }) });

  render(<InterviewRoom interviewId="iv-1" />);
  fireEvent.click(await screen.findByRole('button', { name: /start recording/i }));
  expect(await screen.findByText('Recording')).toBeInTheDocument();
  expect(screen.getByLabelText('Elapsed recording time')).toHaveTextContent('00:00 / 03:00');

  await act(async () => {
    fireEvent.click(screen.getByRole('button', { name: /stop recording/i }));
  });
  expect(stopTrack).toHaveBeenCalled(); // microphone released
  expect(await screen.findByText(/transcript ready/i)).toBeInTheDocument();
  expect(screen.getByLabelText('Playback of your recording')).toBeInTheDocument();

  const transcript = screen.getByLabelText(/transcript — review and edit/i);
  expect(transcript).toHaveValue('I would add an index');
  fireEvent.change(transcript, { target: { value: 'I would add a composite index' } });
  fireEvent.click(screen.getByRole('button', { name: /submit answer/i }));
  await waitFor(() =>
    expect(submitInterviewAnswer).toHaveBeenCalledWith('iv-1', {
      questionId: 'q1',
      answerText: 'I would add a composite index',
      answerSource: 'VOICE',
    })
  );
});

test('voice mode can cancel a recording', async () => {
  installMedia({ getUserMedia: jest.fn().mockResolvedValue({ getTracks: () => [{ stop: jest.fn() }] }) });
  getInterview.mockResolvedValue(makeInterview({ interaction_mode: 'VOICE' }));
  render(<InterviewRoom interviewId="iv-1" />);
  fireEvent.click(await screen.findByRole('button', { name: /start recording/i }));
  await screen.findByText('Recording');
  await act(async () => {
    fireEvent.click(screen.getByRole('button', { name: /cancel/i }));
  });
  expect(await screen.findByRole('button', { name: /start recording/i })).toBeInTheDocument();
  expect(transcribeInterviewAudio).not.toHaveBeenCalled();
});

test('voice mode explains a denied microphone permission and keeps typing available', async () => {
  const denied = Object.assign(new Error('denied'), { name: 'NotAllowedError' });
  installMedia({ getUserMedia: jest.fn().mockRejectedValue(denied) });
  getInterview.mockResolvedValue(makeInterview({ interaction_mode: 'VOICE' }));
  render(<InterviewRoom interviewId="iv-1" />);
  fireEvent.click(await screen.findByRole('button', { name: /start recording/i }));
  expect(await screen.findByText(/microphone access was blocked/i)).toBeInTheDocument();
  expect(screen.getByLabelText(/transcript — review and edit/i)).not.toBeDisabled();
});

test('voice mode falls back to typing when the browser cannot record', async () => {
  getInterview.mockResolvedValue(makeInterview({ interaction_mode: 'VOICE' }));
  render(<InterviewRoom interviewId="iv-1" />);
  expect(await screen.findByText(/this browser cannot record audio/i)).toBeInTheDocument();
  expect(screen.queryByRole('button', { name: /start recording/i })).not.toBeInTheDocument();
});

test('voice mode falls back to typing when transcription is unavailable', async () => {
  installMedia({ getUserMedia: jest.fn().mockResolvedValue({ getTracks: () => [{ stop: jest.fn() }] }) });
  getInterview.mockResolvedValue(makeInterview({ interaction_mode: 'VOICE' }));
  transcribeInterviewAudio.mockRejectedValue({
    response: { status: 503, data: { detail: { message: 'Speech transcription is not configured.', stage: 'transcription_unavailable' } } },
  });
  render(<InterviewRoom interviewId="iv-1" />);
  fireEvent.click(await screen.findByRole('button', { name: /start recording/i }));
  await screen.findByText('Recording');
  await act(async () => {
    fireEvent.click(screen.getByRole('button', { name: /stop recording/i }));
  });
  expect(await screen.findByText(/voice transcription is unavailable right now/i)).toBeInTheDocument();
});
