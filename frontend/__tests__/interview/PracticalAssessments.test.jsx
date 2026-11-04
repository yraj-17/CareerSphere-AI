import React from 'react';
import { fireEvent, render, screen, waitFor, within } from '@testing-library/react';

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
  useRouter: () => ({ push: jest.fn() }),
}));

jest.mock('@/services/api', () => ({
  completeInterview: jest.fn(),
  extractErrorMessage: jest.fn((err) => err?.message || 'Error'),
  getInterview: jest.fn(),
  navigateInterview: jest.fn(),
  retryInterviewEvaluation: jest.fn(),
  saveInterviewDraft: jest.fn(),
  submitInterviewAnswer: jest.fn(),
  transcribeInterviewAudio: jest.fn(),
}));

import { getInterview, navigateInterview, saveInterviewDraft, submitInterviewAnswer } from '@/services/api';
import InterviewRoom from '@/components/interview/InterviewRoom';
import AnswerFeedback from '@/components/interview/AnswerFeedback';

const CALC_VIEW = {
  type: 'calculation',
  available: true,
  label: 'Auto-graded — calculated deterministically with Python ipaddress',
  title: 'Same subnet?',
  prompt: 'Host A is 10.0.5.10 and host B is 10.0.6.1, both using subnet mask 255.255.255.0.',
  task_type: 'same_subnet',
  conventions: 'Usable hosts exclude the network and broadcast addresses.',
  fields: [
    { key: 'same_subnet', label: 'Same subnet?', hint: 'yes or no', options: ['yes', 'no'] },
    { key: 'network_a', label: 'Network address of host A', hint: 'dotted decimal' },
  ],
};

const SCENARIO_VIEW = {
  type: 'scenario',
  available: true,
  label: 'AI-reviewed — not executed',
  title: 'A container keeps restarting',
  context: 'STATUS: Restarting (137) 4 seconds ago',
  tasks: ['Explain exit code 137.', 'Review the Dockerfile.'],
  deliverable: 'A written answer addressing every task.',
  estimated_minutes: 15,
  criteria: ['Correct diagnosis', 'Dockerfile review'],
};

function q(order, overrides = {}) {
  return {
    id: `q${order}`,
    question_order: order,
    question_text: `Question ${order}?`,
    category: 'TECHNICAL',
    kind: 'question',
    assessment_available: true,
    competency: `Competency ${order}`,
    difficulty: 'INTERMEDIATE',
    interviewer_context: null,
    created_at: '2026-11-04T10:00:00Z',
    answer: null,
    status: 'NOT_STARTED',
    draft_text: null,
    draft_meta: null,
    draft_revision: 0,
    practical: null,
    ...overrides,
  };
}

function interview(questions) {
  const now = new Date();
  return {
    id: 'iv-1',
    target_role: 'Network Engineer',
    interview_type: 'TECHNICAL',
    interaction_mode: 'TEXT',
    difficulty: 'INTERMEDIATE',
    duration_minutes: 15,
    status: 'IN_PROGRESS',
    started_at: now.toISOString(),
    deadline_at: new Date(now.getTime() + 15 * 60 * 1000).toISOString(),
    server_time: now.toISOString(),
    answered_count: 0,
    max_questions: questions.length,
    current_question: questions[0],
    current_position: 1,
    preparing: false,
    blueprint: { question_slots: questions.map((x) => ({ position: x.question_order, kind: x.kind, competency: x.competency })) },
    questions,
  };
}

function setup(data) {
  getInterview.mockResolvedValue(data);
  navigateInterview.mockImplementation((id, position) => Promise.resolve({ ...data, current_position: position }));
  saveInterviewDraft.mockImplementation((id, qid, { revision }) => Promise.resolve({ question_id: qid, saved: true, revision }));
  return render(<InterviewRoom interviewId="iv-1" />);
}

beforeEach(() => jest.clearAllMocks());

test('a calculation is answered in structured fields, autosaved and submitted as structured answers', async () => {
  setup(interview([q(1, { kind: 'calculation', question_text: 'Practical calculation: Same subnet?', practical: CALC_VIEW })]));
  expect(await screen.findByText(CALC_VIEW.label)).toBeInTheDocument();
  expect(screen.queryByLabelText('Your answer')).not.toBeInTheDocument(); // no free-text box
  const submit = screen.getByRole('button', { name: /submit answers/i });
  expect(submit).toBeDisabled();

  fireEvent.change(screen.getByLabelText('Same subnet?'), { target: { value: 'no' } });
  fireEvent.change(screen.getByLabelText('Network address of host A'), { target: { value: '10.0.5.0' } });
  await waitFor(() =>
    expect(saveInterviewDraft).toHaveBeenCalledWith(
      'iv-1', 'q1', expect.objectContaining({ meta: { answers: { same_subnet: 'no', network_a: '10.0.5.0' } } })
    )
  );
  expect(within(screen.getByRole('list', { name: 'Questions' })).getByRole('button', { name: 'Question 1, In progress' })).toBeInTheDocument();

  submitInterviewAnswer.mockReturnValue(new Promise(() => {}));
  fireEvent.click(submit);
  expect(submitInterviewAnswer).toHaveBeenCalledWith('iv-1', {
    questionId: 'q1',
    structuredAnswer: { same_subnet: 'no', network_a: '10.0.5.0' },
    answerSource: 'TEXT',
  });
});

test('a restored calculation draft repopulates the fields', async () => {
  setup(interview([q(1, { kind: 'calculation', practical: CALC_VIEW, draft_meta: { answers: { network_a: '10.0.5.0' } }, draft_revision: 4, status: 'IN_PROGRESS' })]));
  expect(await screen.findByLabelText('Network address of host A')).toHaveValue('10.0.5.0');
});

test('a scenario shows its situation, tasks and the AI-reviewed label, and is answered in writing', async () => {
  setup(interview([q(1, { kind: 'scenario', question_text: 'Practical scenario: A container keeps restarting', practical: SCENARIO_VIEW })]));
  expect(await screen.findByText('AI-reviewed — not executed')).toBeInTheDocument();
  expect(screen.getByText('STATUS: Restarting (137) 4 seconds ago')).toBeInTheDocument();
  expect(screen.getByText('Review the Dockerfile.')).toBeInTheDocument();
  expect(screen.getByText(/nothing is executed/i)).toBeInTheDocument();
  fireEvent.change(screen.getByLabelText('Your answer'), { target: { value: 'It was OOM killed.' } });
  submitInterviewAnswer.mockReturnValue(new Promise(() => {}));
  fireEvent.click(screen.getByRole('button', { name: /submit answer/i }));
  expect(submitInterviewAnswer).toHaveBeenCalledWith('iv-1', { questionId: 'q1', answerText: 'It was OOM killed.', answerSource: 'TEXT' });
});

test('an unavailable practical slot explains why instead of offering an answer box', async () => {
  const reason = 'No verified problem or validated assessment is available for this role and competency yet.';
  setup(interview([
    q(1),
    q(2, { kind: 'scenario', assessment_available: false, status: 'UNAVAILABLE', competency: 'Core Practice', practical: { type: 'scenario', available: false, reason } }),
    q(3, { kind: 'coding', assessment_available: false, status: 'UNAVAILABLE', competency: 'JavaScript',
      practical: { type: 'coding', available: true, title: 'Parse URL Query Strings', difficulty: 'MEDIUM', languages: ['JAVASCRIPT'] } }),
  ]));
  await screen.findByText('Question 1?');
  fireEvent.click(screen.getByRole('button', { name: /next question/i }));
  expect(await screen.findByText(new RegExp(reason.slice(0, 40)))).toBeInTheDocument();
  expect(screen.queryByLabelText('Your answer')).not.toBeInTheDocument();
  fireEvent.click(screen.getByRole('button', { name: /next question/i }));
  expect(await screen.findByText('Parse URL Query Strings')).toBeInTheDocument();
  expect(screen.getByText(/code submission isn.t available for this slot/i)).toBeInTheDocument();
});

test('feedback shows deterministic field results and rubric criteria with their labels', () => {
  const base = { id: 'a', question_id: 'q', answer_text: '', answer_source: 'TEXT', submitted_at: '', evaluation_status: 'COMPLETED', can_retry_evaluation: false };
  const { rerender } = render(
    <AnswerFeedback answer={{ ...base, score: 50, evaluation: {
      score: 50, method: 'deterministic', label: CALC_VIEW.label, correct: 1, total: 2,
      fields: [
        { key: 'same_subnet', label: 'Same subnet?', given: 'yes', expected: 'no', correct: false },
        { key: 'network_a', label: 'Network address of host A', given: '10.0.5.0', expected: '10.0.5.0', correct: true },
      ],
      strengths: [], improvements: ['Re-check: Same subnet?.'], feedback: 'Review the fields marked incorrect.', key_points: [],
    } }} />
  );
  expect(screen.getByText(CALC_VIEW.label)).toBeInTheDocument();
  expect(screen.getByText('Incorrect')).toBeInTheDocument();
  expect(screen.getByText('Correct')).toBeInTheDocument();

  rerender(
    <AnswerFeedback answer={{ ...base, score: 85, evaluation: {
      score: 85, method: 'ai_rubric', label: 'AI-reviewed — not executed',
      criteria: [{ id: 'diagnosis', title: 'Correct diagnosis', points: 30, score: 50, comment: 'Partly right.' }],
      strengths: [], improvements: [], feedback: 'Add verification steps.', key_points: [],
    } }} />
  );
  expect(screen.getByText('AI-reviewed — not executed')).toBeInTheDocument();
  expect(screen.getByText('50/100 · weight 30%')).toBeInTheDocument();
  expect(screen.queryByText(/tests passed/i)).not.toBeInTheDocument();
});

describe('difficulty fallback disclosure', () => {
  const { DifficultyNote, PracticalUnavailable } = require('@/components/interview/PracticalTask');

  test('an assigned problem below the planned level says so', () => {
    render(
      <PracticalUnavailable
        question={{
          kind: 'coding',
          competency: 'Scripting & Automation',
          practical: {
            type: 'coding', available: true, title: 'Organise a downloads folder',
            difficulty: 'MEDIUM', planned_difficulty: 'HARD', difficulty_fallback: true, languages: ['BASH'],
          },
        }}
      />,
    );
    const note = screen.getByRole('note');
    expect(note).toHaveTextContent('Difficulty: Medium');
    expect(note).toHaveTextContent('calls for Hard');
    expect(note).toHaveTextContent('recorded in your report');
  });

  test('no notice when the planned level was met', () => {
    render(<DifficultyNote practical={{ difficulty: 'HARD', planned_difficulty: 'HARD', difficulty_fallback: false }} />);
    expect(screen.queryByRole('note')).toBeNull();
  });
});
