import LoginForm from '@/components/auth/LoginForm';
import BackgroundFX from '@/components/landing/BackgroundFX';

export const metadata = {
  title: 'Login — CareerSphere AI',
  description: 'Log in to your CareerSphere AI account',
};

export default function LoginPage({ searchParams }) {
  return (
    <div className="relative min-h-[calc(100vh-5rem)] flex-1 flex items-center justify-center px-4 py-12 sm:px-6 lg:px-8">
      <BackgroundFX />
      <LoginForm searchParams={searchParams} />
    </div>
  );
}

