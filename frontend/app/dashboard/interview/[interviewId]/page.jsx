'use client';

import React from 'react';
import { useParams } from 'next/navigation';
import InterviewAuthGate from '@/components/interview/InterviewAuthGate';
import InterviewRoom from '@/components/interview/InterviewRoom';

export default function InterviewRoomDashboardPage() {
  const params = useParams();
  const interviewId = params?.interviewId;

  return <InterviewAuthGate>{interviewId ? <InterviewRoom interviewId={interviewId} /> : null}</InterviewAuthGate>;
}
