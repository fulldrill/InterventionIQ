'use client';

import AIChatPanel from '@/components/ai/AIChatPanel';
import ProficiencyBarChart from '@/components/charts/ProficiencyBarChart';
import { assessmentApi } from '@/lib/api';
import Link from 'next/link';
import { useRouter } from 'next/navigation';
import { useCallback, useEffect, useState } from 'react';

type Tab = 'upload' | 'standards' | 'assistant';

interface AssessmentItem {
  id: string;
  name: string;
  week_of: string | null;
}

interface ClassroomItem {
  id: string;
  name: string;
}

interface StandardData {
  standard: string;
  proficiency: number;
  student_count: number;
  suppressed: boolean;
}

interface ItemAnalysisData {
  question_type: string;
  avg_score_pct: number;
  item_count: number;
}

function extractMarylandDomain(standardCode: string): string {
  const domainMatch = standardCode.match(/(\d+\.[A-Z]{2})/);
  if (!domainMatch) {
    return 'Other Standards';
  }
  const domainCode = domainMatch[1];
  const domainLabels: Record<string, string> = {
    '3.OA': 'Operations and Algebraic Thinking (3.OA)',
    '3.NBT': 'Number and Operations in Base Ten (3.NBT)',
    '3.NF': 'Number and Operations - Fractions (3.NF)',
    '3.MD': 'Measurement and Data (3.MD)',
    '3.G': 'Geometry (3.G)',
  };
  return domainLabels[domainCode] || `${domainCode} Domain`;
}

export default function DashboardPage() {
  const router = useRouter();
  const [email, setEmail] = useState('');
  const [role, setRole] = useState('');
  const [isCheckingAuth, setIsCheckingAuth] = useState(true);
  const [activeTab, setActiveTab] = useState<Tab>('upload');
  const [classrooms, setClassrooms] = useState<ClassroomItem[]>([]);
  const [assessments, setAssessments] = useState<AssessmentItem[]>([]);
  const [selectedClassroomId, setSelectedClassroomId] = useState('');
  const [selectedAssessmentId, setSelectedAssessmentId] = useState('');
  const [standardData, setStandardData] = useState<StandardData[]>([]);
  const [itemAnalysisData, setItemAnalysisData] = useState<ItemAnalysisData[]>([]);
  const [isLoadingSample, setIsLoadingSample] = useState(false);
  const [isUploadingCsv, setIsUploadingCsv] = useState(false);
  const [isLoadingStandards, setIsLoadingStandards] = useState(false);
  const [notice, setNotice] = useState('');
  const [errorMessage, setErrorMessage] = useState('');
  const [mathCsvFile, setMathCsvFile] = useState<File | null>(null);
  const [metadataCsvFile, setMetadataCsvFile] = useState<File | null>(null);
  const [customAssessmentName, setCustomAssessmentName] = useState('');

  const tokenHeaders = (): Record<string, string> => {
    const token = window.localStorage.getItem('access_token');
    if (!token) {
      return {};
    }
    return { Authorization: `Bearer ${token}` };
  };

  const loadClassroomsAndAssessments = useCallback(async () => {
    const [classroomResponse, assessmentResponse] = await Promise.all([
      fetch('/api/assessments/classrooms/mine', {
        credentials: 'include',
        headers: tokenHeaders(),
      }),
      fetch('/api/assessments', {
        credentials: 'include',
        headers: tokenHeaders(),
      }),
    ]);

    if (!classroomResponse.ok || !assessmentResponse.ok) {
      throw new Error('Unable to load classrooms and assessments.');
    }

    const classroomPayload = (await classroomResponse.json()) as ClassroomItem[];
    const assessmentPayload = (await assessmentResponse.json()) as AssessmentItem[];

    setClassrooms(classroomPayload);
    setAssessments(assessmentPayload);

    if (!selectedClassroomId && classroomPayload.length > 0) {
      setSelectedClassroomId(classroomPayload[0].id);
    }
    if (!selectedAssessmentId && assessmentPayload.length > 0) {
      setSelectedAssessmentId(assessmentPayload[0].id);
    }
  }, [selectedAssessmentId, selectedClassroomId]);

  const loadStandards = useCallback(async (assessmentId: string) => {
    if (!assessmentId) {
      setStandardData([]);
      setItemAnalysisData([]);
      return;
    }
    setIsLoadingStandards(true);
    setErrorMessage('');
    try {
      const [standardsResponse, itemAnalysisResponse] = await Promise.all([
        fetch(`/api/analytics/proficiency_by_standard?assessment_id=${assessmentId}`, {
          credentials: 'include',
          headers: tokenHeaders(),
        }),
        fetch(`/api/analytics/item_analysis?assessment_id=${assessmentId}`, {
          credentials: 'include',
          headers: tokenHeaders(),
        }),
      ]);

      if (!standardsResponse.ok || !itemAnalysisResponse.ok) {
        throw new Error('Could not load analytics for this assessment.');
      }

      const standardsPayload = (await standardsResponse.json()) as { data?: StandardData[] };
      const itemPayload = (await itemAnalysisResponse.json()) as { data?: ItemAnalysisData[] };

      setStandardData(standardsPayload.data || []);
      setItemAnalysisData(itemPayload.data || []);
    } catch (error) {
      setErrorMessage(error instanceof Error ? error.message : 'Unable to load analytics.');
      setStandardData([]);
      setItemAnalysisData([]);
    } finally {
      setIsLoadingStandards(false);
    }
  }, []);

  useEffect(() => {
    let isMounted = true;

    const verifySession = async () => {
      const token = window.localStorage.getItem('access_token');

      if (!token) {
        router.replace('/login');
        return;
      }

      const decodeEmailFromToken = (jwt: string) => {
        try {
          const payload = JSON.parse(atob(jwt.split('.')[1] ?? '')) as { sub?: string };
          return payload.sub ?? 'Authenticated User';
        } catch {
          return 'Authenticated User';
        }
      };

      const tryGetMe = async (accessToken: string) => {
        return fetch('/api/auth/me', {
          method: 'GET',
          credentials: 'include',
          headers: {
            Authorization: `Bearer ${accessToken}`,
          },
        });
      };

      try {
        let activeToken = token;
        let meResponse = await tryGetMe(activeToken);

        if (meResponse.status === 401) {
          const refreshResponse = await fetch('/api/auth/refresh', {
            method: 'POST',
            credentials: 'include',
          });

          if (!refreshResponse.ok) {
            throw new Error('Session expired');
          }

          const refreshPayload = await refreshResponse.json().catch(() => ({}));
          const newAccessToken = String(refreshPayload?.access_token ?? '');
          if (!newAccessToken) {
            throw new Error('Session expired');
          }

          window.localStorage.setItem('access_token', newAccessToken);
          activeToken = newAccessToken;
          meResponse = await tryGetMe(activeToken);
        }

        if (!meResponse.ok) {
          throw new Error('Session invalid');
        }

        const profile = (await meResponse.json().catch(() => ({}))) as { role?: string };

        if (!isMounted) {
          return;
        }

        setEmail(decodeEmailFromToken(activeToken));
        setRole(profile.role ?? 'teacher');
        setIsCheckingAuth(false);
        await loadClassroomsAndAssessments();
      } catch {
        window.localStorage.removeItem('access_token');
        router.replace('/login');
      }
    };

    void verifySession();

    return () => {
      isMounted = false;
    };
  }, [loadClassroomsAndAssessments, router]);

  useEffect(() => {
    if (!selectedAssessmentId) {
      setStandardData([]);
      return;
    }
    void loadStandards(selectedAssessmentId);
  }, [loadStandards, selectedAssessmentId]);

  const handleLogout = async () => {
    await fetch('/api/auth/logout', {
      method: 'POST',
      credentials: 'include',
    }).catch(() => undefined);
    window.localStorage.removeItem('access_token');
    router.replace('/login');
  };

  const handleLoadSampleData = async () => {
    setIsLoadingSample(true);
    setNotice('');
    setErrorMessage('');
    try {
      const formData = new FormData();
      if (selectedClassroomId) {
        formData.append('classroom_id', selectedClassroomId);
      }
      const response = await fetch('/api/assessments/load-sample', {
        method: 'POST',
        credentials: 'include',
        headers: tokenHeaders(),
        body: formData,
      });

      const payload = await response.json().catch(() => ({}));
      if (!response.ok) {
        throw new Error(payload?.detail || 'Unable to load sample data.');
      }

      await loadClassroomsAndAssessments();
      const createdId = String(payload?.assessment_id || '');
      if (createdId) {
        setSelectedAssessmentId(createdId);
        setActiveTab('standards');
      }
      setNotice('Sample assessment loaded. Maryland standard categorization is ready in the Standards tab.');
    } catch (error) {
      setErrorMessage(error instanceof Error ? error.message : 'Could not load sample data.');
    } finally {
      setIsLoadingSample(false);
    }
  };

  const handleUploadCsv = async () => {
    if (!mathCsvFile || !metadataCsvFile) {
      setErrorMessage('Select both the assessment CSV and metadata CSV first.');
      return;
    }

    setIsUploadingCsv(true);
    setNotice('');
    setErrorMessage('');
    try {
      const payload = await assessmentApi.upload(
        mathCsvFile,
        metadataCsvFile,
        selectedClassroomId || undefined,
        customAssessmentName || undefined,
      );

      await loadClassroomsAndAssessments();
      const createdId = String(payload?.assessment_id || '');
      if (createdId) {
        setSelectedAssessmentId(createdId);
        setActiveTab('standards');
      }

      setNotice('CSV upload completed. Standards and item analysis are now available.');
      setMathCsvFile(null);
      setMetadataCsvFile(null);
      setCustomAssessmentName('');
    } catch (error) {
      setErrorMessage(error instanceof Error ? error.message : 'CSV upload failed.');
    } finally {
      setIsUploadingCsv(false);
    }
  };

  if (isCheckingAuth) {
    return (
      <main className="min-h-screen bg-gradient-to-br from-cyan-100 via-white to-amber-100 px-4 py-8 text-slate-900 dark:from-slate-950 dark:via-slate-900 dark:to-slate-950 dark:text-slate-100 sm:px-6 lg:px-8">
        <div className="mx-auto flex w-full max-w-5xl items-center justify-center rounded-2xl border border-slate-300 bg-white p-8 shadow-lg dark:border-slate-700 dark:bg-slate-900">
          <p className="text-sm font-semibold">Verifying your session...</p>
        </div>
      </main>
    );
  }

  const domainSummary = standardData.reduce<Record<string, number[]>>((acc, row) => {
    const domain = extractMarylandDomain(row.standard);
    if (!acc[domain]) {
      acc[domain] = [];
    }
    if (!row.suppressed) {
      acc[domain].push(row.proficiency);
    }
    return acc;
  }, {});

  return (
    <main className="min-h-screen bg-gradient-to-br from-cyan-100 via-white to-amber-100 px-4 py-8 text-slate-900 dark:from-slate-950 dark:via-slate-900 dark:to-slate-950 dark:text-slate-100 sm:px-6 lg:px-8">
      <div className="mx-auto w-full max-w-5xl space-y-6">
        <header className="rounded-2xl border border-slate-300 bg-white p-6 shadow-lg dark:border-slate-700 dark:bg-slate-900">
          <p className="text-xs font-semibold uppercase tracking-[0.2em] text-cyan-700 dark:text-cyan-300">InterventionIQ</p>
          <h1 className="mt-2 text-3xl font-bold">Dashboard</h1>
          <p className="mt-2 text-sm text-slate-700 dark:text-slate-300">Signed in as {email}</p>
          <p className="mt-1 text-xs uppercase tracking-wide text-slate-600 dark:text-slate-400">Role: {role}</p>
        </header>

        <section className="rounded-2xl border border-slate-300 bg-white p-4 shadow-sm dark:border-slate-700 dark:bg-slate-900">
          <div className="flex flex-wrap gap-2">
            <button
              type="button"
              onClick={() => setActiveTab('upload')}
              className={`rounded-lg px-4 py-2 text-sm font-semibold ${activeTab === 'upload' ? 'bg-cyan-700 text-white dark:bg-cyan-500 dark:text-slate-950' : 'border border-slate-300 dark:border-slate-600'}`}
            >
              Upload / Sample Data
            </button>
            <button
              type="button"
              onClick={() => setActiveTab('standards')}
              className={`rounded-lg px-4 py-2 text-sm font-semibold ${activeTab === 'standards' ? 'bg-cyan-700 text-white dark:bg-cyan-500 dark:text-slate-950' : 'border border-slate-300 dark:border-slate-600'}`}
            >
              Maryland Standards
            </button>
            <button
              type="button"
              onClick={() => setActiveTab('assistant')}
              className={`rounded-lg px-4 py-2 text-sm font-semibold ${activeTab === 'assistant' ? 'bg-cyan-700 text-white dark:bg-cyan-500 dark:text-slate-950' : 'border border-slate-300 dark:border-slate-600'}`}
            >
              AI Assistant
            </button>
          </div>
        </section>

        {notice && (
          <p className="rounded-lg border border-emerald-500/40 bg-emerald-100 px-3 py-2 text-sm font-medium text-emerald-800 dark:border-emerald-500/50 dark:bg-emerald-900/30 dark:text-emerald-300">
            {notice}
          </p>
        )}
        {errorMessage && (
          <p className="rounded-lg border border-red-500/40 bg-red-100 px-3 py-2 text-sm font-medium text-red-800 dark:border-red-500/50 dark:bg-red-900/30 dark:text-red-300">
            {errorMessage}
          </p>
        )}

        {activeTab === 'upload' && (
          <section className="rounded-2xl border border-slate-300 bg-white p-6 shadow-sm dark:border-slate-700 dark:bg-slate-900">
            <h2 className="text-xl font-semibold">Load Assessment Data</h2>
            <p className="mt-2 text-sm text-slate-700 dark:text-slate-300">
              Load the included sample files and generate proficiency analytics categorized by Maryland-aligned standards.
            </p>
            <div className="mt-4 space-y-4">
              <label className="block text-sm font-semibold">Target Classroom</label>
              <select
                value={selectedClassroomId}
                onChange={(event) => setSelectedClassroomId(event.target.value)}
                className="w-full rounded-xl border border-slate-400 bg-white px-4 py-3 text-sm outline-none transition focus:border-cyan-600 focus:ring-2 focus:ring-cyan-600 dark:border-slate-500 dark:bg-slate-950 dark:focus:border-cyan-400 dark:focus:ring-cyan-400"
              >
                <option value="">Auto-create / first available classroom</option>
                {classrooms.map((item) => (
                  <option key={item.id} value={item.id}>
                    {item.name}
                  </option>
                ))}
              </select>

              <div className="grid gap-3 sm:grid-cols-2">
                <div>
                  <label className="block text-sm font-semibold">Assessment CSV (Reveal Math)</label>
                  <input
                    type="file"
                    accept=".csv"
                    onChange={(event) => setMathCsvFile(event.target.files?.[0] || null)}
                    className="mt-2 w-full rounded-xl border border-slate-400 bg-white px-3 py-2 text-sm dark:border-slate-500 dark:bg-slate-950"
                  />
                </div>
                <div>
                  <label className="block text-sm font-semibold">Metadata CSV</label>
                  <input
                    type="file"
                    accept=".csv"
                    onChange={(event) => setMetadataCsvFile(event.target.files?.[0] || null)}
                    className="mt-2 w-full rounded-xl border border-slate-400 bg-white px-3 py-2 text-sm dark:border-slate-500 dark:bg-slate-950"
                  />
                </div>
              </div>

              <div>
                <label className="block text-sm font-semibold">Assessment Name (optional)</label>
                <input
                  type="text"
                  value={customAssessmentName}
                  onChange={(event) => setCustomAssessmentName(event.target.value)}
                  placeholder="Grade 3 Unit 4 Checkpoint"
                  className="mt-2 w-full rounded-xl border border-slate-400 bg-white px-4 py-3 text-sm outline-none transition focus:border-cyan-600 focus:ring-2 focus:ring-cyan-600 dark:border-slate-500 dark:bg-slate-950 dark:focus:border-cyan-400 dark:focus:ring-cyan-400"
                />
              </div>

              <button
                type="button"
                onClick={handleUploadCsv}
                disabled={isUploadingCsv || !mathCsvFile || !metadataCsvFile}
                className="inline-flex items-center justify-center rounded-xl bg-slate-800 px-4 py-3 text-sm font-semibold text-white transition hover:bg-slate-900 disabled:cursor-not-allowed disabled:opacity-70 dark:bg-slate-200 dark:text-slate-900 dark:hover:bg-white"
              >
                {isUploadingCsv ? 'Uploading CSV files...' : 'Upload CSV Files'}
              </button>

              <div className="h-px bg-slate-200 dark:bg-slate-700" />

              <button
                type="button"
                onClick={handleLoadSampleData}
                disabled={isLoadingSample}
                className="inline-flex items-center justify-center rounded-xl bg-cyan-700 px-4 py-3 text-sm font-semibold text-white transition hover:bg-cyan-800 disabled:cursor-not-allowed disabled:opacity-70 dark:bg-cyan-500 dark:text-slate-950 dark:hover:bg-cyan-400"
              >
                {isLoadingSample ? 'Loading sample data...' : 'Load Sample Data'}
              </button>
            </div>
          </section>
        )}

        {activeTab === 'standards' && (
          <section className="space-y-4 rounded-2xl border border-slate-300 bg-white p-6 shadow-sm dark:border-slate-700 dark:bg-slate-900">
            <div className="flex flex-wrap items-end gap-3">
              <div className="min-w-[260px] flex-1">
                <label className="block text-sm font-semibold">Assessment</label>
                <select
                  value={selectedAssessmentId}
                  onChange={(event) => setSelectedAssessmentId(event.target.value)}
                  className="mt-2 w-full rounded-xl border border-slate-400 bg-white px-4 py-3 text-sm outline-none transition focus:border-cyan-600 focus:ring-2 focus:ring-cyan-600 dark:border-slate-500 dark:bg-slate-950 dark:focus:border-cyan-400 dark:focus:ring-cyan-400"
                >
                  {assessments.map((item) => (
                    <option key={item.id} value={item.id}>
                      {item.name}
                    </option>
                  ))}
                </select>
              </div>
            </div>

            {isLoadingStandards ? (
              <p className="text-sm font-semibold">Loading standards analytics...</p>
            ) : standardData.length === 0 ? (
              <p className="text-sm text-slate-700 dark:text-slate-300">No analytics yet. Load sample data first.</p>
            ) : (
              <>
                <ProficiencyBarChart data={standardData} height={380} />

                <article className="rounded-xl border border-slate-300 p-4 dark:border-slate-700">
                  <h3 className="text-sm font-semibold">Item Analysis by Question Type</h3>
                  {itemAnalysisData.length === 0 ? (
                    <p className="mt-2 text-xs text-slate-600 dark:text-slate-400">No item analysis data available.</p>
                  ) : (
                    <div className="mt-3 space-y-2">
                      {itemAnalysisData.map((row) => (
                        <div key={row.question_type} className="space-y-1">
                          <div className="flex items-center justify-between text-xs">
                            <span className="font-medium">{row.question_type}</span>
                            <span>{row.avg_score_pct.toFixed(1)}% ({row.item_count} items)</span>
                          </div>
                          <div className="h-2 rounded bg-slate-200 dark:bg-slate-800">
                            <div
                              className="h-2 rounded bg-cyan-600 dark:bg-cyan-400"
                              style={{ width: `${Math.max(0, Math.min(100, row.avg_score_pct))}%` }}
                            />
                          </div>
                        </div>
                      ))}
                    </div>
                  )}
                </article>

                <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-3">
                  {Object.entries(domainSummary).map(([domain, scores]) => {
                    const avg = scores.length > 0 ? scores.reduce((sum, n) => sum + n, 0) / scores.length : 0;
                    return (
                      <article key={domain} className="rounded-xl border border-slate-300 p-4 dark:border-slate-700">
                        <p className="text-sm font-semibold">{domain}</p>
                        <p className="mt-1 text-xs text-slate-600 dark:text-slate-400">Average proficiency</p>
                        <p className="mt-1 text-lg font-bold text-cyan-700 dark:text-cyan-300">{avg.toFixed(1)}%</p>
                      </article>
                    );
                  })}
                </div>
              </>
            )}
          </section>
        )}

        {activeTab === 'assistant' && (
          <section className="overflow-hidden rounded-2xl border border-slate-300 bg-white shadow-sm dark:border-slate-700 dark:bg-slate-900">
            <div className="h-[560px]">
              <AIChatPanel assessmentId={selectedAssessmentId || null} />
            </div>
          </section>
        )}

        <div className="flex flex-wrap gap-3">
          <Link
            href="/"
            className="inline-flex items-center justify-center rounded-xl border border-slate-400 px-4 py-2 text-sm font-semibold transition hover:border-cyan-600 hover:text-cyan-700 dark:border-slate-600 dark:hover:border-cyan-400 dark:hover:text-cyan-300"
          >
            Home
          </Link>
          <button
            type="button"
            onClick={handleLogout}
            className="inline-flex items-center justify-center rounded-xl bg-cyan-700 px-4 py-2 text-sm font-semibold text-white transition hover:bg-cyan-800 dark:bg-cyan-500 dark:text-slate-950 dark:hover:bg-cyan-400"
          >
            Log Out
          </button>
        </div>
      </div>
    </main>
  );
}
