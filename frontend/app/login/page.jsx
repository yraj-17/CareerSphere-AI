import LoginForm from '@/components/auth/LoginForm';

export const metadata = {
  title: 'Login — CareerSphere AI',
  description: 'Log in to your CareerSphere AI account',
};

export default function LoginPage({ searchParams }) {
  return (
    <div className="flex-1 flex items-center justify-center px-4 py-12 sm:px-6 lg:px-8">
      <LoginForm searchParams={searchParams} />
    </div>
  );
}
