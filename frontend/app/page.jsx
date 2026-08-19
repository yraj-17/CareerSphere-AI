import BackgroundFX from '@/components/landing/BackgroundFX';
import Navbar from '@/components/landing/Navbar';
import Hero from '@/components/landing/Hero';
import ProblemSection from '@/components/landing/ProblemSection';
import FeaturesOrbit from '@/components/landing/FeaturesOrbit';
import HowItWorks from '@/components/landing/HowItWorks';
import AIEngine from '@/components/landing/AIEngine';
import InterviewDemo from '@/components/landing/InterviewDemo';
import AnalyticsDashboard from '@/components/landing/AnalyticsDashboard';
import NetworkingSection from '@/components/landing/NetworkingSection';
import ArchitectureFlow from '@/components/landing/ArchitectureFlow';
import TechnologyStack from '@/components/landing/TechnologyStack';
import SecuritySection from '@/components/landing/SecuritySection';
import CTASection from '@/components/landing/CTASection';
import Footer from '@/components/landing/Footer';

export default function HomePage() {
  return (
    <div className="relative min-h-screen overflow-x-clip bg-bg text-slate-100">
      <BackgroundFX />
      <Navbar />
      <Hero />
      <ProblemSection />
      <FeaturesOrbit />
      <HowItWorks />
      <AIEngine />
      <InterviewDemo />
      <AnalyticsDashboard />
      <NetworkingSection />
      <ArchitectureFlow />
      <TechnologyStack />
      <SecuritySection />
      <CTASection />
      <Footer />
    </div>
  );
}
