'use client';

import React from 'react';
import InterviewAuthGate from '@/components/interview/InterviewAuthGate';
import InterviewSetupPage from '@/components/interview/InterviewSetupPage';

export default function InterviewDashboardPage() {
  return (
    <InterviewAuthGate>
      <InterviewSetupPage />
    </InterviewAuthGate>
  );
}
