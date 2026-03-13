'use client';

import { Moon, Sun } from 'lucide-react';
import Link from 'next/link';
import { FormEvent, useEffect, useMemo, useState } from 'react';

type SubmitState = 'idle' | 'loading' | 'success';

export default function HomePage() {
  const [isDark, setIsDark] = useState(false);
  const [email, setEmail] = useState('');
  const [emailTouched, setEmailTouched] = useState(false);
  const [submitState, setSubmitState] = useState<SubmitState>('idle');

  useEffect(() => {
    const storedTheme = window.localStorage.getItem('theme');
    const prefersDark = window.matchMedia('(prefers-color-scheme: dark)').matches;
    const shouldUseDark = storedTheme ? storedTheme === 'dark' : prefersDark;

    document.documentElement.classList.toggle('dark', shouldUseDark);
    setIsDark(shouldUseDark);
  }, []);

  const emailValid = useMemo(() => {
    if (!email) {
      return false;
    }
    return /^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(email);
  }, [email]);

  const showEmailError = emailTouched && !emailValid;

  const toggleTheme = () => {
    const next = !isDark;
    setIsDark(next);
    document.documentElement.classList.toggle('dark', next);
    window.localStorage.setItem('theme', next ? 'dark' : 'light');
  };

  const handleSubmit = async (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    setEmailTouched(true);

    if (!emailValid) {
      return;
    }

    setSubmitState('loading');

    await new Promise((resolve) => setTimeout(resolve, 1400));

    setSubmitState('success');
    setEmail('');
    setEmailTouched(false);
  };

  return (
    <div className="min-h-screen bg-gradient-to-br from-cyan-100 via-white to-amber-100 text-slate-900 transition-colors duration-300 dark:from-slate-950 dark:via-slate-900 dark:to-slate-950 dark:text-slate-100">
      <header className="border-b border-slate-300/80 bg-white/80 backdrop-blur-md dark:border-slate-700 dark:bg-slate-900/70">
        <nav className="mx-auto flex w-full max-w-6xl items-center justify-between px-4 py-4 sm:px-6 lg:px-8">
          <div>
            <p className="text-xs font-semibold uppercase tracking-[0.2em] text-cyan-700 dark:text-cyan-300">InterventionIQ</p>
            <h1 className="text-lg font-bold sm:text-xl">Student Insight Platform</h1>
          </div>

          <div className="flex items-center gap-3">
            <Link
              href="/login"
              className="hidden rounded-full border border-slate-400/70 px-4 py-2 text-sm font-medium text-slate-900 transition hover:border-cyan-500 hover:text-cyan-700 dark:border-slate-600 dark:text-slate-100 dark:hover:border-cyan-400 dark:hover:text-cyan-300 sm:inline-flex"
            >
              Log In
            </Link>
            <a
              href="#signup"
              className="hidden rounded-full border border-slate-400/70 px-4 py-2 text-sm font-medium text-slate-900 transition hover:border-cyan-500 hover:text-cyan-700 dark:border-slate-600 dark:text-slate-100 dark:hover:border-cyan-400 dark:hover:text-cyan-300 md:inline-flex"
            >
              Get Started
            </a>
            <button
              type="button"
              onClick={toggleTheme}
              aria-label="Toggle dark mode"
              className="inline-flex h-11 w-11 items-center justify-center rounded-full border border-slate-400/80 bg-white text-slate-900 shadow-sm transition hover:bg-slate-100 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-cyan-600 dark:border-slate-500 dark:bg-slate-800 dark:text-slate-100 dark:hover:bg-slate-700"
            >
              {isDark ? <Sun size={20} /> : <Moon size={20} />}
            </button>
          </div>
        </nav>
      </header>

      <main className="mx-auto grid w-full max-w-6xl gap-12 px-4 pb-16 pt-10 sm:px-6 md:grid-cols-2 md:items-center lg:px-8 lg:pt-16">
        <section className="space-y-6">
          <p className="inline-flex rounded-full bg-cyan-700 px-3 py-1 text-xs font-semibold tracking-wide text-white dark:bg-cyan-500 dark:text-slate-950">
            Modern Analytics for Teachers
          </p>
          <h2 className="text-4xl font-extrabold leading-tight sm:text-5xl">
            Understand student growth faster with AI-powered classroom insights.
          </h2>
          <p className="max-w-xl text-base leading-7 text-slate-700 dark:text-slate-300 sm:text-lg">
            Upload weekly assessments, monitor proficiency trends, and build interventions in minutes.
            Designed for high contrast accessibility and smooth use across mobile, tablet, and desktop.
          </p>

          <div className="grid gap-4 sm:grid-cols-3">
            <div className="rounded-2xl border border-slate-300 bg-white/85 p-4 shadow-sm dark:border-slate-700 dark:bg-slate-900/80">
              <p className="text-2xl font-bold text-cyan-700 dark:text-cyan-300">15m</p>
              <p className="text-sm text-slate-700 dark:text-slate-300">Weekly analysis time</p>
            </div>
            <div className="rounded-2xl border border-slate-300 bg-white/85 p-4 shadow-sm dark:border-slate-700 dark:bg-slate-900/80">
              <p className="text-2xl font-bold text-cyan-700 dark:text-cyan-300">100%</p>
              <p className="text-sm text-slate-700 dark:text-slate-300">Mobile responsive UI</p>
            </div>
            <div className="rounded-2xl border border-slate-300 bg-white/85 p-4 shadow-sm dark:border-slate-700 dark:bg-slate-900/80">
              <p className="text-2xl font-bold text-cyan-700 dark:text-cyan-300">24/7</p>
              <p className="text-sm text-slate-700 dark:text-slate-300">Anytime access</p>
            </div>
          </div>
        </section>

        <section id="signup" className="mx-auto w-full max-w-md rounded-3xl border border-slate-300 bg-white p-6 shadow-xl dark:border-slate-700 dark:bg-slate-900 sm:p-8">
          <h3 className="text-2xl font-bold">Sign Up</h3>
          <p className="mt-2 text-sm text-slate-700 dark:text-slate-300">
            Register your teacher account to unlock personalized dashboards.
          </p>
          <p className="mt-1 text-sm text-slate-700 dark:text-slate-300">
            Prefer the full flow?{' '}
            <Link href="/signup" className="font-semibold text-cyan-700 hover:text-cyan-800 dark:text-cyan-300 dark:hover:text-cyan-200">
              Open the dedicated signup page
            </Link>
            .
          </p>

          <form onSubmit={handleSubmit} className="mt-6 space-y-4" noValidate>
            <label htmlFor="email" className="block text-sm font-semibold text-slate-800 dark:text-slate-100">
              Work Email
            </label>
            <input
              id="email"
              name="email"
              type="email"
              value={email}
              onChange={(event) => setEmail(event.target.value)}
              onBlur={() => setEmailTouched(true)}
              placeholder="teacher@school.edu"
              className="w-full rounded-xl border border-slate-400 bg-white px-4 py-3 text-base text-slate-900 outline-none transition placeholder:text-slate-500 focus:border-cyan-600 focus:ring-2 focus:ring-cyan-600 dark:border-slate-500 dark:bg-slate-950 dark:text-slate-100 dark:placeholder:text-slate-400 dark:focus:border-cyan-400 dark:focus:ring-cyan-400"
              aria-invalid={showEmailError}
              aria-describedby={showEmailError ? 'email-error' : undefined}
            />

            {showEmailError && (
              <p id="email-error" className="text-sm font-medium text-red-700 dark:text-red-400">
                Please enter a valid email address.
              </p>
            )}

            <button
              type="submit"
              disabled={submitState === 'loading'}
              className="inline-flex w-full items-center justify-center rounded-xl bg-cyan-700 px-4 py-3 text-sm font-semibold text-white transition hover:bg-cyan-800 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-cyan-600 disabled:cursor-not-allowed disabled:opacity-70 dark:bg-cyan-500 dark:text-slate-950 dark:hover:bg-cyan-400"
            >
              {submitState === 'loading' ? (
                <span className="inline-flex items-center gap-2">
                  <span className="h-4 w-4 animate-spin rounded-full border-2 border-white border-t-transparent dark:border-slate-900 dark:border-t-transparent" />
                  Registering...
                </span>
              ) : submitState === 'success' ? (
                'Registered Successfully'
              ) : (
                'Create Account'
              )}
            </button>

            {submitState === 'success' && (
              <p className="rounded-lg border border-emerald-500/40 bg-emerald-100 px-3 py-2 text-sm font-medium text-emerald-800 dark:border-emerald-500/50 dark:bg-emerald-900/30 dark:text-emerald-300">
                Success! Your registration request was received.
              </p>
            )}
          </form>
        </section>
      </main>
    </div>
  );
}
