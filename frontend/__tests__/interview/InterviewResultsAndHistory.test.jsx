import React from 'react';
import { fireEvent, render, screen, waitFor } from '@testing-library/react';

jest.mock('next/link', () => {
  const Link = ({ children, href, ...props }) => (
    <a href={href} {...props}>
      {children}
    </a>
  );
  Link.displayName = 'MockLink';
  return Link;
});

jest.mock('@/services/api', () => ({
  extractErrorMessage: jest.fn((err) => err?.message || 'Error'),
  generateInterviewReport: jest.fn(),
  getInterview: jest.fn(),
  getInterviewReport: jest.fn(),
  listInterviews: jest.fn(),
}));

import { generateInterviewReport, getInterview, getInterviewReport, listInterviews } from '@/services/api';
import InterviewResultsPage from '@/components/interview/InterviewResultsPage';
import InterviewHistoryPage, { HISTORY_PAGE_SIZE } from '@/components/interview/InterviewHistoryPage';

const ANSWER = {
  id: 'a1',
  question_id: 'q1',
  answer_text: 'Use an index',
  answer_source: 'TEXT',
  submitted_at: '2026-10-29T10:01:00Z',
  evaluation_status: 'COMPLETED',
  score: 72,
  evaluation: {
    score: 72,
    dimensions: { accuracy: 80, reasoning: 60, relevance: 75, clarity: 70, structure: null, reflection: null },
    strengths: ['Correct idea'],
    improvements: ['Give an example'],
    feedback: 'Good direction; quantify the impact.',
    key_points: [],
  },
  can_retry_evaluation: false,
};

const INTERVIEW = {
  id: 'iv-1',
  target_role: 'Backend Engineer',
  interview_type: 'MIXED',
  interaction_mode: 'TEXT',
  difficulty: 'INTERMEDIATE',
  duration_minutes: 15,
  status: 'COMPLETED',
  started_at: '2026-10-29T10:00:00Z',
  deadline_at: '2026-10-29T10:15:00Z',
  completed_at: '2026-10-29T10:10:00Z',
  final_score: 72,
  question_count: 2,
  answered_count: 1,
  report_status: 'COMPLETED',
  max_questions: 6,
  questions: [
    { id: 'q1', question_order: 1, question_text: 'Speed up a query?', category: 'TECHNICAL', competency: 'SQL', difficulty: 'INTERMEDIATE', created_at: '', answer: ANSWER },
    { id: 'q2', question_order: 2, question_text: 'Tell me about a conflict.', category: 'BEHAVIORAL', competency: 'Teamwork', difficulty: 'INTERMEDIATE', created_at: '', answer: null },
  ],
};

const REPORT = {
  interview_id: 'iv-1',
  status: 'COMPLETED',
  overall_score: 72,
  aggregates: {
    question_count: 2,
    answered_count: 1,
    evaluated_count: 1,
    dimension_scores: { accuracy: 80, reasoning: 60, relevance: 75, clarity: 70, structure: null, reflection: null },
    category_scores: { TECHNICAL: 72, BEHAVIORAL: null },
    strongest: [{ question_id: 'q1', question_order: 1, competency: 'SQL', category: 'TECHNICAL', score: 72 }],
    weakest: [],
    methodology: 'Mean of evaluated answer scores.',
  },
  narrative: {
    summary: 'You communicated a correct approach to query tuning.',
    strengths: ['Database fundamentals'],
    weaknesses: ['Few concrete examples'],
    repeated_gaps: [],
    improvement_plan: ['Practice explaining with metrics'],
    topics_to_revise: ['Query plans'],
  },
  generated_at: '2026-10-29T10:11:00Z',
  can_retry: false,
  score_scale: 'Scores are 0-100 AI-generated practice feedback. They are not a hiring decision.',
};

beforeEach(() => jest.clearAllMocks());

describe('InterviewResultsPage', () => {
  test('renders the final report and question-by-question feedback', async () => {
    getInterview.mockResolvedValue(INTERVIEW);
    getInterviewReport.mockResolvedValue(REPORT);
    render(<InterviewResultsPage interviewId="iv-1" />);

    expect(await screen.findByText('You communicated a correct approach to query tuning.')).toBeInTheDocument();
    expect(screen.getByRole('heading', { name: /overall score/i })).toBeInTheDocument();
    expect(screen.getAllByText('72').length).toBeGreaterThan(0);
    expect(screen.getByText('1 of 1 answers scored · 2 questions asked')).toBeInTheDocument();
    expect(screen.getAllByRole('progressbar', { name: 'Technical accuracy' })[0]).toHaveAttribute('aria-valuenow', '80');
    expect(screen.queryByRole('progressbar', { name: 'Structure & specificity' })).not.toBeInTheDocument();
    expect(screen.getByText('Practice explaining with metrics')).toBeInTheDocument();
    expect(screen.getByText('Query plans')).toBeInTheDocument();
    expect(screen.getByText('Not answered')).toBeInTheDocument();
    expect(screen.getByText(/not a hiring decision/i)).toBeInTheDocument();
    expect(generateInterviewReport).not.toHaveBeenCalled(); // stored report, no model rerun
  });

  test('a coding answer shows the submitted code and its Judge0 result', async () => {
    const code = 'def count_pairs(values, target):\n    return 0\n';
    const codingAnswer = {
      ...ANSWER, id: 'a2', question_id: 'q3', answer_text: code, score: 100,
      evaluation: {
        score: 100, method: 'judge0', label: 'Executed on Judge0 — scored by test results', verdict: 'ACCEPTED', verdict_label: 'Accepted',
        correct: 8, total: 8, language: 'PYTHON', language_label: 'Python (3.8.1)', strengths: [], improvements: [],
        feedback: 'Accepted: 8 of 8 tests passed (Python (3.8.1)).', key_points: [],
      },
    };
    getInterview.mockResolvedValue({
      ...INTERVIEW,
      questions: [...INTERVIEW.questions, { id: 'q3', question_order: 3, question_text: 'Coding assessment: Pairs', category: 'TECHNICAL', kind: 'coding', competency: 'Data Structures', difficulty: 'INTERMEDIATE', created_at: '', answer: codingAnswer }],
    });
    const practical = {
      reserved: 1, reached: 1, assessed: 1, score: 100, available: true, kinds: ['coding'],
      items: [{ position: 3, kind: 'coding', competency: 'Data Structures', status: 'assessed', score: 100, method: 'judge0',
        difficulty: { difficulty: 'EASY', planned_difficulty: 'EASY', difficulty_fallback: false } }],
    };
    getInterviewReport.mockResolvedValue({
      ...REPORT,
      aggregates: { ...REPORT.aggregates, answered_count: 2, question_count: 3, sections: { practical } },
    });
    render(<InterviewResultsPage interviewId="iv-1" />);
    expect(await screen.findByText('Your submitted code · Python (3.8.1)')).toBeInTheDocument();
    // The overall score covers the conceptual answer; the coding answer is counted as practical.
    expect(screen.getByText('1 of 1 answers scored · 1 practical assessed separately · 3 questions asked')).toBeInTheDocument();
    expect(screen.getByText('100/100 · Executed on Judge0')).toBeInTheDocument();
    expect(screen.getByText((_, el) => el?.tagName === 'PRE' && el.textContent === code)).toBeInTheDocument();
    expect(screen.getByText('Executed on Judge0 — scored by test results')).toBeInTheDocument();
    expect(screen.getByText(/8 of 8 tests passed \(/)).toBeInTheDocument();
  });

  test('Phase 5 report: executive summary, separate dimensions, competencies and coding results', async () => {
    const review = {
      label: 'AI Code Review', status: 'COMPLETED', note: 'Correctness comes only from Judge0 execution; this review rates code quality and is not an execution result.',
      quality_score: 75, compiled: true, can_retry: false, summary: 'Readable query; add an index on orders.customer_id.',
      criteria: [{ id: 'efficiency', title: 'Algorithm efficiency', weight: 20, score: 60 }],
      strengths: ['Correct LEFT JOIN'], weaknesses: [], improvements: [], alternative_approaches: [], time_complexity: 'O(n log n)',
      space_complexity: 'O(n)', missing_edge_cases: [], recommendations: ['Index the join column'],
    };
    const coding = {
      items: [
        { question_order: 3, kind: 'sql', competency: 'SQL Queries', title: 'Customer Order Totals', difficulty: 'EASY',
          language: 'SQLITE', language_label: 'SQL (SQLite 3.27.2)', verdict: 'WRONG_ANSWER', verdict_label: 'Wrong Answer',
          tests_passed: 4, tests_total: 6, correctness_score: 66.7, quality_score: 75, coding_score: 69.2, max_time_seconds: 0.012,
          max_memory_kb: 1800, submission_attempts: 2, review_status: 'COMPLETED', review },
      ],
      correctness_score: 67, quality_score: 75, coding_score: 69, reviews_pending: 0, reviews_failed: 0,
    };
    const sqlAnswer = { ...ANSWER, id: 'a3', question_id: 'q3', answer_text: 'SELECT name FROM customers;', score: 69 };
    getInterview.mockResolvedValue({
      ...INTERVIEW,
      questions: [...INTERVIEW.questions, { id: 'q3', question_order: 3, question_text: 'SQL assessment: Totals', category: 'TECHNICAL', kind: 'sql', competency: 'SQL Queries', difficulty: 'INTERMEDIATE', created_at: '', answer: sqlAnswer }],
    });
    getInterviewReport.mockResolvedValue({
      ...REPORT,
      aggregates: {
        ...REPORT.aggregates,
        sections: { coding, practical: { reserved: 1, reached: 1, assessed: 1, score: 69, items: [] } },
        dimensions: { technical_knowledge: 72, practical_assessment: 69, coding_correctness: 67, code_quality: 75, problem_solving: 60, communication: 70, behavioral: null },
        competency_scores: [
          { competency: 'SQL', category: 'TECHNICAL', score: 72, level: 'Solid', questions: 1, evaluated: 1, strengths: ['Correct idea'], improvements: ['Give an example'] },
          { competency: 'Teamwork', category: 'BEHAVIORAL', score: null, level: null, questions: 1, evaluated: 0, strengths: [], improvements: [] },
        ],
      },
    });
    render(<InterviewResultsPage interviewId="iv-1" />);
    expect(await screen.findByRole('heading', { name: 'Executive summary' })).toBeInTheDocument();
    const dims = screen.getByLabelText('Evaluation dimensions');
    expect(dims).toHaveTextContent('Coding correctness (Judge0)67/100');
    expect(dims).toHaveTextContent('Code quality (AI review)75/100');
    expect(dims).toHaveTextContent('BehavioralNot assessed'); // never shown as 0
    expect(screen.getByLabelText('Competency analysis')).toHaveTextContent('72/100 · Solid');
    expect(screen.getByText(/Not assessed in this interview: Teamwork/)).toBeInTheDocument();
    const card = screen.getByRole('article', { name: 'Customer Order Totals' });
    expect(card).toHaveTextContent('Judge0: Wrong Answer'); // execution verdict, separate from AI quality
    expect(card).toHaveTextContent('Dialect: SQL (SQLite 3.27.2)');
    expect(card).toHaveTextContent('4/6');
    expect(card).toHaveTextContent('Combined69/100');
    expect(card).toHaveTextContent('Attempts2');
    expect(card).toHaveTextContent('Index the join column');
  });

  test('generates a pending report automatically', async () => {
    getInterview.mockResolvedValue(INTERVIEW);
    getInterviewReport.mockResolvedValue({ ...REPORT, status: 'PENDING', narrative: null, overall_score: null, aggregates: null, can_retry: true });
    generateInterviewReport.mockResolvedValue(REPORT);
    render(<InterviewResultsPage interviewId="iv-1" />);
    expect(await screen.findByText(/generating your report/i)).toBeInTheDocument();
    expect(await screen.findByText('You communicated a correct approach to query tuning.')).toBeInTheDocument();
    expect(generateInterviewReport).toHaveBeenCalledTimes(1);
  });

  test('keeps scores and offers a retry when the narrative failed', async () => {
    getInterview.mockResolvedValue(INTERVIEW);
    getInterviewReport.mockResolvedValue({ ...REPORT, status: 'FAILED', narrative: null, can_retry: true });
    generateInterviewReport.mockResolvedValue(REPORT);
    render(<InterviewResultsPage interviewId="iv-1" />);
    expect(await screen.findByText(/written summary couldn't be generated/i)).toBeInTheDocument();
    expect(screen.getByText('Good direction; quantify the impact.')).toBeInTheDocument();
    fireEvent.click(screen.getByRole('button', { name: /retry report/i }));
    expect(await screen.findByText('You communicated a correct approach to query tuning.')).toBeInTheDocument();
  });

  test('explains when there is no report', async () => {
    getInterview.mockResolvedValue({ ...INTERVIEW, status: 'ABANDONED', answered_count: 0, questions: [INTERVIEW.questions[1]] });
    getInterviewReport.mockRejectedValue({ response: { status: 404 } });
    render(<InterviewResultsPage interviewId="iv-1" />);
    expect(await screen.findByText(/no report for this interview/i)).toBeInTheDocument();
  });

  test('does not expose a report while the interview is in progress', async () => {
    getInterview.mockResolvedValue({ ...INTERVIEW, status: 'IN_PROGRESS' });
    render(<InterviewResultsPage interviewId="iv-1" />);
    expect(await screen.findByText(/still in progress/i)).toBeInTheDocument();
    expect(getInterviewReport).not.toHaveBeenCalled();
  });
});

describe('InterviewResultsPage role engine', () => {
  test('separates conceptual, practical and role competency scores', async () => {
    const reserved = {
      id: 'q3', question_order: 3, question_text: 'SQL assessment: SQL Queries', category: 'TECHNICAL', kind: 'sql',
      assessment_available: false, competency: 'SQL Queries', difficulty: 'INTERMEDIATE', created_at: '', answer: null,
    };
    getInterview.mockResolvedValue({ ...INTERVIEW, questions: [...INTERVIEW.questions, reserved] });
    getInterviewReport.mockResolvedValue({
      ...REPORT,
      aggregates: {
        ...REPORT.aggregates,
        competency_scores: [{ competency: 'SQL', category: 'TECHNICAL', score: 72, questions: 1, evaluated: 1 }],
        sections: {
          conceptual: { score: 72, evaluated: 1, questions: 1 },
          behavioral: { score: null, evaluated: 0, questions: 1 },
          communication: { score: 70 },
          problem_solving: { score: 60 },
          practical: {
            reserved: 1, reached: 1, assessed: 0, score: null, available: false, kinds: ['sql'],
            items: [{ position: 3, kind: 'sql', competency: 'SQL Queries', status: 'not_available' }],
          },
        },
      },
    });
    render(<InterviewResultsPage interviewId="iv-1" />);
    expect(await screen.findByRole('heading', { name: 'Assessment breakdown' })).toBeInTheDocument();
    expect(screen.getByText('Conceptual knowledge')).toBeInTheDocument();
    expect(screen.getByText('Problem solving')).toBeInTheDocument();
    expect(screen.queryByText('Behavioral', { selector: 'p' })).not.toBeInTheDocument(); // no behavioral score, not shown
    expect(screen.getByText(/excluded from every score above/i)).toBeInTheDocument();
    expect(screen.getByText('Q3. SQL · SQL Queries')).toBeInTheDocument();
    expect(screen.getByText('No verified assessment')).toBeInTheDocument();
    expect(screen.getByRole('heading', { name: 'Role competencies' })).toBeInTheDocument();
    expect(screen.getByText('Not assessed')).toBeInTheDocument();
    expect(screen.getByText(/was reserved for a practical assessment/i)).toBeInTheDocument();
  });
});

describe('InterviewHistoryPage', () => {
  const item = (overrides) => ({
    id: 'x',
    target_role: 'Role',
    interview_type: 'TECHNICAL',
    interaction_mode: 'TEXT',
    difficulty: 'BEGINNER',
    duration_minutes: 15,
    status: 'COMPLETED',
    started_at: '2026-10-29T10:00:00Z',
    final_score: 81,
    question_count: 3,
    answered_count: 3,
    ...overrides,
  });

  test('lists interviews with resume and report links', async () => {
    listInterviews.mockResolvedValue({
      total: 3,
      limit: HISTORY_PAGE_SIZE,
      offset: 0,
      interviews: [
        item({ id: 'a', target_role: 'Active Role', status: 'IN_PROGRESS', final_score: null }),
        item({ id: 'b', target_role: 'Done Role', interaction_mode: 'VOICE' }),
        item({ id: 'c', target_role: 'Empty Role', status: 'ABANDONED', answered_count: 0, final_score: null }),
      ],
    });
    render(<InterviewHistoryPage />);
    expect(await screen.findByText('Active Role')).toBeInTheDocument();
    expect(screen.getByRole('link', { name: /resume/i })).toHaveAttribute('href', '/dashboard/interview/a');
    expect(screen.getByRole('link', { name: /view report/i })).toHaveAttribute('href', '/dashboard/interview/b/results');
    expect(screen.getByText('No answers submitted')).toBeInTheDocument();
    expect(screen.getByText('81')).toBeInTheDocument();
    expect(screen.getByText(/Technical · Voice · Beginner · 15 min/)).toBeInTheDocument();
    expect(listInterviews).toHaveBeenCalledWith({ limit: HISTORY_PAGE_SIZE, offset: 0 });
  });

  test('paginates on the server', async () => {
    listInterviews.mockResolvedValue({ total: 12, limit: 10, offset: 0, interviews: [item({ id: 'p1' })] });
    render(<InterviewHistoryPage />);
    expect(await screen.findByText('Page 1 of 2')).toBeInTheDocument();
    fireEvent.click(screen.getByRole('button', { name: /next/i }));
    await waitFor(() => expect(listInterviews).toHaveBeenLastCalledWith({ limit: 10, offset: 10 }));
  });

  test('shows the empty state', async () => {
    listInterviews.mockResolvedValue({ total: 0, limit: 10, offset: 0, interviews: [] });
    render(<InterviewHistoryPage />);
    expect(await screen.findByText('No interviews yet')).toBeInTheDocument();
  });

  test('shows the error state with retry', async () => {
    listInterviews.mockRejectedValueOnce(new Error('Network down')).mockResolvedValue({ total: 0, interviews: [] });
    render(<InterviewHistoryPage />);
    expect(await screen.findByText('Network down')).toBeInTheDocument();
    fireEvent.click(screen.getByRole('button', { name: /try again/i }));
    expect(await screen.findByText('No interviews yet')).toBeInTheDocument();
  });
});
