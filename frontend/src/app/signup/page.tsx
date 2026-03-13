'use client';

import Link from 'next/link';
import { FormEvent, useMemo, useState } from 'react';

type SubmitState = 'idle' | 'loading' | 'success' | 'error';

const PASSWORD_RULE = /^(?=.*[a-z])(?=.*[A-Z])(?=.*\d)(?=.*[@$!%*?&^#])[A-Za-z\d@$!%*?&^#]{12,}$/;

export default function SignupPage() {
  const [fullName, setFullName] = useState('');
  const [schoolCode, setSchoolCode] = useState('');
  const [email, setEmail] = useState('');
  const [password, setPassword] = useState('');
  const [confirmPassword, setConfirmPassword] = useState('');
  const [showPassword, setShowPassword] = useState(false);
  const [submitted, setSubmitted] = useState(false);
  const [submitState, setSubmitState] = useState<SubmitState>('idle');
  const [message, setMessage] = useState('');

  const emailValid = useMemo(() => /^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(email), [email]);
  const passwordValid = useMemo(() => PASSWORD_RULE.test(password), [password]);
  const passwordsMatch = password === confirmPassword;
  const nameValid = fullName.trim().length >= 2;
  const schoolCodeValid = schoolCode.trim().length >= 3;

  const hasValidationError = submitted && (!nameValid || !schoolCodeValid || !emailValid || !passwordValid || !passwordsMatch);

  const handleSubmit = async (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    setSubmitted(true);
    setSubmitState('idle');
    setMessage('');

    if (!nameValid || !schoolCodeValid || !emailValid || !passwordValid || !passwordsMatch) {
      return;
    }

    setSubmitState('loading');

    try {
      const response = await fetch('/api/auth/signup', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          full_name: fullName.trim(),
          school_code: schoolCode.trim(),
          email,
          password,
        }),
      });

      const payload = await response.json().catch(() => ({}));

      if (!response.ok) {
        throw new Error(payload?.detail || 'Unable to create account right now.');
      }

      setSubmitState('success');
      setSubmitted(false);
      setMessage(payload?.message || 'Account created. Please check your email to verify your address.');
      setPassword('');
      setConfirmPassword('');
    } catch (error) {
      setSubmitState('error');
      setMessage(error instanceof Error ? error.message : 'Unable to create account right now.');
    }
  };

  return (
    <main className="min-h-screen bg-gradient-to-br from-cyan-100 via-white to-amber-100 px-4 py-12 text-slate-900 dark:from-slate-950 dark:via-slate-900 dark:to-slate-950 dark:text-slate-100 sm:px-6 lg:px-8">
      <div className="mx-auto w-full max-w-lg rounded-3xl border border-slate-300 bg-white p-6 shadow-xl dark:border-slate-700 dark:bg-slate-900 sm:p-8">
        <div className="mb-6">
          <p className="text-xs font-semibold uppercase tracking-[0.2em] text-cyan-700 dark:text-cyan-300">InterventionIQ</p>
          <h1 className="mt-2 text-2xl font-bold">Create Your Account</h1>
          <p className="mt-2 text-sm text-slate-700 dark:text-slate-300">
            Join your school workspace with your teacher profile and school join code.
          </p>
        </div>

        <form onSubmit={handleSubmit} className="space-y-4" noValidate>
          <div>
            <label htmlFor="full_name" className="block text-sm font-semibold">Full Name</label>
            <input
              id="full_name"
              type="text"
              value={fullName}
              onChange={(event) => setFullName(event.target.value)}
              placeholder="Jane Doe"
              className="mt-2 w-full rounded-xl border border-slate-400 bg-white px-4 py-3 text-base outline-none transition placeholder:text-slate-500 focus:border-cyan-600 focus:ring-2 focus:ring-cyan-600 dark:border-slate-500 dark:bg-slate-950 dark:placeholder:text-slate-400 dark:focus:border-cyan-400 dark:focus:ring-cyan-400"
            />
            {submitted && !nameValid && <p className="mt-2 text-sm font-medium text-red-700 dark:text-red-400">Enter your full name.</p>}
          </div>

          <div>
            <label htmlFor="school_code" className="block text-sm font-semibold">School Join Code</label>
            <input
              id="school_code"
              type="text"
              value={schoolCode}
              onChange={(event) => setSchoolCode(event.target.value)}
              placeholder="SAMPLE2026"
              className="mt-2 w-full rounded-xl border border-slate-400 bg-white px-4 py-3 text-base uppercase outline-none transition placeholder:text-slate-500 focus:border-cyan-600 focus:ring-2 focus:ring-cyan-600 dark:border-slate-500 dark:bg-slate-950 dark:placeholder:text-slate-400 dark:focus:border-cyan-400 dark:focus:ring-cyan-400"
            />
            {submitted && !schoolCodeValid && <p className="mt-2 text-sm font-medium text-red-700 dark:text-red-400">Enter a valid school code.</p>}
          </div>

          <div>
            <label htmlFor="email" className="block text-sm font-semibold">Work Email</label>
            <input
              id="email"
              type="email"
              value={email}
              onChange={(event) => setEmail(event.target.value)}
              placeholder="teacher@school.edu"
              className="mt-2 w-full rounded-xl border border-slate-400 bg-white px-4 py-3 text-base outline-none transition placeholder:text-slate-500 focus:border-cyan-600 focus:ring-2 focus:ring-cyan-600 dark:border-slate-500 dark:bg-slate-950 dark:placeholder:text-slate-400 dark:focus:border-cyan-400 dark:focus:ring-cyan-400"
            />
            {submitted && !emailValid && <p className="mt-2 text-sm font-medium text-red-700 dark:text-red-400">Enter a valid email address.</p>}
          </div>

          <div>
            <label htmlFor="password" className="block text-sm font-semibold">Password</label>
            <input
              id="password"
              type={showPassword ? 'text' : 'password'}
              value={password}
              onChange={(event) => setPassword(event.target.value)}
              placeholder="Min 12 chars with upper/lower/number/symbol"
              className="mt-2 w-full rounded-xl border border-slate-400 bg-white px-4 py-3 text-base outline-none transition placeholder:text-slate-500 focus:border-cyan-600 focus:ring-2 focus:ring-cyan-600 dark:border-slate-500 dark:bg-slate-950 dark:placeholder:text-slate-400 dark:focus:border-cyan-400 dark:focus:ring-cyan-400"
            />
            {submitted && !passwordValid && (
              <p className="mt-2 text-sm font-medium text-red-700 dark:text-red-400">
                Password must be at least 12 characters with uppercase, lowercase, number, and special character.
              </p>
            )}
          </div>

          <div>
            <label htmlFor="confirm_password" className="block text-sm font-semibold">Confirm Password</label>
            <input
              id="confirm_password"
              type={showPassword ? 'text' : 'password'}
              value={confirmPassword}
              onChange={(event) => setConfirmPassword(event.target.value)}
              placeholder="Re-enter password"
              className="mt-2 w-full rounded-xl border border-slate-400 bg-white px-4 py-3 text-base outline-none transition placeholder:text-slate-500 focus:border-cyan-600 focus:ring-2 focus:ring-cyan-600 dark:border-slate-500 dark:bg-slate-950 dark:placeholder:text-slate-400 dark:focus:border-cyan-400 dark:focus:ring-cyan-400"
            />
            {submitted && !passwordsMatch && <p className="mt-2 text-sm font-medium text-red-700 dark:text-red-400">Passwords do not match.</p>}
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
            {submitState === 'loading' ? 'Creating account...' : 'Create Account'}
          </button>

          {hasValidationError && submitState !== 'loading' && (
            <p className="rounded-lg border border-red-500/40 bg-red-100 px-3 py-2 text-sm font-medium text-red-800 dark:border-red-500/50 dark:bg-red-900/30 dark:text-red-300">
              Please correct the highlighted fields.
            </p>
          )}

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
          Already have an account?{' '}
          <Link href="/login" className="font-semibold text-cyan-700 hover:text-cyan-800 dark:text-cyan-300 dark:hover:text-cyan-200">
            Log in here
          </Link>
          .
        </p>
      </div>
    </main>
  );
}
