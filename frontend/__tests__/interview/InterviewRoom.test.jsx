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
  navigateInterview: jest.fn(),
  retryInterviewEvaluation: jest.fn(),
  saveInterviewDraft: jest.fn(),
  submitInterviewAnswer: jest.fn(),
  transcribeInterviewAudio: jest.fn(),
}));

import {
  completeInterview,
  getInterview,
  navigateInterview,
  retryInterviewEvaluation,
  saveInterviewDraft,
  submitInterviewAnswer,
  transcribeInterviewAudio,
} from '@/services/api';
import InterviewRoom from '@/components/interview/InterviewRoom';

function question(order, overrides = {}) {
  return {
    id: `q${order}`,
    question_order: order,
    question_text: `Question text number ${order}?`,
    category: 'TECHNICAL',
    kind: 'question',
    assessment_available: true,
    competency: `Competency ${order}`,
    difficulty: 'INTERMEDIATE',
    interviewer_context: null,
    created_at: '2026-11-01T10:00:00Z',
    answer: null,
    status: 'NOT_STARTED',
    draft_text: null,
    draft_revision: 0,
    ...overrides,
  };
}

const reserved = (order, competency) =>
  question(order, {
    kind: 'coding',
    assessment_available: false,
    status: 'UNAVAILABLE',
    competency,
    question_text: `Coding assessment: ${competency}`,
  });

const EVALUATED = {
  id: 'a1',
  question_id: 'q1',
  answer_text: 'Use an index.',
  answer_source: 'TEXT',
  submitted_at: '2026-11-01T10:01:00Z',
  evaluation_status: 'COMPLETED',
  score: 77,
  evaluation: {
    score: 77,
    dimensions: { accuracy: 90, reasoning: 60, relevance: 80, clarity: 70, structure: null, reflection: null },
    strengths: ['Mentioned indexes'],
    improvements: ['Discuss trade-offs'],
    feedback: 'Solid start. Explain how you would verify the improvement.',
    key_points: [],
  },
  can_retry_evaluation: false,
};

function allQuestions(overrides = {}) {
  return [
    question(1, overrides[1]),
    reserved(2, 'Data Structures'),
    question(3, overrides[3]),
    question(4, overrides[4]),
    reserved(5, 'Algorithms & Problem Solving'),
    question(6, overrides[6]),
  ];
}

function makeInterview(overrides = {}) {
  const now = new Date();
  const questions = overrides.questions || allQuestions();
  const answered = questions.filter((q) => q.answer).length;
  return {
    id: 'iv-1',
    target_role: 'Software Development Engineer',
    interview_type: 'TECHNICAL',
    interaction_mode: 'TEXT',
    difficulty: 'INTERMEDIATE',
    duration_minutes: 15,
    status: 'IN_PROGRESS',
    started_at: now.toISOString(),
    deadline_at: new Date(now.getTime() + 15 * 60 * 1000).toISOString(),
    completed_at: null,
    final_score: null,
    question_count: questions.length,
    answered_count: answered,
    report_status: null,
    focus_areas: [],
    instructions: null,
    max_questions: 6,
    server_time: now.toISOString(),
    remaining_seconds: 900,
    current_question: questions.find((q) => !q.answer && q.assessment_available) || null,
    can_request_next_question: false,
    current_position: null,
    preparing: false,
    blueprint: {
      question_slots: [1, 2, 3, 4, 5, 6].map((p) => ({
        position: p,
        kind: [2, 5].includes(p) ? 'coding' : 'question',
        competency: questions.find((q) => q.question_order === p)?.competency || `Planned ${p}`,
      })),
    },
    questions,
    ...overrides,
  };
}

function questionNav() {
  return screen.getByRole('list', { name: 'Questions' });
}

function setupRoom(interview = makeInterview()) {
  getInterview.mockResolvedValue(interview);
  navigateInterview.mockImplementation((id, position) => Promise.resolve({ ...interview, current_position: position }));
  saveInterviewDraft.mockImplementation((id, qid, { revision }) => Promise.resolve({ question_id: qid, saved: true, revision }));
  return render(<InterviewRoom interviewId="iv-1" />);
}

beforeEach(() => {
  jest.clearAllMocks();
});

test('renders the navigator, timer and progress for every planned question', async () => {
  setupRoom();
  expect(await screen.findByText('Question text number 1?')).toBeInTheDocument();
  expect(screen.getByRole('timer')).toHaveTextContent(/1[45]:\d\d/);
  expect(screen.getByText('Question 1 of 6')).toBeInTheDocument();
  const buttons = within(questionNav()).getAllByRole('button');
  expect(buttons).toHaveLength(6);
  expect(buttons[0]).toHaveAttribute('aria-current', 'step');
  expect(buttons[1]).toHaveAccessibleName('Question 2, Not available');
  expect(screen.getByRole('button', { name: /previous question/i })).toBeDisabled();
  expect(screen.getByRole('button', { name: /next question/i })).toBeEnabled();
  expect(screen.getByRole('button', { name: /submit answer/i })).toBeDisabled();
});

test('next and previous only navigate: nothing is submitted, evaluated or generated', async () => {
  setupRoom();
  await screen.findByText('Question text number 1?');
  fireEvent.click(screen.getByRole('button', { name: /next question/i }));
  expect(await screen.findByText(/coding assessment · data structures/i)).toBeInTheDocument();
  expect(screen.queryByLabelText('Your answer')).not.toBeInTheDocument(); // reserved practical slot
  fireEvent.click(screen.getByRole('button', { name: /next question/i }));
  expect(screen.getByText('Question text number 3?')).toBeInTheDocument();
  fireEvent.click(screen.getByRole('button', { name: /previous question/i }));
  fireEvent.click(screen.getByRole('button', { name: /previous question/i }));
  expect(screen.getByText('Question text number 1?')).toBeInTheDocument();

  const positions = navigateInterview.mock.calls.map((call) => call[1]);
  expect(positions.slice(-4)).toEqual([2, 3, 2, 1]);
  const seqs = navigateInterview.mock.calls.map((call) => call[2]);
  expect([...seqs].sort((a, b) => a - b)).toEqual(seqs); // strictly increasing sequence numbers
  expect(new Set(seqs).size).toBe(seqs.length);
  expect(submitInterviewAnswer).not.toHaveBeenCalled();
  expect(retryInterviewEvaluation).not.toHaveBeenCalled();
});

test('a draft survives navigating away and back, and is saved when leaving', async () => {
  setupRoom();
  const editor = await screen.findByLabelText('Your answer');
  fireEvent.change(editor, { target: { value: 'First idea.\nSecond line.' } });
  fireEvent.click(within(questionNav()).getByRole('button', { name: /question 3/i }));
  await waitFor(() =>
    expect(saveInterviewDraft).toHaveBeenCalledWith('iv-1', 'q1', expect.objectContaining({ text: 'First idea.\nSecond line.' }))
  );
  expect(screen.getByText('Question text number 3?')).toBeInTheDocument();
  expect(screen.getByLabelText('Your answer')).toHaveValue('');
  expect(within(questionNav()).getByRole('button', { name: 'Question 1, In progress' })).toBeInTheDocument();

  fireEvent.click(screen.getByRole('button', { name: /previous question/i }));
  fireEvent.click(screen.getByRole('button', { name: /previous question/i }));
  expect(screen.getByLabelText('Your answer')).toHaveValue('First idea.\nSecond line.');
  expect(submitInterviewAnswer).not.toHaveBeenCalled();
});

test('autosave keeps newer local text when the server reports a stale save', async () => {
  setupRoom();
  saveInterviewDraft.mockImplementation((id, qid, { revision }) => Promise.resolve({ question_id: qid, saved: false, revision: revision + 100 }));
  fireEvent.change(await screen.findByLabelText('Your answer'), { target: { value: 'typing...' } });
  expect(screen.getByText('Unsaved changes')).toBeInTheDocument();
  await waitFor(() => expect(saveInterviewDraft).toHaveBeenCalled(), { timeout: 2000 });
  expect(await screen.findByText('Unsaved changes')).toBeInTheDocument();
  expect(screen.getByLabelText('Your answer')).toHaveValue('typing...');
});

test('autosave confirms when the draft is stored', async () => {
  setupRoom();
  fireEvent.change(await screen.findByLabelText('Your answer'), { target: { value: 'saved text' } });
  expect(await screen.findByText('Draft saved', {}, { timeout: 2500 })).toBeInTheDocument();
});

test('jump directly to a question, and the last question offers finish instead of next', async () => {
  setupRoom();
  await screen.findByText('Question text number 1?');
  fireEvent.click(within(questionNav()).getByRole('button', { name: /question 6/i }));
  expect(screen.getByText('Question text number 6?')).toBeInTheDocument();
  expect(screen.getByText('Question 6 of 6')).toBeInTheDocument();
  expect(screen.getByRole('button', { name: /next question/i })).toBeDisabled();
  expect(screen.getByRole('button', { name: /finish interview/i })).toBeInTheDocument();
  expect(navigateInterview).toHaveBeenLastCalledWith('iv-1', 6, expect.any(Number));
});

test('refresh/resume restores the saved position and server drafts', async () => {
  setupRoom(makeInterview({ current_position: 4, questions: allQuestions({ 4: { draft_text: 'resumed draft', status: 'IN_PROGRESS', draft_revision: 5 } }) }));
  expect(await screen.findByText('Question text number 4?')).toBeInTheDocument();
  expect(screen.getByLabelText('Your answer')).toHaveValue('resumed draft');
  expect(screen.getByText('Question 4 of 6')).toBeInTheDocument();
});

test('submitting is separate; submitted answers are read-only on revisit', async () => {
  const after = makeInterview({ questions: allQuestions({ 1: { answer: EVALUATED, status: 'ANSWERED' } }) });
  let state = makeInterview();
  setupRoom(state);
  navigateInterview.mockImplementation((id, position) => Promise.resolve({ ...state, current_position: position }));
  submitInterviewAnswer.mockImplementation(() => {
    state = after;
    return Promise.resolve({ answer: EVALUATED, interview: after });
  });

  fireEvent.change(await screen.findByLabelText('Your answer'), { target: { value: 'Use an index.' } });
  fireEvent.click(screen.getByRole('button', { name: /submit answer/i }));
  expect(await screen.findByLabelText('Answer feedback')).toBeInTheDocument();
  expect(submitInterviewAnswer).toHaveBeenCalledTimes(1);
  expect(submitInterviewAnswer).toHaveBeenCalledWith('iv-1', { questionId: 'q1', answerText: 'Use an index.', answerSource: 'TEXT' });
  expect(screen.queryByLabelText('Your answer')).not.toBeInTheDocument();
  expect(within(questionNav()).getByRole('button', { name: 'Question 1, Answered' })).toBeInTheDocument();

  fireEvent.click(screen.getByRole('button', { name: /next question/i }));
  fireEvent.click(screen.getByRole('button', { name: /previous question/i }));
  expect(screen.getByText('Your submitted answer')).toBeInTheDocument();
  expect(submitInterviewAnswer).toHaveBeenCalledTimes(1); // revisiting never resubmits
});

test('the timer keeps running across navigation and never resets', async () => {
  const interview = makeInterview({ deadline_at: new Date(Date.now() + 10 * 60 * 1000).toISOString() });
  setupRoom(interview);
  await screen.findByText('Question text number 1?');
  const before = screen.getByRole('timer').textContent;
  fireEvent.click(screen.getByRole('button', { name: /next question/i }));
  fireEvent.click(screen.getByRole('button', { name: /next question/i }));
  await waitFor(() => expect(navigateInterview).toHaveBeenCalledTimes(3));
  const after = screen.getByRole('timer').textContent;
  expect(after <= before).toBe(true);
  expect(before).toMatch(/^(09|10):\d\d$/);
});

test('finishing summarises answered, unanswered and draft-only questions and allows going back', async () => {
  setupRoom(
    makeInterview({
      questions: allQuestions({
        1: { answer: EVALUATED, status: 'ANSWERED' },
        3: { draft_text: 'half done', status: 'IN_PROGRESS', draft_revision: 3 },
      }),
    })
  );
  await screen.findByText('Question text number 3?'); // opens the first unanswered question
  fireEvent.click(screen.getByRole('button', { name: /end interview/i }));
  const dialog = screen.getByRole('dialog', { name: /finish this interview/i });
  expect(within(dialog).getByText('Answered').nextSibling).toHaveTextContent('1');
  expect(within(dialog).getByText('Unanswered').nextSibling).toHaveTextContent('3');
  expect(within(dialog).getByText(/saved drafts that were not submitted/i)).toBeInTheDocument();

  fireEvent.click(within(dialog).getByRole('button', { name: 'Go to question 3' }));
  expect(screen.queryByRole('dialog')).not.toBeInTheDocument();
  expect(screen.getByLabelText('Your answer')).toHaveValue('half done');
  expect(completeInterview).not.toHaveBeenCalled();

  completeInterview.mockResolvedValue({ ...makeInterview(), status: 'COMPLETED', answered_count: 1 });
  fireEvent.click(screen.getByRole('button', { name: /end interview/i }));
  fireEvent.click(within(screen.getByRole('dialog')).getByRole('button', { name: /finish interview/i }));
  await waitFor(() => expect(mockPush).toHaveBeenCalledWith('/dashboard/interview/iv-1/results'));
});

test('when time runs out every saved draft is submitted, then the interview ends', async () => {
  const now = new Date();
  const interview = makeInterview({
    server_time: now.toISOString(),
    deadline_at: now.toISOString(),
    questions: allQuestions({
      1: { draft_text: 'draft one', status: 'IN_PROGRESS', draft_revision: 1 },
      4: { draft_text: 'draft four', status: 'IN_PROGRESS', draft_revision: 1 },
    }),
  });
  setupRoom(interview);
  submitInterviewAnswer.mockImplementation(() => Promise.resolve({ answer: EVALUATED, interview }));
  completeInterview.mockResolvedValue({ ...interview, status: 'EXPIRED', answered_count: 2 });

  await waitFor(() => expect(completeInterview).toHaveBeenCalled());
  const submitted = submitInterviewAnswer.mock.calls.map((call) => call[1].answerText).sort();
  expect(submitted).toEqual(['draft four', 'draft one']);
  await waitFor(() => expect(mockPush).toHaveBeenCalledWith('/dashboard/interview/iv-1/results'));
});

test('a question still being prepared shows a preparing state until it is ready', async () => {
  const partial = makeInterview({ questions: [question(1)], preparing: true });
  setupRoom(partial);
  await screen.findByText('Question text number 1?');
  getInterview.mockResolvedValue(makeInterview());
  fireEvent.click(within(questionNav()).getByRole('button', { name: 'Question 3, Preparing' }));
  expect(screen.getByText(/preparing question 3/i)).toBeInTheDocument();
  expect(await screen.findByText('Question text number 3?', {}, { timeout: 4000 })).toBeInTheDocument();
});

test('shows a recoverable state when evaluation fails and retries it', async () => {
  const failed = { ...EVALUATED, evaluation_status: 'FAILED', score: null, evaluation: null, can_retry_evaluation: true };
  getInterview.mockResolvedValueOnce(makeInterview({ current_position: 1, questions: allQuestions({ 1: { answer: failed, status: 'SUBMITTED' } }) }));
  navigateInterview.mockImplementation(() => new Promise(() => {}));
  render(<InterviewRoom interviewId="iv-1" />);
  getInterview.mockResolvedValue(makeInterview({ current_position: 1, questions: allQuestions({ 1: { answer: EVALUATED, status: 'ANSWERED' } }) }));
  retryInterviewEvaluation.mockResolvedValue(EVALUATED);
  expect(await screen.findByText(/your answer was saved, but feedback isn't available yet/i)).toBeInTheDocument();
  fireEvent.click(screen.getByRole('button', { name: /retry evaluation/i }));
  await waitFor(() => expect(retryInterviewEvaluation).toHaveBeenCalledWith('iv-1', 'a1'));
  expect(await screen.findByLabelText('Answer feedback')).toBeInTheDocument();
});

test('renders the expired state for a session the server has closed', async () => {
  getInterview.mockResolvedValue(makeInterview({ status: 'EXPIRED', questions: allQuestions({ 1: { answer: EVALUATED, status: 'ANSWERED' } }) }));
  render(<InterviewRoom interviewId="iv-1" />);
  expect(await screen.findByText('Time limit reached')).toBeInTheDocument();
  expect(screen.getByRole('link', { name: /view report/i })).toHaveAttribute('href', '/dashboard/interview/iv-1/results');
  expect(navigateInterview).not.toHaveBeenCalled();
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

afterEach(() => {
  delete window.MediaRecorder;
  Object.defineProperty(navigator, 'mediaDevices', { value: undefined, configurable: true });
});

test('voice mode records, transcribes, and lets the user review the transcript before submitting', async () => {
  const stopTrack = jest.fn();
  installMedia({ getUserMedia: jest.fn().mockResolvedValue({ getTracks: () => [{ stop: stopTrack }] }) });
  setupRoom(makeInterview({ interaction_mode: 'VOICE' }));
  transcribeInterviewAudio.mockResolvedValue({ transcript: 'I would add an index', duration_seconds: 4 });
  submitInterviewAnswer.mockResolvedValue({ answer: EVALUATED, interview: makeInterview({ interaction_mode: 'VOICE' }) });

  fireEvent.click(await screen.findByRole('button', { name: /start recording/i }));
  expect(await screen.findByText('Recording')).toBeInTheDocument();
  await act(async () => {
    fireEvent.click(screen.getByRole('button', { name: /stop recording/i }));
  });
  expect(stopTrack).toHaveBeenCalled();
  expect(await screen.findByText(/transcript ready/i)).toBeInTheDocument();
  const transcript = screen.getByLabelText(/transcript — review and edit/i);
  expect(transcript).toHaveValue('I would add an index');
  fireEvent.change(transcript, { target: { value: 'I would add a composite index' } });
  fireEvent.click(screen.getByRole('button', { name: /submit answer/i }));
  await waitFor(() =>
    expect(submitInterviewAnswer).toHaveBeenCalledWith('iv-1', { questionId: 'q1', answerText: 'I would add a composite index', answerSource: 'VOICE' })
  );
});

test('voice mode explains a denied microphone permission and keeps typing available', async () => {
  const denied = Object.assign(new Error('denied'), { name: 'NotAllowedError' });
  installMedia({ getUserMedia: jest.fn().mockRejectedValue(denied) });
  setupRoom(makeInterview({ interaction_mode: 'VOICE' }));
  fireEvent.click(await screen.findByRole('button', { name: /start recording/i }));
  expect(await screen.findByText(/microphone access was blocked/i)).toBeInTheDocument();
  expect(screen.getByLabelText(/transcript — review and edit/i)).not.toBeDisabled();
});

test('voice mode falls back to typing when the browser cannot record', async () => {
  setupRoom(makeInterview({ interaction_mode: 'VOICE' }));
  expect(await screen.findByText(/this browser cannot record audio/i)).toBeInTheDocument();
});

test('voice mode falls back to typing when transcription is unavailable', async () => {
  installMedia({ getUserMedia: jest.fn().mockResolvedValue({ getTracks: () => [{ stop: jest.fn() }] }) });
  setupRoom(makeInterview({ interaction_mode: 'VOICE' }));
  transcribeInterviewAudio.mockRejectedValue({
    response: { status: 503, data: { detail: { message: 'Speech transcription is not configured.', stage: 'transcription_unavailable' } } },
  });
  fireEvent.click(await screen.findByRole('button', { name: /start recording/i }));
  await screen.findByText('Recording');
  await act(async () => {
    fireEvent.click(screen.getByRole('button', { name: /stop recording/i }));
  });
  expect(await screen.findByText(/voice transcription is unavailable right now/i)).toBeInTheDocument();
});

test('voice transcripts stay with their own question when navigating', async () => {
  installMedia({ getUserMedia: jest.fn().mockResolvedValue({ getTracks: () => [{ stop: jest.fn() }] }) });
  setupRoom(makeInterview({ interaction_mode: 'VOICE' }));
  transcribeInterviewAudio.mockResolvedValue({ transcript: 'answer for one', duration_seconds: 2 });
  fireEvent.click(await screen.findByRole('button', { name: /start recording/i }));
  await screen.findByText('Recording');
  await act(async () => {
    fireEvent.click(screen.getByRole('button', { name: /stop recording/i }));
  });
  await screen.findByText(/transcript ready/i);
  fireEvent.click(within(questionNav()).getByRole('button', { name: /question 3/i }));
  expect(screen.getByLabelText(/transcript — review and edit/i)).toHaveValue('');
  fireEvent.click(within(questionNav()).getByRole('button', { name: /question 1/i }));
  expect(screen.getByLabelText(/transcript — review and edit/i)).toHaveValue('answer for one');
});
