import type { Metadata } from 'next';
import { ThemeProvider } from '../components/theme/theme-provider';
import './globals.css';

export const metadata: Metadata = {
  title: 'Forge — AI-Native Software Engineering Workspace',
  description:
    'Forge is the repository-aware software engineering workspace. Formulate plans, inspect AST symbols, execute terminal tools, and build software with durable engineering memory.',
};

export default function RootLayout({
  children,
}: Readonly<{ children: React.ReactNode }>) {
  return (
    <html lang="en" suppressHydrationWarning className="dark" data-theme="dark">
      <body className="min-h-screen bg-[var(--forge-bg)] text-[var(--forge-text-primary)] antialiased font-sans">
        <ThemeProvider defaultTheme="dark">
          {children}
        </ThemeProvider>
      </body>
    </html>
  );
}
