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
    <html lang="en">
      <body className="flex min-h-screen flex-col bg-grid-pattern">
        <AuthProvider>
          <AppChrome>{children}</AppChrome>
        </AuthProvider>
      </body>
    </html>
  );
}
