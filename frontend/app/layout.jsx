import './globals.css';
import { AuthProvider } from '@/context/AuthContext';
import Navbar from '@/components/common/Navbar';

export const metadata = {
  title: 'CareerSphere AI — AI-Powered Career Platform',
  description:
    'CareerSphere AI is the next-generation career growth and professional networking platform for students, graduates, and professionals.',
};

export default function RootLayout({ children }) {
  return (
    <html lang="en" className="dark">
      <body className="bg-slate-950 text-slate-100 flex flex-col min-h-screen bg-grid-pattern">
        <AuthProvider>
          <Navbar />
          <main className="flex-1 flex flex-col">{children}</main>
          <footer className="border-t border-slate-800/80 bg-slate-950/60 py-6 text-center text-xs text-slate-500">
            <div className="max-w-7xl mx-auto px-4 flex flex-col sm:flex-row items-center justify-between gap-2">
              <p>© {new Date().getFullYear()} CareerSphere AI. All rights reserved.</p>
              <p className="text-slate-500">
                Empowering next-generation career excellence with AI.
              </p>
            </div>
          </footer>
        </AuthProvider>
      </body>
    </html>
  );
}
