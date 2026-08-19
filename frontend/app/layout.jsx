import './globals.css';
import { AuthProvider } from '@/context/AuthContext';
import AppChrome from '@/components/common/AppChrome';

export const metadata = {
  title: 'CareerSphere AI - AI-Powered Career Platform',
  description:
    'CareerSphere AI is the next-generation career growth and professional networking platform for students, graduates, and professionals.',
};

export default function RootLayout({ children }) {
  return (
    <html lang="en" className="dark">
      <body className="bg-slate-950 text-slate-100 flex flex-col min-h-screen bg-grid-pattern">
        <AuthProvider>
          <AppChrome>{children}</AppChrome>
        </AuthProvider>
      </body>
    </html>
  );
}
