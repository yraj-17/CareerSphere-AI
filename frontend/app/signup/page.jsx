import SignupForm from '@/components/auth/SignupForm';

export const metadata = {
  title: 'Sign Up — CareerSphere AI',
  description: 'Create your new CareerSphere AI account',
};

export default function SignupPage() {
  return (
    <div className="flex-1 flex items-center justify-center px-4 py-12 sm:px-6 lg:px-8">
      <SignupForm />
    </div>
  );
}
