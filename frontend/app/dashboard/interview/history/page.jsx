'use client';

import React from 'react';
import InterviewAuthGate from '@/components/interview/InterviewAuthGate';
import InterviewHistoryPage from '@/components/interview/InterviewHistoryPage';

export default function InterviewHistoryDashboardPage() {
  return (
    <InterviewAuthGate>
      <InterviewHistoryPage />
    </InterviewAuthGate>
  );
}
