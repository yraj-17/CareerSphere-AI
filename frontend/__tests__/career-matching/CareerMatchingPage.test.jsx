/**
 * CareerMatchingPage — real job listings.
 *
 * Fixtures below are test-only mocks of the API response; they never reach production.
 */

import React from 'react';
import { render, screen, fireEvent, waitFor, within } from '@testing-library/react';

jest.mock('next/link', () => {
  const Link = ({ children, href, ...props }) => <a href={href} {...props}>{children}</a>;
  Link.displayName = 'MockLink';
  return Link;
});

jest.mock('framer-motion', () => {
  const strip = (Tag) => {
    const Component = ({ children, ...props }) => {
      const { initial, animate, transition, exit, ...rest } = props;
      return <Tag {...rest}>{children}</Tag>;
    };
    Component.displayName = `Motion(${Tag})`;
    return Component;
  };
  return {
    motion: { article: strip('article'), div: strip('div'), circle: strip('circle') },
    AnimatePresence: ({ children }) => <>{children}</>,
  };
});

jest.mock('@/services/api', () => ({
  getCareerMatching: jest.fn(),
  extractErrorMessage: jest.fn((err) => err?.message || 'An error occurred.'),
}));

import { getCareerMatching } from '@/services/api';
import CareerMatchingPage, {
  formatPostedDate,
  formatSalary,
  safeExternalUrl,
} from '@/components/career-matching/CareerMatchingPage';

const breakdown = {
  required_skill_score: 66.7,
  preferred_skill_score: 0,
  target_role_score: 100,
  experience_score: 100,
  location_remote_score: 100,
  career_preference_score: 50,
  matched_required_skills: ['Python', 'PostgreSQL'],
  missing_required_skills: ['Kafka'],
  matched_preferred_skills: [],
  missing_preferred_skills: [],
  target_role_match: { user_target_roles: ['Backend Engineer'], opportunity_target_role: 'Backend Engineer', relationship: 'exact:Backend Engineer', score: 100 },
  experience_match: { user_level: 'Entry Level', opportunity_level: 'Junior', relationship: 'level_match', score: 100 },
  location_match: { preferred_locations: [], opportunity_is_remote: false, relationship: 'preferred_location', score: 100 },
  preference_matches: [],
  match_reasons: ['Title matches your target role (Backend Engineer).', 'You have 2 of the 3 skills this listing mentions: Python, PostgreSQL.'],
};

const makeJob = (id, overrides = {}) => ({
  opportunity_id: id,
  title: `Backend Engineer ${id}`,
  company: 'Acme Payments',
  location: 'Bengaluru',
  country: 'India',
  work_mode: 'hybrid',
  is_remote: false,
  employment_type: 'full_time',
  opportunity_type: 'job',
  target_role: 'Backend Engineer',
  experience_level: 'Junior',
  salary_min: null,
  salary_max: null,
  salary_currency: null,
  salary_period: null,
  salary_text: null,
  posted_at: new Date(Date.now() - 3 * 86400000).toISOString(),
  source: 'greenhouse',
  source_label: 'Greenhouse',
  source_board: 'acme',
  attribution: "Listed on Acme Payments's Greenhouse job board",
  job_url: `https://job-boards.greenhouse.io/acme/jobs/${id}`,
  application_url: `https://job-boards.greenhouse.io/acme/jobs/${id}`,
  match_score: 78.4,
  match_label: 'Strong match',
  matched_skills: ['Python', 'PostgreSQL'],
  missing_skills: ['Kafka'],
  match_reasons: breakdown.match_reasons,
  explanation: 'Title matches your target role (Backend Engineer).',
  breakdown,
  ...overrides,
});

const success = (results, overrides = {}) => ({
  status: 'success',
  results,
  total_matches: results.length,
  page: 1,
  page_size: 10,
  total_pages: 1,
  profile_summary: { target_roles: ['Backend Engineer'], skills_count: 6, experience_level: 'Entry Level' },
  availability: { active_listings: 120, configured_providers: ['greenhouse'], providers_with_errors: [], last_successful_sync_at: '2026-11-05T00:00:00Z', sync_running: false },
  filter_options: { locations: ['Bengaluru', 'Mumbai'], work_modes: ['hybrid', 'onsite', 'remote'], employment_types: ['full_time'], sources: ['greenhouse'] },
  suggestions: [],
  gemini_status: 'not_configured',
  qwen_status: 'skipped',
  ...overrides,
});

beforeEach(() => {
  jest.clearAllMocks();
});

describe('loading and request errors', () => {
  test('shows the loading state while matches are requested', async () => {
    let resolve;
    getCareerMatching.mockReturnValue(new Promise((r) => { resolve = r; }));
    render(<CareerMatchingPage />);
    expect(screen.getByTestId('career-matching-loading')).toBeInTheDocument();
    resolve(success([makeJob('1')]));
    await waitFor(() => expect(screen.queryByTestId('career-matching-loading')).not.toBeInTheDocument());
  });

  test('API failure shows an error state (not an empty state) and retries', async () => {
    getCareerMatching.mockRejectedValueOnce(new Error('Career matching is temporarily unavailable.'));
    getCareerMatching.mockResolvedValueOnce(success([makeJob('1')]));
    render(<CareerMatchingPage />);
    expect(await screen.findByTestId('career-matching-error')).toHaveTextContent('Career matching is temporarily unavailable.');
    expect(screen.queryByTestId('state-no-matches')).not.toBeInTheDocument();
    fireEvent.click(screen.getByRole('button', { name: /try again/i }));
    expect(await screen.findAllByTestId('job-card')).toHaveLength(1);
  });
});

describe('distinct empty states', () => {
  test.each([
    ['no_profile', 'state-no-profile', /create your profile first/i],
    ['incomplete_profile', 'state-incomplete-profile', /complete your profile/i],
    ['provider_error', 'state-provider-error', /job providers are temporarily unavailable/i],
  ])('%s renders its own state', async (status, testId, title) => {
    getCareerMatching.mockResolvedValue({ status, message: `msg for ${status}`, missing_profile_fields: ['skills'], availability: null });
    render(<CareerMatchingPage />);
    const node = await screen.findByTestId(testId);
    expect(within(node).getByText(title)).toBeInTheDocument();
    expect(within(node).getByText(`msg for ${status}`)).toBeInTheDocument();
  });

  test('no jobs available while importing shows the importing state', async () => {
    getCareerMatching.mockResolvedValue({
      status: 'no_jobs_available', message: 'Job listings are being imported right now.',
      availability: { active_listings: 0, configured_providers: ['greenhouse'], providers_with_errors: [], last_successful_sync_at: null, sync_running: true },
    });
    render(<CareerMatchingPage />);
    expect(await screen.findByText('Importing job listings')).toBeInTheDocument();
  });

  test('no jobs available after a successful sync is a different message', async () => {
    getCareerMatching.mockResolvedValue({
      status: 'no_jobs_available', message: 'No active job listings are available.',
      availability: { active_listings: 0, configured_providers: ['greenhouse'], providers_with_errors: [], last_successful_sync_at: '2026-11-05T00:00:00Z', sync_running: false },
    });
    render(<CareerMatchingPage />);
    expect(await screen.findByText('No job listings available right now')).toBeInTheDocument();
  });

  test('no relevant matches shows the reason and suggestions, with filters still usable', async () => {
    getCareerMatching.mockResolvedValue(success([], {
      status: 'no_relevant_matches',
      message: 'None of the 120 active listings is a relevant match for your profile right now.',
      suggestions: ['Add more skills, including the technologies used in your projects.'],
    }));
    render(<CareerMatchingPage />);
    const node = await screen.findByTestId('state-no-matches');
    expect(within(node).getByText(/none of the 120 active listings/i)).toBeInTheDocument();
    expect(within(node).getByTestId('match-suggestions')).toHaveTextContent('Add more skills');
    expect(screen.getByTestId('career-matching-filters')).toBeInTheDocument();
  });
});

describe('job cards', () => {
  test('renders genuine listing details, skills, source and match score', async () => {
    getCareerMatching.mockResolvedValue(success([makeJob('1')]));
    render(<CareerMatchingPage />);
    const card = await screen.findByTestId('job-card');
    expect(within(card).getByText('Backend Engineer 1')).toBeInTheDocument();
    expect(within(card).getByText('Acme Payments')).toBeInTheDocument();
    expect(within(card).getByText('Bengaluru')).toBeInTheDocument();
    expect(within(card).getByText('Hybrid')).toBeInTheDocument();
    expect(within(card).getByText('Full-time')).toBeInTheDocument();
    expect(within(card).getByText('78%')).toBeInTheDocument();
    expect(within(card).getByText('Python')).toBeInTheDocument();
    expect(within(card).getByText('Kafka')).toBeInTheDocument();
    expect(within(card).getByText('Greenhouse')).toBeInTheDocument();
    expect(within(card).getByText('Posted 3 days ago')).toBeInTheDocument();
    expect(within(card).getByTestId('match-explanation')).toHaveTextContent('Title matches your target role');
  });

  test('salary is shown only when the provider published it', async () => {
    getCareerMatching.mockResolvedValue(success([
      makeJob('1'),
      makeJob('2', { salary_min: 1200000, salary_max: 1800000, salary_currency: 'INR', salary_period: 'year' }),
    ]));
    render(<CareerMatchingPage />);
    const [noSalary, withSalary] = await screen.findAllByTestId('job-card');
    expect(within(noSalary).queryByText(/₹/)).not.toBeInTheDocument();
    expect(within(withSalary).getByText(/₹12,00,000 – ₹18,00,000\/yr/)).toBeInTheDocument();
  });

  test('apply button opens the original application page in a new tab', async () => {
    getCareerMatching.mockResolvedValue(success([makeJob('42')]));
    render(<CareerMatchingPage />);
    const link = await screen.findByRole('link', { name: /apply on acme payments/i });
    expect(link).toHaveAttribute('href', 'https://job-boards.greenhouse.io/acme/jobs/42');
    expect(link).toHaveAttribute('target', '_blank');
    expect(link).toHaveAttribute('rel', expect.stringContaining('noopener'));
  });

  test('non-http application URLs are never rendered as links', async () => {
    getCareerMatching.mockResolvedValue(success([makeJob('1', { application_url: 'javascript:alert(1)', job_url: null })]));
    render(<CareerMatchingPage />);
    expect(await screen.findByText('Application link unavailable')).toBeInTheDocument();
    expect(screen.queryByRole('link', { name: /apply/i })).not.toBeInTheDocument();
  });

  test('Adzuna listings carry the required Adzuna attribution link', async () => {
    getCareerMatching.mockResolvedValue(success([makeJob('1', { source: 'adzuna', source_label: 'Adzuna', source_board: 'python developer' })]));
    render(<CareerMatchingPage />);
    expect(await screen.findByRole('link', { name: 'Adzuna' })).toHaveAttribute('href', 'https://www.adzuna.co.uk');
  });

  test('match details reveal deterministic reasons and breakdown', async () => {
    getCareerMatching.mockResolvedValue(success([makeJob('1')]));
    render(<CareerMatchingPage />);
    fireEvent.click(await screen.findByRole('button', { name: /why this match/i }));
    expect(screen.getByTestId('match-reasons')).toHaveTextContent('You have 2 of the 3 skills');
    expect(screen.getByText('Score breakdown')).toBeInTheDocument();
  });
});

describe('filters and pagination', () => {
  test('changing a filter refetches page 1 with that filter', async () => {
    getCareerMatching.mockResolvedValue(success([makeJob('1')]));
    render(<CareerMatchingPage />);
    await screen.findByTestId('job-card');
    fireEvent.change(screen.getByLabelText('Work mode'), { target: { value: 'remote' } });
    await waitFor(() => expect(getCareerMatching).toHaveBeenLastCalledWith(
      expect.objectContaining({ page: 1, filters: expect.objectContaining({ work_mode: 'remote' }) }),
    ));
    fireEvent.change(screen.getByLabelText('Location'), { target: { value: 'Mumbai' } });
    await waitFor(() => expect(getCareerMatching).toHaveBeenLastCalledWith(
      expect.objectContaining({ filters: expect.objectContaining({ work_mode: 'remote', location: 'Mumbai' }) }),
    ));
    fireEvent.click(screen.getByRole('button', { name: /clear filters/i }));
    await waitFor(() => expect(getCareerMatching).toHaveBeenLastCalledWith(
      expect.objectContaining({ filters: { location: '', work_mode: '', employment_type: '', experience: '' } }),
    ));
  });

  test('pagination requests the next page', async () => {
    window.scrollTo = jest.fn();
    getCareerMatching.mockResolvedValue(success([makeJob('1')], { total_matches: 25, total_pages: 3 }));
    render(<CareerMatchingPage />);
    await screen.findByTestId('job-card');
    expect(screen.getByText('Page 1 of 3')).toBeInTheDocument();
    fireEvent.click(screen.getByRole('button', { name: /next/i }));
    await waitFor(() => expect(getCareerMatching).toHaveBeenLastCalledWith(expect.objectContaining({ page: 2 })));
  });

  test('AI insights are requested only on demand', async () => {
    getCareerMatching.mockResolvedValue(success([makeJob('1')]));
    render(<CareerMatchingPage />);
    await screen.findByTestId('job-card');
    expect(getCareerMatching).toHaveBeenCalledWith(expect.objectContaining({ includeAI: false }));
    fireEvent.click(screen.getByRole('button', { name: /add ai insights/i }));
    await waitFor(() => expect(getCareerMatching).toHaveBeenLastCalledWith(expect.objectContaining({ includeAI: true })));
  });
});

describe('helpers', () => {
  test('safeExternalUrl allows only http(s)', () => {
    expect(safeExternalUrl('https://jobs.lever.co/x/1')).toBe('https://jobs.lever.co/x/1');
    expect(safeExternalUrl('javascript:alert(1)')).toBeNull();
    expect(safeExternalUrl(null)).toBeNull();
  });

  test('formatSalary never invents a salary', () => {
    expect(formatSalary({})).toBeNull();
    expect(formatSalary({ salary_text: '$20k - $35k' })).toBe('$20k - $35k');
  });

  test('formatPostedDate handles missing and invalid dates', () => {
    expect(formatPostedDate(null)).toBeNull();
    expect(formatPostedDate('not a date')).toBeNull();
  });
});

describe('presentation states with results', () => {
  test('sync running while matches exist shows a refresh notice, not an empty state', async () => {
    getCareerMatching.mockResolvedValue(success([makeJob('1')], {
      availability: { active_listings: 120, configured_providers: ['greenhouse'], providers_with_errors: [], last_successful_sync_at: '2026-11-05T00:00:00Z', sync_running: true },
    }));
    render(<CareerMatchingPage />);
    expect(await screen.findByTestId('sync-running-notice')).toHaveTextContent(/being refreshed/i);
    expect(screen.getAllByTestId('job-card')).toHaveLength(1);
  });

  test('a partial provider failure warns but still shows real matches', async () => {
    getCareerMatching.mockResolvedValue(success([makeJob('1')], {
      availability: { active_listings: 120, configured_providers: ['greenhouse', 'lever'], providers_with_errors: ['lever'], last_successful_sync_at: '2026-11-05T00:00:00Z', sync_running: false },
    }));
    render(<CareerMatchingPage />);
    expect(await screen.findByText(/last update from lever failed/i)).toBeInTheDocument();
    expect(screen.getAllByTestId('job-card')).toHaveLength(1);
  });

  test('a withdrawn listing disappears after refresh', async () => {
    getCareerMatching
      .mockResolvedValueOnce(success([makeJob('1'), makeJob('2')]))
      .mockResolvedValueOnce(success([makeJob('1')]));
    render(<CareerMatchingPage />);
    expect(await screen.findAllByTestId('job-card')).toHaveLength(2);
    fireEvent.click(screen.getByRole('button', { name: /refresh career matches/i }));
    await waitFor(() => expect(screen.getAllByTestId('job-card')).toHaveLength(1));
    expect(screen.queryByText('Backend Engineer 2')).not.toBeInTheDocument();
  });

  test('every empty outcome uses a different heading', async () => {
    const headings = {};
    const cases = {
      no_profile: { status: 'no_profile', message: 'm' },
      incomplete_profile: { status: 'incomplete_profile', message: 'm', missing_profile_fields: ['skills'] },
      provider_error: { status: 'provider_error', message: 'm' },
      importing: { status: 'no_jobs_available', message: 'm', availability: { sync_running: true, last_successful_sync_at: null } },
      no_jobs: { status: 'no_jobs_available', message: 'm', availability: { sync_running: false, last_successful_sync_at: '2026-11-05T00:00:00Z' } },
      no_matches: success([], { status: 'no_relevant_matches', message: 'm' }),
    };
    for (const [key, payload] of Object.entries(cases)) {
      getCareerMatching.mockResolvedValueOnce(payload);
      const { unmount } = render(<CareerMatchingPage />);
      headings[key] = (await screen.findByRole('heading', { level: 2 })).textContent;
      unmount();
    }
    expect(new Set(Object.values(headings)).size).toBe(Object.keys(cases).length);
  });
});
