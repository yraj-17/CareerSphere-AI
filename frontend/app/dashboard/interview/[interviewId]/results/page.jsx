'use client';

import React from 'react';
import { useParams } from 'next/navigation';
import InterviewAuthGate from '@/components/interview/InterviewAuthGate';
import InterviewResultsPage from '@/components/interview/InterviewResultsPage';

export default function InterviewResultsDashboardPage() {
  const params = useParams();
  const interviewId = params?.interviewId;

  return <InterviewAuthGate>{interviewId ? <InterviewResultsPage interviewId={interviewId} /> : null}</InterviewAuthGate>;
}
