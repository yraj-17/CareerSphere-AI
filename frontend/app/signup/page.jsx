import SignupForm from '@/components/auth/SignupForm';

export const metadata = {
  title: 'Sign Up — CareerSphere AI',
  description: 'Create your new CareerSphere AI account',
};

export default function SignupPage() {
  return (
    <div className="flex min-h-0 flex-1 items-stretch bg-[#F5F6F8] lg:h-[calc(100dvh-68px)] lg:overflow-hidden">
      <SignupForm />
    </div>
  );
}
