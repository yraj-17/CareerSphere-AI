import React from 'react';
import { fireEvent, render, screen, waitFor, within } from '@testing-library/react';

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
  analyzeInterviewRole: jest.fn(),
  createInterview: jest.fn(),
  extractErrorMessage: jest.fn((err) => err?.response?.data?.detail?.message || err?.response?.data?.detail || err?.message || 'Error'),
  getInterviewOptions: jest.fn(),
  getInterviewRoles: jest.fn(),
  getInterviewSuggestions: jest.fn(),
  listInterviews: jest.fn(),
  previewInterviewBlueprint: jest.fn(),
}));

import {
  analyzeInterviewRole,
  createInterview,
  getInterviewOptions,
  getInterviewRoles,
  getInterviewSuggestions,
  listInterviews,
  previewInterviewBlueprint,
} from '@/services/api';
import InterviewSetupPage, { validateSetup } from '@/components/interview/InterviewSetupPage';
import { matchCatalogRole, practicalCount } from '@/components/interview/interviewConstants';

const OPTIONS = {
  interview_types: ['TECHNICAL', 'BEHAVIORAL', 'MIXED'],
  interaction_modes: ['TEXT', 'VOICE'],
  difficulties: ['BEGINNER', 'INTERMEDIATE', 'ADVANCED'],
  durations: [10, 15, 20, 30],
  default_duration_minutes: 15,
  max_answer_length: 5000,
  max_focus_areas: 8,
  min_questions: 3,
  question_limits: { 10: 4, 15: 6, 20: 8, 30: 12 },
  max_job_description_length: 4000,
  transcription_available: false,
  max_audio_seconds: 180,
  max_audio_bytes: 8388608,
};

const ROLES = [
  {
    slug: 'frontend-developer', title: 'Frontend Developer', family: 'Frontend', source: 'catalog',
    aliases: ['front end developer', 'frontend engineer'],
    focus_areas: ['JavaScript & TypeScript', 'React & State Management', 'HTML, CSS & Responsive Design'],
    practical_kinds: ['coding', 'scenario'], languages: ['JAVASCRIPT'], competencies: [],
  },
  {
    slug: 'database-developer', title: 'Database Developer', family: 'Database', source: 'catalog',
    aliases: ['db developer'], focus_areas: ['SQL', 'Database Design', 'Performance & Optimization'],
    practical_kinds: ['sql'], languages: [], competencies: [],
  },
  {
    slug: 'network-engineer', title: 'Network Engineer', family: 'Networking', source: 'catalog',
    aliases: ['networking engineer'], focus_areas: ['IP Addressing & Subnetting', 'Routing & Switching', 'Troubleshooting'],
    practical_kinds: ['calculation', 'scenario'], languages: [], competencies: [],
  },
];

const DB_PLAN = {
  role: ROLES[1],
  assessment_kinds_available: [],
  blueprint: {
    question_slots: [
      { position: 1, kind: 'question', category: 'TECHNICAL', competency: 'Database Design & Normalization' },
      { position: 2, kind: 'sql', category: 'TECHNICAL', competency: 'SQL Queries' },
      { position: 3, kind: 'question', category: 'TECHNICAL', competency: 'Indexing' },
      { position: 4, kind: 'question', category: 'TECHNICAL', competency: 'Transactions & ACID' },
      { position: 5, kind: 'sql', category: 'TECHNICAL', competency: 'Joins & Subqueries' },
      { position: 6, kind: 'question', category: 'TECHNICAL', competency: 'Query Optimization' },
    ],
  },
};

function setup({ options = OPTIONS, suggestions = { target_role: null, skills: [], has_profile: false }, history = [] } = {}) {
  getInterviewOptions.mockResolvedValue(options);
  getInterviewRoles.mockResolvedValue({ roles: ROLES });
  getInterviewSuggestions.mockImplementation((role) =>
    Promise.resolve(role ? { target_role: null, skills: [], has_profile: true } : suggestions)
  );
  listInterviews.mockResolvedValue({ total: history.length, limit: 5, offset: 0, interviews: history });
  previewInterviewBlueprint.mockResolvedValue(DB_PLAN);
  return render(<InterviewSetupPage />);
}

function summary() {
  return screen.getByRole('heading', { name: /interview summary/i }).parentElement;
}

beforeEach(() => {
  jest.clearAllMocks();
});

test('defaults to a 15 minute, 6 question technical text interview with 2 practical slots', async () => {
  setup();
  const duration = await screen.findByLabelText('Duration');
  expect(duration).toHaveValue('15');
  expect(screen.getByRole('option', { name: '15 minutes (default)' })).toBeInTheDocument();
  expect(screen.getByLabelText('Number of questions')).toHaveValue('6');
  expect(screen.getByRole('radio', { name: /^technical/i })).toBeChecked();
  expect(screen.getByRole('radio', { name: /text interview/i })).toBeChecked();
  expect(screen.getByRole('radio', { name: /intermediate/i })).toBeChecked();
  expect(within(summary()).getByText('6 (4 conceptual · 2 practical)')).toBeInTheDocument();
  expect(screen.getByText(/not a hiring decision/i)).toBeInTheDocument();
});

test('practicalCount mirrors the backend reservation rule', () => {
  expect([3, 4, 5, 6, 9, 12].map((n) => practicalCount('TECHNICAL', n))).toEqual([1, 2, 2, 2, 3, 4]);
  expect(practicalCount('BEHAVIORAL', 6)).toBe(0);
  expect(practicalCount('MIXED', 6)).toBe(1);
});

test('matchCatalogRole resolves titles, aliases and seniority prefixes but never guesses', () => {
  expect(matchCatalogRole('Frontend Developer', ROLES).slug).toBe('frontend-developer');
  expect(matchCatalogRole('Senior Front-End Developer', ROLES).slug).toBe('frontend-developer');
  expect(matchCatalogRole('DB Developer', ROLES).slug).toBe('database-developer');
  expect(matchCatalogRole('Blockchain Developer', ROLES)).toBeNull();
});

test('validates the configuration before creating an interview', async () => {
  setup();
  fireEvent.click(await screen.findByRole('button', { name: /start interview/i }));
  expect(await screen.findByText(/enter the role you are preparing for/i)).toBeInTheDocument();
  expect(createInterview).not.toHaveBeenCalled();
});

test('validateSetup rejects unsupported and oversized values', () => {
  const base = {
    targetRole: 'Engineer',
    interviewType: 'TECHNICAL',
    interactionMode: 'TEXT',
    durationMinutes: 15,
    questionCount: 6,
    focusAreas: [],
    instructions: '',
    jobDescription: '',
  };
  expect(validateSetup(base)).toEqual({});
  expect(validateSetup({ ...base, durationMinutes: 17 }).durationMinutes).toBeTruthy();
  expect(validateSetup({ ...base, questionCount: 7 }).questionCount).toBeTruthy();
  expect(validateSetup({ ...base, questionCount: 2 }).questionCount).toBeTruthy();
  expect(validateSetup({ ...base, interactionMode: 'VOICE' }, { voiceAvailable: false }).interactionMode).toBeTruthy();
  expect(validateSetup({ ...base, focusAreas: Array.from({ length: 9 }, (_, i) => `s${i}`) }).focusAreas).toBeTruthy();
  expect(validateSetup({ ...base, instructions: 'x'.repeat(501) }).instructions).toBeTruthy();
  expect(validateSetup({ ...base, jobDescription: 'x'.repeat(4001) }).jobDescription).toBeTruthy();
});

test('focus areas come from the selected role and change with it', async () => {
  setup();
  const role = await screen.findByLabelText('Target job role');
  fireEvent.change(role, { target: { value: 'Frontend Developer' } });
  expect(screen.getByRole('button', { name: 'React & State Management' })).toBeInTheDocument();
  expect(screen.queryByRole('button', { name: 'IP Addressing & Subnetting' })).not.toBeInTheDocument();

  fireEvent.click(screen.getByRole('button', { name: 'React & State Management' }));
  expect(screen.getByRole('button', { name: 'React & State Management' })).toHaveAttribute('aria-pressed', 'true');

  fireEvent.change(role, { target: { value: 'Network Engineer' } });
  expect(screen.getByRole('button', { name: 'IP Addressing & Subnetting' })).toBeInTheDocument();
  expect(screen.queryByRole('button', { name: 'React & State Management' })).not.toBeInTheDocument();
  expect(within(summary()).getByText('General for the role')).toBeInTheDocument(); // previous role's focus dropped
});

test('only role-relevant profile skills are suggested', async () => {
  setup();
  getInterviewSuggestions.mockImplementation((role) =>
    Promise.resolve(role === 'Frontend Developer' ? { skills: ['React'], has_profile: true } : { skills: [], has_profile: true })
  );
  fireEvent.change(await screen.findByLabelText('Target job role'), { target: { value: 'Frontend Developer' } });
  await waitFor(() => expect(getInterviewSuggestions).toHaveBeenCalledWith('Frontend Developer'));
  expect(await screen.findByText(/from your profile, relevant to this role/i)).toBeInTheDocument();
  expect(screen.getByRole('button', { name: 'React' })).toBeInTheDocument();
});

test('shows the server-built plan with reserved practical slots and starts the interview', async () => {
  createInterview.mockResolvedValue({ id: 'iv-1' });
  setup();
  fireEvent.change(await screen.findByLabelText('Target job role'), { target: { value: 'Database Developer' } });
  fireEvent.click(screen.getByRole('button', { name: 'Performance & Optimization' }));
  fireEvent.click(screen.getByRole('radio', { name: /advanced/i }));
  fireEvent.change(screen.getByLabelText(/job description/i), { target: { value: 'Own our reporting database.' } });

  const plan = await screen.findByRole('list', { name: /interview plan/i });
  expect(within(plan).getAllByText('SQL')).toHaveLength(2);
  expect(within(plan).getByText(/SQL Queries/)).toBeInTheDocument();
  expect(screen.getByText(/slots are reserved in this plan/i)).toBeInTheDocument();
  expect(previewInterviewBlueprint).toHaveBeenLastCalledWith(
    expect.objectContaining({ target_role: 'Database Developer', question_count: 6, focus_areas: ['Performance & Optimization'] })
  );

  fireEvent.click(screen.getByRole('button', { name: /start interview/i }));
  await waitFor(() => expect(mockPush).toHaveBeenCalledWith('/dashboard/interview/iv-1'));
  expect(createInterview).toHaveBeenCalledWith({
    target_role: 'Database Developer',
    interview_type: 'TECHNICAL',
    interaction_mode: 'TEXT',
    difficulty: 'ADVANCED',
    duration_minutes: 15,
    question_count: 6,
    focus_areas: ['Performance & Optimization'],
    instructions: null,
    job_description: 'Own our reporting database.',
  });
});

test('question count follows the selected duration', async () => {
  setup();
  fireEvent.change(await screen.findByLabelText('Duration'), { target: { value: '10' } });
  const count = screen.getByLabelText('Number of questions');
  expect(count).toHaveValue('4');
  expect(within(count).getAllByRole('option').map((o) => o.value)).toEqual(['3', '4']);
  fireEvent.change(count, { target: { value: '3' } });
  expect(within(summary()).getByText('3 (2 conceptual · 1 practical)')).toBeInTheDocument();
});

test('custom job titles are analysed on their own terms', async () => {
  analyzeInterviewRole.mockResolvedValue({
    slug: null, title: 'Blockchain Developer', family: 'Blockchain', source: 'custom', summary: '',
    focus_areas: ['Smart Contracts', 'Security'], practical_kinds: ['scenario'], languages: [],
    competencies: [{ name: 'Smart Contract Development' }, { name: 'Cryptography & Security' }],
  });
  setup();
  fireEvent.change(await screen.findByLabelText('Target job role'), { target: { value: 'Blockchain Developer' } });
  expect(screen.getByText(/custom role/i)).toBeInTheDocument();
  expect(screen.getByText(/never treated as a different role/i)).toBeInTheDocument();
  expect(previewInterviewBlueprint).not.toHaveBeenCalled(); // no LLM call until the user asks

  fireEvent.click(screen.getByRole('button', { name: /analyse role/i }));
  await waitFor(() => expect(analyzeInterviewRole).toHaveBeenCalledWith('Blockchain Developer'));
  expect(await screen.findByText(/Analysed: Smart Contract Development, Cryptography & Security/)).toBeInTheDocument();
  expect(screen.getByRole('button', { name: 'Smart Contracts' })).toBeInTheDocument();
});

test('voice mode is disabled with an explanation when transcription is not configured', async () => {
  setup();
  const voice = await screen.findByRole('radio', { name: /voice interview/i });
  expect(voice).toBeDisabled();
  expect(screen.getByText(/speech transcription is not configured/i)).toBeInTheDocument();
});

test('voice mode can be selected when transcription is available', async () => {
  setup({ options: { ...OPTIONS, transcription_available: true } });
  const voice = await screen.findByRole('radio', { name: /voice interview/i });
  fireEvent.click(voice);
  expect(voice).toBeChecked();
  expect(screen.getByText(/ask for microphone access/i)).toBeInTheDocument();
});

test('prefills the target role from the profile', async () => {
  setup({ suggestions: { target_role: 'Data Analyst', skills: [], has_profile: true } });
  expect(await screen.findByLabelText('Target job role')).toHaveValue('Data Analyst');
});

test('offers to resume an interview already in progress', async () => {
  setup({
    history: [{ id: 'active-1', status: 'IN_PROGRESS', target_role: 'QA Engineer', interview_type: 'MIXED', answered_count: 2 }],
  });
  const link = await screen.findByRole('link', { name: /resume interview/i });
  expect(link).toHaveAttribute('href', '/dashboard/interview/active-1');
});

test('shows a resume link when the backend reports an active interview conflict', async () => {
  createInterview.mockRejectedValue({
    response: { status: 409, data: { detail: { message: 'You already have an interview in progress.', interview_id: 'busy-1' } } },
  });
  setup();
  fireEvent.change(await screen.findByLabelText('Target job role'), { target: { value: 'Network Engineer' } });
  fireEvent.click(screen.getByRole('button', { name: /start interview/i }));
  expect(await screen.findByText(/already have an interview in progress/i)).toBeInTheDocument();
  expect(screen.getByRole('link', { name: /resume that interview/i })).toHaveAttribute('href', '/dashboard/interview/busy-1');
  expect(mockPush).not.toHaveBeenCalled();
});

test('shows an error state when options cannot load', async () => {
  getInterviewOptions.mockRejectedValue(new Error('Server down'));
  getInterviewRoles.mockResolvedValue({ roles: [] });
  getInterviewSuggestions.mockResolvedValue({ skills: [] });
  listInterviews.mockResolvedValue({ interviews: [] });
  render(<InterviewSetupPage />);
  expect(await screen.findByText(/couldn't load/i)).toBeInTheDocument();
});
