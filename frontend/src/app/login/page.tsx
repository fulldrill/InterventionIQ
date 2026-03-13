'use client';

import Link from 'next/link';
import { useRouter } from 'next/navigation';
import { FormEvent, useState } from 'react';
import { setAccessToken } from '../../lib/api';

type SubmitState = 'idle' | 'loading' | 'success' | 'error';

export default function LoginPage() {
  const router = useRouter();
  const [showPassword, setShowPassword] = useState(false);
  const [emailTouched, setEmailTouched] = useState(false);
  const [passwordTouched, setPasswordTouched] = useState(false);
  const [emailError, setEmailError] = useState('');
  const [passwordError, setPasswordError] = useState('');
  const [submitState, setSubmitState] = useState<SubmitState>('idle');
  const [message, setMessage] = useState('');

  const showEmailError = emailTouched && !!emailError;
  const showPasswordError = passwordTouched && !!passwordError;
  const hasValidationError = showEmailError || showPasswordError;

  const handleSubmit = async (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    const formData = new FormData(event.currentTarget);
    const submittedEmail = String(formData.get('email') ?? '').trim();
    const submittedPassword = String(formData.get('password') ?? '');

    setEmailTouched(true);
    setPasswordTouched(true);
    setSubmitState('idle');
    setMessage('');

    const nextEmailError = /^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(submittedEmail)
      ? ''
      : 'Enter a valid email address.';
    const nextPasswordError = submittedPassword.length > 0 ? '' : 'Password is required.';

    setEmailError(nextEmailError);
    setPasswordError(nextPasswordError);

    if (nextEmailError || nextPasswordError) {
      return;
    }

    setSubmitState('loading');

    const form = event.currentTarget;

    try {
      const response = await fetch('/api/auth/login', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        credentials: 'include',
        body: JSON.stringify({ email: submittedEmail, password: submittedPassword }),
      });

      const payload = await response.json().catch(() => ({}));

      if (!response.ok) {
        throw new Error(payload?.detail || 'Login failed. Please check your credentials.');
      }

      if (payload?.access_token) {
        setAccessToken(payload.access_token);
        window.localStorage.setItem('access_token', payload.access_token);
      }

      form.reset();
      setEmailTouched(false);
      setPasswordTouched(false);
      setEmailError('');
      setPasswordError('');
      setSubmitState('success');
      setMessage('Logged in successfully. You can now open protected pages.');
      router.push('/dashboard');
      router.refresh();
    } catch (error) {
      setSubmitState('error');
      setMessage(error instanceof Error ? error.message : 'Unable to login right now.');
    }
  };

  return (
    <main className="min-h-screen bg-gradient-to-br from-cyan-100 via-white to-amber-100 px-4 py-12 text-slate-900 dark:from-slate-950 dark:via-slate-900 dark:to-slate-950 dark:text-slate-100 sm:px-6 lg:px-8">
      <div className="mx-auto w-full max-w-md rounded-3xl border border-slate-300 bg-white p-6 shadow-xl dark:border-slate-700 dark:bg-slate-900 sm:p-8">
        <div className="mb-6">
          <p className="text-xs font-semibold uppercase tracking-[0.2em] text-cyan-700 dark:text-cyan-300">InterventionIQ</p>
          <h1 className="mt-2 text-2xl font-bold">Log In</h1>
          <p className="mt-2 text-sm text-slate-700 dark:text-slate-300">
            Welcome back. Enter your school account credentials.
          </p>
        </div>

        <form onSubmit={handleSubmit} className="space-y-4" noValidate>
          <div>
            <label htmlFor="email" className="block text-sm font-semibold">
              Work Email
            </label>
            <input
              id="email"
              name="email"
              type="email"
              onBlur={(event) => {
                setEmailTouched(true);
                const value = event.target.value.trim();
                setEmailError(/^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(value) ? '' : 'Enter a valid email address.');
              }}
              autoComplete="email"
              placeholder="teacher@school.edu"
              className="mt-2 w-full rounded-xl border border-slate-400 bg-white px-4 py-3 text-base outline-none transition placeholder:text-slate-500 focus:border-cyan-600 focus:ring-2 focus:ring-cyan-600 dark:border-slate-500 dark:bg-slate-950 dark:placeholder:text-slate-400 dark:focus:border-cyan-400 dark:focus:ring-cyan-400"
              aria-invalid={showEmailError}
            />
            {showEmailError && <p className="mt-2 text-sm font-medium text-red-700 dark:text-red-400">{emailError}</p>}
          </div>

          <div>
            <label htmlFor="password" className="block text-sm font-semibold">
              Password
            </label>
            <input
              id="password"
              name="password"
              type={showPassword ? 'text' : 'password'}
              onBlur={(event) => {
                setPasswordTouched(true);
                setPasswordError(event.target.value.length > 0 ? '' : 'Password is required.');
              }}
              autoComplete="current-password"
              placeholder="Your secure password"
              className="mt-2 w-full rounded-xl border border-slate-400 bg-white px-4 py-3 text-base outline-none transition placeholder:text-slate-500 focus:border-cyan-600 focus:ring-2 focus:ring-cyan-600 dark:border-slate-500 dark:bg-slate-950 dark:placeholder:text-slate-400 dark:focus:border-cyan-400 dark:focus:ring-cyan-400"
              aria-invalid={showPasswordError}
            />
            {showPasswordError && <p className="mt-2 text-sm font-medium text-red-700 dark:text-red-400">{passwordError}</p>}
          </div>

          <label className="inline-flex items-center gap-2 text-sm text-slate-700 dark:text-slate-300">
            <input
              type="checkbox"
              checked={showPassword}
              onChange={(event) => setShowPassword(event.target.checked)}
              className="h-4 w-4 rounded border-slate-400 text-cyan-700 focus:ring-cyan-600 dark:border-slate-500 dark:bg-slate-950 dark:text-cyan-400 dark:focus:ring-cyan-400"
            />
            Show password
          </label>

          <button
            type="submit"
            disabled={submitState === 'loading'}
            className="inline-flex w-full items-center justify-center rounded-xl bg-cyan-700 px-4 py-3 text-sm font-semibold text-white transition hover:bg-cyan-800 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-cyan-600 disabled:cursor-not-allowed disabled:opacity-70 dark:bg-cyan-500 dark:text-slate-950 dark:hover:bg-cyan-400"
          >
            {submitState === 'loading' ? 'Logging in...' : 'Log In'}
          </button>

          {message && !hasValidationError && (
            <p
              className={
                submitState === 'success'
                  ? 'rounded-lg border border-emerald-500/40 bg-emerald-100 px-3 py-2 text-sm font-medium text-emerald-800 dark:border-emerald-500/50 dark:bg-emerald-900/30 dark:text-emerald-300'
                  : 'rounded-lg border border-red-500/40 bg-red-100 px-3 py-2 text-sm font-medium text-red-800 dark:border-red-500/50 dark:bg-red-900/30 dark:text-red-300'
              }
            >
              {message}
            </p>
          )}
        </form>

        <p className="mt-6 text-sm text-slate-700 dark:text-slate-300">
          Need an account?{' '}
          <Link href="/signup" className="font-semibold text-cyan-700 hover:text-cyan-800 dark:text-cyan-300 dark:hover:text-cyan-200">
            Create one here
          </Link>
          .
        </p>
      </div>
    </main>
  );
}
