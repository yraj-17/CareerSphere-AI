/**
 * Coding assessment workspace (Monaco + FastAPI coding API).
 *
 * NOTE: these are unit tests with the API mocked and Monaco replaced by a textarea
 * (jsdom cannot run Monaco). They verify the UI's integration logic only — real
 * execution on Judge0 is verified separately by the live end-to-end run.
 */
import React from 'react';
import { act, fireEvent, render, screen, waitFor, within } from '@testing-library/react';

const mockEditorCalls = [];
const mockMonaco = {
  editor: { defineTheme: jest.fn() },
  KeyMod: { CtrlCmd: 2048 },
  KeyCode: { Enter: 3 },
};

jest.mock('@monaco-editor/react', () => {
  const ReactLib = require('react');
  function MockEditor(props) {
    mockEditorCalls.push(props);
    const commands = ReactLib.useRef([]);
    ReactLib.useEffect(() => {
      props.beforeMount?.(mockMonaco);
      props.onMount?.(
        { addCommand: (key, fn) => commands.current.push(fn), getAction: () => ({ run: jest.fn() }) },
        mockMonaco
      );
    }, []);
    return (
      <textarea
        aria-label="Code editor"
        data-language={props.language}
        data-path={props.path}
        data-theme={props.theme}
        readOnly={props.options?.readOnly}
        value={props.value}
        onChange={(e) => props.onChange?.(e.target.value)}
        onKeyDown={(e) => {
          if (e.key === 'Enter' && e.ctrlKey) commands.current.forEach((fn) => fn());
        }}
      />
    );
  }
  return { __esModule: true, default: MockEditor, loader: { config: jest.fn() } };
});

// Render the Monaco wrapper directly (the real CodeEditor wraps it in next/dynamic with ssr: false).
jest.mock('@/components/interview/coding/CodeEditor', () => require('@/components/interview/coding/MonacoCodeEditor'));

jest.mock('next/link', () => {
  const Link = ({ children, href, ...props }) => (
    <a href={href} {...props}>
      {children}
    </a>
  );
  Link.displayName = 'MockLink';
  return Link;
});

jest.mock('next/navigation', () => ({ useRouter: () => ({ push: jest.fn() }) }));

jest.mock('@/services/api', () => ({
  completeInterview: jest.fn(),
  extractErrorMessage: jest.fn((err) => err?.message || 'Error'),
  getInterview: jest.fn(),
  navigateInterview: jest.fn(),
  retryInterviewEvaluation: jest.fn(),
  saveInterviewDraft: jest.fn(),
  submitInterviewAnswer: jest.fn(),
  transcribeInterviewAudio: jest.fn(),
  getCodingLanguages: jest.fn(),
  getCodingProblem: jest.fn(),
  runCode: jest.fn(),
  submitCode: jest.fn(),
  getCodingSubmission: jest.fn(),
  listCodingSubmissions: jest.fn(),
  retryCodeReview: jest.fn(),
}));

import { loader } from '@monaco-editor/react';
import {
  getCodingLanguages,
  getCodingProblem,
  getCodingSubmission,
  getInterview,
  listCodingSubmissions,
  navigateInterview,
  retryCodeReview,
  runCode,
  saveInterviewDraft,
  submitCode,
} from '@/services/api';
import InterviewRoom from '@/components/interview/InterviewRoom';
import CodingWorkspace, { POLL_INTERVAL_MS, resetLanguageCache } from '@/components/interview/coding/CodingWorkspace';
import { editorOptions, MONACO_BASE_PATH, THEME_NAME } from '@/components/interview/coding/MonacoCodeEditor';

// ---------------------------------------------------------------------------- fixtures

const LANGS = [
  { key: 'PYTHON', label: 'Python (3.8.1)', monaco_language: 'python', notes: '' },
  { key: 'JAVA', label: 'Java (OpenJDK 13.0.1)', monaco_language: 'java', notes: 'Public class must be named Main.' },
  { key: 'CPP', label: 'C++ (GCC 9.2.0)', monaco_language: 'cpp', notes: 'Compiled as C++17.' },
  { key: 'JAVASCRIPT', label: 'JavaScript (Node.js 12.14.0)', monaco_language: 'javascript', notes: '' },
];

const PROBLEM = {
  id: 'p1',
  slug: 'dsa-pair-sum-count',
  title: 'Count Pairs With Target Sum',
  difficulty: 'EASY',
  category: 'dsa',
  statement: 'Count the pairs (i, j) with i < j and a[i] + a[j] = K.',
  input_format: 'n and K, then n integers.',
  output_format: 'A single integer.',
  constraints: '1 ≤ n ≤ 200 000',
  examples: [{ input: '5 6\n1 5 3 3 7\n', output: '2\n', explanation: '(1,5) and (3,3).' }],
  instructions: null,
  languages: LANGS,
  starter_code: {
    PYTHON: 'def solve():\n    pass\n',
    JAVA: 'public class Main {}\n',
    CPP: 'int main() {}\n',
    JAVASCRIPT: 'function solve() {}\n',
  },
  time_limit_seconds: 2,
  memory_limit_kb: 262144,
  estimated_minutes: 15,
  sample_test_count: 2,
  hidden_test_count: 5,
};

const SQL_PROBLEM = {
  ...PROBLEM,
  id: 'p2',
  slug: 'sql-customer-order-totals',
  title: 'Customer Order Totals',
  category: 'sql',
  input_format: 'CREATE TABLE customers (id INTEGER PRIMARY KEY, name TEXT NOT NULL);',
  output_format: 'name|completed_orders|total_amount per customer.',
  instructions: 'Dialect: SQLite 3.27.2. Write a single query.',
  examples: [{ input: "INSERT INTO customers VALUES (1, 'Asha');", output: 'Asha|2|800\n', explanation: null }],
  languages: [{ key: 'SQLITE', label: 'SQL (SQLite 3.27.2)', monaco_language: 'sql', notes: '' }],
  starter_code: { SQLITE: '-- Write one SELECT statement.\n' },
};

function submission(overrides = {}) {
  return {
    id: 's1',
    question_id: 'q1',
    submission_type: 'RUN',
    language: 'PYTHON',
    language_label: 'Python (3.8.1)',
    status: 'COMPLETED',
    verdict: 'ACCEPTED',
    verdict_label: 'Accepted',
    tests_passed: 2,
    tests_total: 2,
    correctness_score: 100,
    max_time_seconds: 0.021,
    max_memory_kb: 3400,
    compile_output: null,
    error: null,
    created_at: '2026-11-04T10:00:00Z',
    completed_at: '2026-11-04T10:00:01Z',
    results: [
      {
        ordinal: 1, kind: 'sample', verdict: 'ACCEPTED', verdict_label: 'Accepted', passed: true, time: 0.02, memory: 3400,
        judge0_status: 'Accepted', input: '5 6\n1 5 3 3 7\n', expected_output: '2\n', stdout: '2\n', stderr: '', reason: '',
      },
    ],
    ...overrides,
  };
}

const HIDDEN = { ordinal: 3, kind: 'hidden', verdict: 'WRONG_ANSWER', verdict_label: 'Wrong Answer', passed: false, time: 0.03, memory: 3500, judge0_status: 'Accepted' };

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

const codingQ = (order, overrides = {}) =>
  q(order, {
    kind: 'coding',
    question_text: 'Coding assessment: Data Structures',
    competency: 'Data Structures',
    practical: { type: 'coding', available: true, title: 'Count Pairs', difficulty: 'EASY', planned_difficulty: 'EASY', difficulty_fallback: false, languages: ['PYTHON', 'JAVA', 'CPP', 'JAVASCRIPT'] },
    ...overrides,
  });

function interview(questions) {
  const now = new Date();
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

function renderWorkspace(props = {}) {
  const onDraftChange = jest.fn();
  let meta = props.draftMeta || null;
  const question = props.question || codingQ(1);
  const utils = render(
    <CodingWorkspace
      interviewId="iv-1"
      question={question}
      targetRole="Software Development Engineer"
      draftMeta={meta}
      onDraftChange={onDraftChange}
      saveState=""
      cache={props.cache || {}}
      onSubmissionComplete={props.onSubmissionComplete}
      readOnly={props.readOnly}
    />
  );
  // Feed draft changes back in, as InterviewRoom does.
  onDraftChange.mockImplementation((next) => {
    meta = next;
    utils.rerender(
      <CodingWorkspace
        interviewId="iv-1"
        question={question}
        targetRole="Software Development Engineer"
        draftMeta={meta}
        onDraftChange={onDraftChange}
        saveState=""
        cache={props.cache || {}}
        onSubmissionComplete={props.onSubmissionComplete}
        readOnly={props.readOnly}
      />
    );
  });
  return { ...utils, onDraftChange, getMeta: () => meta };
}

const editor = () => screen.getByLabelText('Code editor');
const typeCode = (text) => fireEvent.change(editor(), { target: { value: text } });

beforeEach(() => {
  jest.clearAllMocks();
  mockEditorCalls.length = 0;
  resetLanguageCache();
  getCodingLanguages.mockResolvedValue({ execution_available: true, languages: LANGS });
  getCodingProblem.mockResolvedValue(PROBLEM);
  listCodingSubmissions.mockResolvedValue([]);
  saveInterviewDraft.mockImplementation((id, qid, { revision }) => Promise.resolve({ question_id: qid, saved: true, revision }));
});

afterEach(() => {
  jest.useRealTimers();
});

// ---------------------------------------------------------------------------- 1. Monaco

test('Monaco is self-hosted and configured for code editing', async () => {
  renderWorkspace();
  await screen.findByLabelText('Code editor');
  expect(MONACO_BASE_PATH).toBe('/monaco/vs');
  expect(loader.config).toBeDefined();
  expect(mockMonaco.editor.defineTheme).toHaveBeenCalledWith(THEME_NAME, expect.objectContaining({ base: 'vs-dark' }));
  const props = mockEditorCalls[mockEditorCalls.length - 1];
  expect(props.theme).toBe(THEME_NAME);
  expect(props.language).toBe('python');
  expect(props.path).toBe('q1/PYTHON'); // one model per question + language
  expect(props.options).toEqual(
    expect.objectContaining({ lineNumbers: 'on', matchBrackets: 'always', folding: true, autoIndent: 'full', automaticLayout: true })
  );
  expect(editorOptions({ readOnly: true }).readOnly).toBe(true);
});

test('the Monaco loader points at the self-hosted bundle, not a CDN', () => {
  jest.isolateModules(() => {
    const { loader: isolatedLoader } = require('@monaco-editor/react');
    require('@/components/interview/coding/MonacoCodeEditor');
    expect(isolatedLoader.config).toHaveBeenCalledWith({ paths: { vs: '/monaco/vs' } });
  });
});

// ---------------------------------------------------------------------------- 2-4. starter code, languages, drafts

test('loads the problem and its starter code from the backend', async () => {
  renderWorkspace();
  expect(await screen.findByRole('heading', { name: PROBLEM.title })).toBeInTheDocument();
  expect(getCodingProblem).toHaveBeenCalledWith('iv-1', 'q1');
  expect(editor()).toHaveValue(PROBLEM.starter_code.PYTHON);
  expect(screen.getByText('Easy')).toBeInTheDocument();
  expect(screen.getByText('Software Development Engineer')).toBeInTheDocument();
  expect(screen.getByText(/5 hidden/)).toBeInTheDocument();
});

test('offers only the problem languages with their real runtime labels', async () => {
  renderWorkspace();
  const select = await screen.findByLabelText('Programming language');
  const labels = within(select).getAllByRole('option').map((o) => o.textContent);
  expect(labels).toEqual(['Python (3.8.1)', 'Java (OpenJDK 13.0.1)', 'C++ (GCC 9.2.0)', 'JavaScript (Node.js 12.14.0)']);
  expect(labels.join(' ')).not.toMatch(/Java 17/);
  fireEvent.change(select, { target: { value: 'JAVA' } });
  expect(editor()).toHaveValue(PROBLEM.starter_code.JAVA);
  expect(editor()).toHaveAttribute('data-language', 'java');
});

test('code written for one language is kept when switching languages', async () => {
  const { getMeta } = renderWorkspace();
  await screen.findByLabelText('Code editor');
  typeCode('print("python solution")');
  fireEvent.change(screen.getByLabelText('Programming language'), { target: { value: 'JAVA' } });
  expect(editor()).toHaveValue(PROBLEM.starter_code.JAVA);
  typeCode('class Main { /* java */ }');
  fireEvent.change(screen.getByLabelText('Programming language'), { target: { value: 'PYTHON' } });
  expect(editor()).toHaveValue('print("python solution")');
  expect(getMeta()).toEqual(
    expect.objectContaining({
      language: 'PYTHON',
      edited: true,
      code: { PYTHON: 'print("python solution")', JAVA: 'class Main { /* java */ }' },
    })
  );
});

test('reset restores the starter code for the current language only, after confirmation', async () => {
  renderWorkspace({ draftMeta: { language: 'PYTHON', code: { PYTHON: 'x = 1', JAVA: 'class Main {}' }, edited: true } });
  await screen.findByLabelText('Code editor');
  fireEvent.click(screen.getByRole('button', { name: /reset code/i }));
  fireEvent.click(screen.getByRole('button', { name: /^reset$/i }));
  expect(editor()).toHaveValue(PROBLEM.starter_code.PYTHON);
  fireEvent.change(screen.getByLabelText('Programming language'), { target: { value: 'JAVA' } });
  expect(editor()).toHaveValue('class Main {}');
});

test('a problem with no compatible language shows an error instead of an editor', async () => {
  getCodingProblem.mockResolvedValue({ ...PROBLEM, languages: [] });
  renderWorkspace();
  expect(await screen.findByText(/no compatible programming language/i)).toBeInTheDocument();
  expect(screen.queryByLabelText('Code editor')).not.toBeInTheDocument();
});

// ---------------------------------------------------------------------------- 5-10. run / submit / polling / results

test('Run Code sends the sample run request and shows the real per-test results', async () => {
  runCode.mockResolvedValue(submission());
  renderWorkspace();
  await screen.findByLabelText('Code editor');
  typeCode('print(2)');
  fireEvent.click(screen.getByRole('button', { name: /run code/i }));
  await screen.findByText('Sample test 1');
  expect(runCode).toHaveBeenCalledWith('iv-1', 'q1', {
    language: 'PYTHON',
    sourceCode: 'print(2)',
    customInput: null,
    idempotencyKey: expect.stringMatching(/^[A-Za-z0-9_-]{8,64}$/),
  });
  expect(submitCode).not.toHaveBeenCalled();
  expect(screen.getByText(/Run \(sample tests only\)/)).toBeInTheDocument();
  expect(screen.getByText('2/2 tests passed ·', { exact: false })).toBeInTheDocument();
  expect(screen.getByText('Passed')).toBeInTheDocument();
});

test('Run Code with custom input sends it and shows the program output', async () => {
  runCode.mockResolvedValue(
    submission({
      tests_passed: null, tests_total: null, verdict: 'EXECUTED', verdict_label: 'Executed',
      results: [{ ordinal: 1, kind: 'custom', verdict: 'EXECUTED', verdict_label: 'Executed', passed: null, time: 0.01, memory: 3000, judge0_status: 'Accepted', input: '3 3\n1 2 3\n', expected_output: null, stdout: '1\n', stderr: 'debug' , reason: '' }],
    })
  );
  renderWorkspace();
  await screen.findByLabelText('Code editor');
  typeCode('print(1)');
  fireEvent.click(screen.getByRole('tab', { name: 'Custom input' }));
  fireEvent.change(screen.getByLabelText('Custom input', { selector: 'textarea' }), { target: { value: '3 3\n1 2 3\n' } });
  fireEvent.click(screen.getByRole('checkbox'));
  fireEvent.click(screen.getByRole('button', { name: /run code/i }));
  await waitFor(() => expect(runCode).toHaveBeenCalled());
  expect(runCode.mock.calls[0][2].customInput).toBe('3 3\n1 2 3\n');
  fireEvent.click(await screen.findByRole('tab', { name: 'Output' }));
  expect(screen.getByText('Output for your custom input.')).toBeInTheDocument();
  expect(screen.getByText('debug')).toBeInTheDocument();
});

test('Submit Solution shows the real verdict; hidden tests show outcome only', async () => {
  const onSubmissionComplete = jest.fn();
  submitCode.mockResolvedValue(
    submission({
      submission_type: 'SUBMIT', verdict: 'WRONG_ANSWER', verdict_label: 'Wrong Answer', tests_passed: 1, tests_total: 2, correctness_score: 43,
      results: [submission().results[0], HIDDEN],
    })
  );
  renderWorkspace({ onSubmissionComplete });
  await screen.findByLabelText('Code editor');
  typeCode('print(0)');
  fireEvent.click(screen.getByRole('button', { name: /submit solution/i }));
  await screen.findByText('Hidden test 3');
  expect(submitCode).toHaveBeenCalledWith('iv-1', 'q1', { language: 'PYTHON', sourceCode: 'print(0)', idempotencyKey: expect.any(String) });
  expect(runCode).not.toHaveBeenCalled();
  expect(screen.getByRole('status', { name: '' }).textContent).toMatch(/Wrong Answer/);
  expect(screen.getByText(/score 43\/100/)).toBeInTheDocument();
  expect(screen.getByText('Input and expected output are hidden.')).toBeInTheDocument();
  expect(onSubmissionComplete).toHaveBeenCalled();
});

test('polls a running submission until it reaches a terminal status, then stops', async () => {
  jest.useFakeTimers();
  submitCode.mockResolvedValue(submission({ submission_type: 'SUBMIT', status: 'RUNNING', verdict: null, verdict_label: null, results: [] }));
  getCodingSubmission
    .mockResolvedValueOnce(submission({ submission_type: 'SUBMIT', status: 'RUNNING', verdict: null, results: [] }))
    .mockResolvedValueOnce(submission({ submission_type: 'SUBMIT' }));
  renderWorkspace();
  await screen.findByLabelText('Code editor');
  typeCode('print(2)');
  fireEvent.click(screen.getByRole('button', { name: /submit solution/i }));
  expect(await screen.findByText(/compiling and running on judge0/i)).toBeInTheDocument();
  expect(screen.getByRole('button', { name: /run code/i })).toBeDisabled(); // no overlapping actions
  await act(async () => {
    jest.advanceTimersByTime(POLL_INTERVAL_MS);
  });
  await act(async () => {
    jest.advanceTimersByTime(POLL_INTERVAL_MS);
  });
  await screen.findByText('Sample test 1');
  expect(getCodingSubmission).toHaveBeenCalledTimes(2);
  await act(async () => {
    jest.advanceTimersByTime(POLL_INTERVAL_MS * 5);
  });
  expect(getCodingSubmission).toHaveBeenCalledTimes(2); // stopped at the terminal status
});

test('polling stops when the workspace unmounts (navigating away)', async () => {
  jest.useFakeTimers();
  runCode.mockResolvedValue(submission({ status: 'QUEUED', verdict: null, results: [] }));
  getCodingSubmission.mockResolvedValue(submission({ status: 'RUNNING', verdict: null, results: [] }));
  const { unmount } = renderWorkspace();
  await screen.findByLabelText('Code editor');
  typeCode('print(2)');
  fireEvent.click(screen.getByRole('button', { name: /run code/i }));
  await screen.findByText(/queued on the execution service/i);
  unmount();
  await act(async () => {
    jest.advanceTimersByTime(POLL_INTERVAL_MS * 10);
  });
  expect(getCodingSubmission).not.toHaveBeenCalled();
});

test('a compilation error is shown in the Compilation tab', async () => {
  runCode.mockResolvedValue(
    submission({
      verdict: 'COMPILATION_ERROR', verdict_label: 'Compilation Error', tests_passed: 0,
      compile_output: "main.cpp:3:5: error: 'x' was not declared in this scope",
      results: [{ ...submission().results[0], verdict: 'COMPILATION_ERROR', verdict_label: 'Compilation Error', passed: false, stdout: '' }],
    })
  );
  renderWorkspace();
  await screen.findByLabelText('Code editor');
  typeCode('int main() { x; }');
  fireEvent.click(screen.getByRole('button', { name: /run code/i }));
  await screen.findByText('Sample test 1');
  fireEvent.click(screen.getByRole('tab', { name: 'Compilation' }));
  expect(screen.getByText('Compilation failed')).toBeInTheDocument();
  expect(screen.getByText(/'x' was not declared/)).toBeInTheDocument();
});

test('a runtime error shows its verdict and standard error', async () => {
  runCode.mockResolvedValue(
    submission({
      verdict: 'RUNTIME_ERROR', verdict_label: 'Runtime Error', tests_passed: 0,
      results: [{ ...submission().results[0], verdict: 'RUNTIME_ERROR', verdict_label: 'Runtime Error', passed: false, stdout: '', stderr: 'IndexError: list index out of range', reason: 'The program exited with an error.' }],
    })
  );
  renderWorkspace();
  await screen.findByLabelText('Code editor');
  typeCode('a = []\nprint(a[1])');
  fireEvent.click(screen.getByRole('button', { name: /run code/i }));
  expect(await screen.findByText('IndexError: list index out of range')).toBeInTheDocument();
  expect(screen.getAllByText('Runtime Error').length).toBeGreaterThan(0);
});

// ---------------------------------------------------------------------------- 14. history

test('submission history lists earlier results and viewing one never re-runs code', async () => {
  const older = submission({ id: 's0', submission_type: 'SUBMIT', verdict: 'ACCEPTED', verdict_label: 'Accepted', tests_passed: 7, tests_total: 7 });
  listCodingSubmissions.mockResolvedValue([older]);
  getCodingSubmission.mockResolvedValue({ ...older, results: [submission().results[0], { ...HIDDEN, passed: true, verdict: 'ACCEPTED', verdict_label: 'Accepted' }] });
  renderWorkspace();
  await screen.findByLabelText('Code editor');
  fireEvent.click(await screen.findByRole('tab', { name: /submission history \(1\)/i }));
  const list = screen.getByRole('list', { name: 'Submission history' });
  expect(within(list).getByText('Submit')).toBeInTheDocument();
  expect(within(list).getByText('7/7')).toBeInTheDocument();
  fireEvent.click(within(list).getByRole('button'));
  expect(await screen.findByText(/Viewing an earlier submission/)).toBeInTheDocument();
  expect(getCodingSubmission).toHaveBeenCalledWith('iv-1', 's0');
  expect(runCode).not.toHaveBeenCalled();
  expect(submitCode).not.toHaveBeenCalled();
});

// ---------------------------------------------------------------------------- 19-20. states and errors

test('empty code is rejected without a request', async () => {
  renderWorkspace();
  await screen.findByLabelText('Code editor');
  typeCode('   ');
  fireEvent.click(screen.getByRole('button', { name: /run code/i }));
  expect(await screen.findByText('Write some code before running it.')).toBeInTheDocument();
  expect(runCode).not.toHaveBeenCalled();
});

test('rapid double clicks send a single request', async () => {
  let resolve;
  runCode.mockReturnValue(new Promise((r) => { resolve = r; }));
  renderWorkspace();
  await screen.findByLabelText('Code editor');
  typeCode('print(2)');
  const run = screen.getByRole('button', { name: /run code/i });
  fireEvent.click(run);
  fireEvent.click(run);
  fireEvent.click(screen.getByRole('button', { name: /submit solution/i }));
  expect(runCode).toHaveBeenCalledTimes(1);
  expect(submitCode).not.toHaveBeenCalled();
  await act(async () => resolve(submission()));
});

test('a lost response is retried with the same idempotency key (no duplicate submission)', async () => {
  submitCode.mockRejectedValueOnce({ code: 'ECONNABORTED' }).mockResolvedValueOnce(submission({ submission_type: 'SUBMIT' }));
  renderWorkspace();
  await screen.findByLabelText('Code editor');
  typeCode('print(2)');
  fireEvent.click(screen.getByRole('button', { name: /submit solution/i }));
  expect(await screen.findByText(/may still be running/i)).toBeInTheDocument();
  fireEvent.click(screen.getByRole('button', { name: /submit solution/i }));
  await screen.findByText('Sample test 1');
  expect(submitCode.mock.calls[1][2].idempotencyKey).toBe(submitCode.mock.calls[0][2].idempotencyKey);
});

test.each([
  [{ response: { status: 503, data: { detail: { message: 'internal', stage: 'judge0_unavailable' } } } }, /temporarily unavailable/i],
  [{ response: { status: 401, data: { detail: 'Not authenticated' } } }, /session has expired/i],
  [{ response: { status: 429, data: { detail: { message: 'Too many runs. Please wait a minute.', status: 'RATE_LIMITED' } } } }, /too many runs/i],
  [{ response: { status: 409, data: { detail: { message: 'ended', status: 'ENDED' } } } }, /interview has ended/i],
  [{ response: { status: 422, data: { detail: [{ msg: 'Value error, Source code is larger than 64 KB.' }] } } }, /larger than 64 KB/i],
  [{ message: 'Network Error' }, /unable to reach the server/i],
])('execution errors are explained without internals (%#)', async (error, message) => {
  runCode.mockRejectedValue(error);
  renderWorkspace();
  await screen.findByLabelText('Code editor');
  typeCode('print(2)');
  fireEvent.click(screen.getByRole('button', { name: /run code/i }));
  const alert = await screen.findByRole('alert');
  expect(alert).toHaveTextContent(message);
  expect(alert.textContent).not.toMatch(/judge0_unavailable|token|2358/i);
});

test('a problem that fails to load shows an error state', async () => {
  getCodingProblem.mockRejectedValue({ response: { status: 409, data: { detail: { message: 'No coding problem is assigned to this question yet.', status: 'NO_PROBLEM' } } } });
  renderWorkspace();
  expect(await screen.findByRole('alert')).toHaveTextContent('No coding problem is assigned to this question yet.');
});

test('execution unavailable on the server disables Run and Submit', async () => {
  getCodingLanguages.mockResolvedValue({ execution_available: false, languages: [] });
  renderWorkspace();
  expect(await screen.findByText(/code execution is unavailable/i)).toBeInTheDocument();
  expect(screen.getByRole('button', { name: /run code/i })).toBeDisabled();
  expect(screen.getByRole('button', { name: /submit solution/i })).toBeDisabled();
});

test('read-only after the interview ends', async () => {
  renderWorkspace({ readOnly: true });
  await screen.findByLabelText('Code editor');
  expect(editor()).toHaveAttribute('readonly');
  expect(screen.getByRole('button', { name: /run code/i })).toBeDisabled();
});

// ---------------------------------------------------------------------------- 16. SQL

test('SQL problems show the schema, SQLite label, query actions and a result table', async () => {
  getCodingProblem.mockResolvedValue(SQL_PROBLEM);
  runCode.mockResolvedValue(
    submission({
      language: 'SQLITE', language_label: 'SQL (SQLite 3.27.2)',
      results: [{ ...submission().results[0], input: SQL_PROBLEM.examples[0].input, expected_output: 'Asha|2|800\n', stdout: 'Asha|2|800\nBilal|NULL|0\n', passed: false, verdict: 'WRONG_ANSWER', verdict_label: 'Wrong Answer' }],
    })
  );
  renderWorkspace({ question: codingQ(1, { kind: 'sql', practical: { type: 'sql', available: true, languages: ['SQLITE'] } }) });
  await screen.findByLabelText('Code editor');
  expect(screen.getByLabelText('SQL assessment workspace')).toBeInTheDocument();
  expect(editor()).toHaveAttribute('data-language', 'sql');
  expect(within(screen.getByLabelText('Programming language')).getAllByRole('option').map((o) => o.textContent)).toEqual(['SQL (SQLite 3.27.2)']);
  expect(screen.getByLabelText('Database schema')).toHaveTextContent('CREATE TABLE customers');
  expect(screen.getByText(/Sample dataset/)).toBeInTheDocument();
  typeCode('SELECT name FROM customers;');
  fireEvent.click(screen.getByRole('button', { name: /run query/i }));
  expect(await screen.findByText(/Your output · 2 rows/)).toBeInTheDocument();
  const table = screen.getAllByRole('table')[1];
  expect(within(table).getByText('Bilal')).toBeInTheDocument();
  expect(screen.getByRole('button', { name: /submit query/i })).toBeInTheDocument();
});

// ---------------------------------------------------------------------------- 11-13, 15, 17-18: inside the interview room

function setupRoom(data) {
  getInterview.mockResolvedValue(data);
  navigateInterview.mockImplementation((id, position) => Promise.resolve({ ...data, current_position: position }));
  return render(<InterviewRoom interviewId="iv-1" />);
}

test('code drafts are kept per question across Previous/Next, without running or submitting', async () => {
  setupRoom(interview([codingQ(1), q(2), codingQ(3, { id: 'q3' })]));
  await screen.findByLabelText('Code editor');
  typeCode('print("q1 answer")');
  fireEvent.click(screen.getByRole('button', { name: /next question/i }));
  expect(await screen.findByLabelText('Your answer')).toBeInTheDocument(); // theory question: no editor
  expect(screen.queryByLabelText('Code editor')).not.toBeInTheDocument();
  fireEvent.click(screen.getByRole('button', { name: /next question/i }));
  await waitFor(() => expect(editor()).toHaveValue(PROBLEM.starter_code.PYTHON)); // q3 has its own code
  typeCode('print("q3 answer")');
  fireEvent.click(screen.getByRole('button', { name: 'Question 1, In progress' }));
  await waitFor(() => expect(editor()).toHaveValue('print("q1 answer")'));
  fireEvent.click(screen.getByRole('button', { name: /question 3,/i }));
  await waitFor(() => expect(editor()).toHaveValue('print("q3 answer")'));
  expect(runCode).not.toHaveBeenCalled();
  expect(submitCode).not.toHaveBeenCalled();
  await waitFor(() => expect(saveInterviewDraft).toHaveBeenCalled()); // persisted through the existing draft API
  const saved = saveInterviewDraft.mock.calls.find((call) => call[1] === 'q1');
  expect(saved[2].meta).toEqual(expect.objectContaining({ language: 'PYTHON', code: { PYTHON: 'print("q1 answer")' }, edited: true }));
});

test('a refreshed page restores the saved code draft and language from the server', async () => {
  setupRoom(interview([codingQ(1, { status: 'IN_PROGRESS', draft_revision: 7, draft_meta: { language: 'JAVA', code: { JAVA: 'class Main { int saved; }' }, edited: true } })]));
  await screen.findByLabelText('Code editor');
  expect(editor()).toHaveValue('class Main { int saved; }');
  expect(screen.getByLabelText('Programming language')).toHaveValue('JAVA');
  expect(screen.getByRole('button', { name: 'Question 1, In progress' })).toBeInTheDocument();
});

test('the interview timer keeps running while moving between coding and other questions', async () => {
  jest.useFakeTimers();
  setupRoom(interview([codingQ(1), q(2)]));
  await screen.findByLabelText('Code editor');
  const before = screen.getByRole('timer').textContent;
  await act(async () => {
    jest.advanceTimersByTime(5000);
  });
  fireEvent.click(screen.getByRole('button', { name: /next question/i }));
  await screen.findByLabelText('Your answer');
  const after = screen.getByRole('timer').textContent;
  expect(after).not.toBe(before);
  expect(after < before).toBe(true); // counted down, never reset
});

test('an answered coding question shows its recorded Judge0 result and stays editable for resubmission', async () => {
  const answer = {
    id: 'a1', question_id: 'q1', answer_text: 'print(2)', answer_source: 'TEXT', submitted_at: '2026-11-04T10:00:00Z',
    evaluation_status: 'COMPLETED', score: 92, can_retry_evaluation: false,
    evaluation: {
      score: 92, method: 'judge0', verdict: 'ACCEPTED', verdict_label: 'Accepted', correct: 7, total: 7, language_label: 'Python (3.8.1)',
      correctness_score: 100, review_status: 'COMPLETED', quality_score: 75, coding_score: 92.5,
      strengths: [], improvements: [], feedback: '', key_points: [],
    },
  };
  setupRoom(interview([codingQ(1, { status: 'ANSWERED', answer, draft_meta: { language: 'PYTHON', code: { PYTHON: 'print(2)' }, edited: true } })]));
  await screen.findByLabelText('Code editor');
  // Judge0 correctness, AI quality and the combined score are shown separately.
  expect(screen.getByText(/Recorded answer:/)).toHaveTextContent('Accepted · 7/7 tests · correctness 100/100 · AI code quality 75/100 · combined 93/100');
  expect(editor()).toHaveValue('print(2)');
  expect(screen.getByRole('button', { name: /submit solution/i })).toBeEnabled();
});

test('calculation and scenario questions never show the code editor', async () => {
  setupRoom(
    interview([
      q(1, { kind: 'calculation', practical: { type: 'calculation', available: true, label: 'Auto-graded — calculated deterministically with Python ipaddress', conventions: 'c', fields: [{ key: 'network', label: 'Network address', hint: 'dotted decimal' }] } }),
      q(2, { kind: 'scenario', practical: { type: 'scenario', available: true, label: 'AI-reviewed — not executed', title: 'Restart loop', context: 'ctx', tasks: ['t1'], criteria: ['Diagnosis'] } }),
    ])
  );
  expect(await screen.findByLabelText('Network address')).toBeInTheDocument();
  expect(screen.queryByLabelText('Code editor')).not.toBeInTheDocument();
  fireEvent.click(screen.getByRole('button', { name: /next question/i }));
  expect(await screen.findByText('AI-reviewed — not executed')).toBeInTheDocument();
  expect(screen.getByLabelText('Your answer')).toBeInTheDocument();
  expect(screen.queryByLabelText('Code editor')).not.toBeInTheDocument();
  expect(getCodingProblem).not.toHaveBeenCalled();
});

// ---------------------------------------------------------------------------- Phase 5: AI Code Review + follow-ups

const REVIEW_DONE = {
  label: 'AI Code Review', status: 'COMPLETED', note: 'Correctness comes only from Judge0 execution; this review rates code quality and is not an execution result.',
  quality_score: 75, compiled: true, can_retry: false, summary: 'A clear single-pass approach.',
  criteria: [
    { id: 'problem_solving', title: 'Problem-solving approach', weight: 25, score: 80 },
    { id: 'code_quality', title: 'Code quality and readability', weight: 20, score: 70 },
  ],
  strengths: ['Single pass'], weaknesses: ['No empty-input guard'], improvements: ['Validate input'], alternative_approaches: ['Two pointers'],
  time_complexity: 'O(n)', space_complexity: 'O(n)', missing_edge_cases: ['Empty input'], recommendations: ['Add boundary tests'],
};

test('the Judge0 verdict shows immediately and the AI review loads independently', async () => {
  jest.useFakeTimers();
  const pending = submission({ submission_type: 'SUBMIT', verdict: 'WRONG_ANSWER', verdict_label: 'Wrong Answer', tests_passed: 1, tests_total: 2,
    correctness_score: 40, ai_review: { label: 'AI Code Review', status: 'PENDING', note: 'n', criteria: [], compiled: true } , coding_score: null });
  submitCode.mockResolvedValue(pending);
  getCodingSubmission.mockResolvedValue({ ...pending, ai_review: REVIEW_DONE, coding_score: 50.5 });
  const onSubmissionComplete = jest.fn();
  renderWorkspace({ onSubmissionComplete });
  await screen.findByLabelText('Code editor');
  typeCode('print(0)');
  fireEvent.click(screen.getByRole('button', { name: /submit solution/i }));
  expect(await screen.findByText(/reviewing your code/i)).toBeInTheDocument();
  expect(screen.getAllByText('Wrong Answer').length).toBeGreaterThan(0); // execution result is already final
  await act(async () => {
    jest.advanceTimersByTime(4000);
  });
  expect(await screen.findByText(/Code quality 75\/100/)).toBeInTheDocument();
  expect(screen.getByText(/combined coding score 51\/100/)).toBeInTheDocument();
  expect(screen.getAllByText('Wrong Answer').length).toBeGreaterThan(0); // the review never changes the verdict
  fireEvent.click(screen.getByRole('button', { name: 'View review' }));
  const panel = screen.getByRole('region', { name: 'AI Code Review' });
  expect(within(panel).getByText('Problem-solving approach')).toBeInTheDocument();
  expect(within(panel).getAllByText('O(n)', { selector: 'dd' })).toHaveLength(2); // time and space (AI estimates)
  expect(within(panel).getByText(/not an execution result/)).toBeInTheDocument();
  expect(onSubmissionComplete).toHaveBeenCalledTimes(2); // verdict, then review (refreshes the recorded answer)
});

test('a failed review is labelled unavailable and can be retried', async () => {
  const failed = submission({ submission_type: 'SUBMIT', ai_review: { label: 'AI Code Review', status: 'FAILED', note: 'n', criteria: [], compiled: true, can_retry: true }, coding_score: null });
  submitCode.mockResolvedValue(failed);
  retryCodeReview.mockResolvedValue({ ...failed, ai_review: REVIEW_DONE, coding_score: 92.5 });
  renderWorkspace();
  await screen.findByLabelText('Code editor');
  typeCode('print(2)');
  fireEvent.click(screen.getByRole('button', { name: /submit solution/i }));
  expect(await screen.findByText(/unavailable — correctness from Judge0/)).toBeInTheDocument();
  fireEvent.click(screen.getByRole('tab', { name: 'AI Code Review' }));
  expect(screen.getByText(/uses Judge0 correctness only/)).toBeInTheDocument();
  fireEvent.click(screen.getByRole('button', { name: /retry review/i }));
  await waitFor(() => expect(retryCodeReview).toHaveBeenCalledWith('iv-1', 's1'));
  expect(await screen.findByText('A clear single-pass approach.')).toBeInTheDocument();
});

test('a follow-up appears right after its parent in the navigator and in Previous/Next order', async () => {
  const follow = q(102, {
    id: 'f2', parent_question_id: 'q2', question_text: 'How would your solution behave with a hundredfold larger input?',
    competency: 'Data Structures', interviewer_context: 'Probing scalability.',
  });
  const data = interview([q(1), codingQ(2, { follow_up_state: 'CREATED' }), q(3), follow]);
  data.max_questions = 3; // the follow-up is extra to the planned questions
  data.blueprint.question_slots = data.blueprint.question_slots.filter((slot) => slot.position <= 3);
  data.follow_up_count = 1;
  setupRoom(data);
  await screen.findByText('Question 1?');
  const chips = within(screen.getByRole('list', { name: 'Questions' })).getAllByRole('button').map((b) => b.textContent);
  expect(chips).toEqual(['1', '2', '2a', '3']);
  fireEvent.click(screen.getByRole('button', { name: /next question/i }));
  await screen.findByLabelText('Code editor');
  fireEvent.click(screen.getByRole('button', { name: /next question/i }));
  expect(await screen.findByText('How would your solution behave with a hundredfold larger input?')).toBeInTheDocument();
  expect(screen.getAllByText(/Follow-up to question 2/).length).toBeGreaterThan(0);
  expect(screen.getByLabelText('Your answer')).toBeInTheDocument(); // answered in writing
  expect(navigateInterview).toHaveBeenLastCalledWith('iv-1', 102, expect.any(Number));
  fireEvent.click(screen.getByRole('button', { name: /next question/i }));
  expect(await screen.findByText('Question 3?')).toBeInTheDocument();
});
