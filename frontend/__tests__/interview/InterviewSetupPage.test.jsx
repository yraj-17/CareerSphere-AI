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
  createInterview: jest.fn(),
  extractErrorMessage: jest.fn((err) => err?.response?.data?.detail?.message || err?.response?.data?.detail || err?.message || 'Error'),
  getInterviewOptions: jest.fn(),
  getInterviewSuggestions: jest.fn(),
  listInterviews: jest.fn(),
}));

import { createInterview, getInterviewOptions, getInterviewSuggestions, listInterviews } from '@/services/api';
import InterviewSetupPage, { validateSetup } from '@/components/interview/InterviewSetupPage';

const OPTIONS = {
  interview_types: ['TECHNICAL', 'BEHAVIORAL', 'MIXED'],
  interaction_modes: ['TEXT', 'VOICE'],
  difficulties: ['BEGINNER', 'INTERMEDIATE', 'ADVANCED'],
  durations: [10, 15, 20, 30],
  default_duration_minutes: 15,
  max_answer_length: 5000,
  max_focus_areas: 8,
  transcription_available: false,
  max_audio_seconds: 180,
  max_audio_bytes: 8388608,
};

function setup({ options = OPTIONS, suggestions = { target_role: null, skills: [], has_profile: false }, history = [] } = {}) {
  getInterviewOptions.mockResolvedValue(options);
  getInterviewSuggestions.mockResolvedValue(suggestions);
  listInterviews.mockResolvedValue({ total: history.length, limit: 5, offset: 0, interviews: history });
  return render(<InterviewSetupPage />);
}

beforeEach(() => {
  jest.clearAllMocks();
});

test('defaults to a 15 minute technical text interview', async () => {
  setup();
  const duration = await screen.findByLabelText('Duration');
  expect(duration).toHaveValue('15');
  expect(screen.getByRole('option', { name: '15 minutes (default)' })).toBeInTheDocument();
  expect(screen.getByRole('radio', { name: /^technical/i })).toBeChecked();
  expect(screen.getByRole('radio', { name: /text interview/i })).toBeChecked();
  expect(screen.getByRole('radio', { name: /intermediate/i })).toBeChecked();
  expect(screen.getByText(/not a hiring decision/i)).toBeInTheDocument();
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
    focusAreas: [],
    instructions: '',
  };
  expect(validateSetup(base)).toEqual({});
  expect(validateSetup({ ...base, durationMinutes: 17 }).durationMinutes).toBeTruthy();
  expect(validateSetup({ ...base, interactionMode: 'VOICE' }, { voiceAvailable: false }).interactionMode).toBeTruthy();
  expect(validateSetup({ ...base, focusAreas: Array.from({ length: 9 }, (_, i) => `s${i}`) }).focusAreas).toBeTruthy();
  expect(validateSetup({ ...base, instructions: 'x'.repeat(501) }).instructions).toBeTruthy();
});

test('selects type, difficulty, duration and focus areas, then starts the interview', async () => {
  createInterview.mockResolvedValue({ id: 'iv-1' });
  setup({ suggestions: { target_role: 'Data Analyst', skills: ['SQL', 'Python'], has_profile: true } });

  const role = await screen.findByLabelText('Target job role');
  expect(role).toHaveValue('Data Analyst');
  expect(screen.getByText(/suggested from your profile/i)).toBeInTheDocument();

  fireEvent.click(screen.getByRole('radio', { name: /behavioral \/ hr/i }));
  fireEvent.click(screen.getByRole('radio', { name: /advanced/i }));
  fireEvent.change(screen.getByLabelText('Duration'), { target: { value: '20' } });
  fireEvent.click(screen.getByRole('button', { name: 'SQL' }));
  fireEvent.change(screen.getByLabelText(/skills or focus areas/i), { target: { value: 'Stakeholder management' } });
  fireEvent.keyDown(screen.getByLabelText(/skills or focus areas/i), { key: 'Enter' });

  const summary = screen.getByRole('heading', { name: /interview summary/i }).parentElement;
  expect(within(summary).getByText('Behavioral / HR')).toBeInTheDocument();
  expect(within(summary).getByText('20 minutes')).toBeInTheDocument();
  expect(within(summary).getByText('Up to 8')).toBeInTheDocument();

  fireEvent.click(screen.getByRole('button', { name: /start interview/i }));
  await waitFor(() => expect(mockPush).toHaveBeenCalledWith('/dashboard/interview/iv-1'));
  expect(createInterview).toHaveBeenCalledWith({
    target_role: 'Data Analyst',
    interview_type: 'BEHAVIORAL',
    interaction_mode: 'TEXT',
    difficulty: 'ADVANCED',
    duration_minutes: 20,
    focus_areas: ['SQL', 'Stakeholder management'],
    instructions: null,
  });
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
  fireEvent.change(await screen.findByLabelText('Target job role'), { target: { value: 'Engineer' } });
  fireEvent.click(screen.getByRole('button', { name: /start interview/i }));
  expect(await screen.findByRole('alert')).toHaveTextContent(/already have an interview in progress/i);
  expect(screen.getByRole('link', { name: /resume that interview/i })).toHaveAttribute('href', '/dashboard/interview/busy-1');
  expect(mockPush).not.toHaveBeenCalled();
});

test('shows an error state when options cannot load', async () => {
  getInterviewOptions.mockRejectedValue(new Error('Server down'));
  getInterviewSuggestions.mockResolvedValue({ skills: [] });
  listInterviews.mockResolvedValue({ interviews: [] });
  render(<InterviewSetupPage />);
  expect(await screen.findByText(/couldn't load/i)).toBeInTheDocument();
});
