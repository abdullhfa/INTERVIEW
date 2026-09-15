import { useState, useEffect, useRef } from 'react';
import type {
  CandidateProfile,
  ProfileExtractionResult,
  GeneratedAnswer,
  InterviewSession,
  AnswerLengthMode,
  AnswerLanguageMode,
  ExpectedQuestion,
} from './types';
import { uploadCV, verifyProfile, addTargetRole, saveExpectedQuestions, createSession, getSession } from './api/client';
import { interviewWS } from './api/websocket';
import { AudioConfigModal } from './components/Interview/AudioConfigModal';
import {
  OTHER_SPECIALIZATION,
  PRIMARY_FIELDS,
  SPECIALIZATION_OPTIONS,
  TARGET_SPECIALIZATIONS,
} from './data/specializations';

// ── Page type ──────────────────────────────────────────────────
type Page = 'setup' | 'expected' | 'role' | 'session' | 'review';

export default function App() {
  const [page, setPage] = useState<Page>('setup');
  const [profile, setProfile] = useState<CandidateProfile | null>(null);
  const [extraction, setExtraction] = useState<ProfileExtractionResult | null>(null);
  const [session, setSession] = useState<InterviewSession | null>(null);
  const [answers, setAnswers] = useState<GeneratedAnswer[]>([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [lengthMode] = useState<AnswerLengthMode>('QUICK');
  const [langMode, setLangMode] = useState<AnswerLanguageMode>('SHOW_ARABIC_AND_ENGLISH');
  const [showAudioConfig, setShowAudioConfig] = useState(false);

  // ── CV Upload ────────────────────────────────────────────────
  const handleUpload = async (file: File) => {
    setLoading(true);
    setError(null);
    try {
      const result: ProfileExtractionResult = await uploadCV(file);
      setExtraction(result);
    } catch (e: unknown) {
      setError(e instanceof Error ? e.message : 'فشل رفع الملف');
    } finally {
      setLoading(false);
    }
  };

  // ── Verify Profile ───────────────────────────────────────────
  const handleVerify = async () => {
    if (!extraction) return;
    setLoading(true);
    setError(null);
    try {
      const verified = await verifyProfile(extraction.extracted_profile) as CandidateProfile;
      setProfile(verified);
      setExtraction(null);
      setPage('expected');
    } catch (e: unknown) {
      setError(e instanceof Error ? e.message : 'فشل التحقق من الملف الشخصي');
    } finally {
      setLoading(false);
    }
  };

  const handleSaveExpectedQuestions = async (items: ExpectedQuestion[]) => {
    if (!profile) return;
    setLoading(true);
    setError(null);
    try {
      const cleaned = items.filter(
        (item) => item.prompt.trim().length >= 2 && item.answer.trim().length >= 2,
      );
      const updated = await saveExpectedQuestions(profile.id, cleaned) as CandidateProfile;
      setProfile(updated);
      setPage('role');
    } catch (e: unknown) {
      setError(e instanceof Error ? e.message : 'فشل حفظ الأسئلة المتوقعة');
    } finally {
      setLoading(false);
    }
  };

  const handleSkipExpectedQuestions = () => {
    setPage('role');
  };

  // ── Add Target Role ──────────────────────────────────────────
  const handleAddRole = async (data: { field: string; specialization: string }) => {
    if (!profile) return;
    setLoading(true);
    try {
      const updated = await addTargetRole(profile.id, data) as CandidateProfile;
      setProfile(updated);
      setShowAudioConfig(true);
    } catch (e: unknown) {
      setError(e instanceof Error ? e.message : 'فشل حفظ التخصص');
    } finally {
      setLoading(false);
    }
  };

  const [audioConfig, setAudioConfig] = useState<{mic: number|null, loopback: number|null}>({mic: null, loopback: null});

  // ── Start Session ────────────────────────────────────────────
  const handleStartSession = async (
    micIdx: number | null,
    loopbackIdx: number | null,
    meetingPlatform: string,
  ) => {
    if (!profile) return;
    setLoading(true);
    setShowAudioConfig(false);
    setAudioConfig({ mic: micIdx, loopback: loopbackIdx });
    try {
      const s = await createSession({
        candidate_id: profile.id,
        mode: 'COACHING',
        target_role_id: profile.target_roles.at(-1)?.id,
        meeting_platform: meetingPlatform,
      }) as InterviewSession;
      setSession(s);
      setAnswers([]);
      setPage('session');
    } catch (e: unknown) {
      setError(e instanceof Error ? e.message : 'فشل بدء الجلسة');
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className={`app-layout app-layout--steps${page === 'setup' && !profile && !extraction ? ' app-layout--setup' : ''}`}>
      <main className="app-main">
        <header className="app-header app-header--steps">
          <div className="brand brand--inline">
            <div className="brand-copy">
              <strong>Interview</strong>
            </div>
          </div>
          <div className="header-actions">
            {session && page === 'session' && (
              <span className="badge badge--success">
                <span className="status-dot status-dot--active" /> الجلسة نشطة
              </span>
            )}
          </div>
        </header>

        <nav className="page-steps" aria-label="خطوات التحضير">
          <button
            type="button"
            className={`page-step ${page === 'setup' ? 'page-step--active' : ''} ${profile ? 'page-step--done' : ''}`}
            onClick={() => setPage('setup')}
          >
            <span className="page-step__num">1</span>
            <span className="page-step__label">إعداد الملف</span>
          </button>
          <span className="page-step__connector" aria-hidden="true" />
          <button
            type="button"
            className={`page-step ${page === 'expected' ? 'page-step--active' : ''} ${(profile?.expected_questions?.length ?? 0) > 0 ? 'page-step--done' : ''}`}
            onClick={() => setPage('expected')}
            disabled={!profile}
          >
            <span className="page-step__num">2</span>
            <span className="page-step__label">أسئلة متوقعة</span>
          </button>
          <span className="page-step__connector" aria-hidden="true" />
          <button
            type="button"
            className={`page-step ${page === 'role' ? 'page-step--active' : ''} ${profile?.target_roles?.length ? 'page-step--done' : ''}`}
            onClick={() => setPage('role')}
            disabled={!profile}
          >
            <span className="page-step__num">3</span>
            <span className="page-step__label">التخصص</span>
          </button>
          <span className="page-step__connector" aria-hidden="true" />
          <button
            type="button"
            className={`page-step ${page === 'session' ? 'page-step--active' : ''} ${session ? 'page-step--done' : ''}`}
            onClick={() => setShowAudioConfig(true)}
            disabled={!profile}
          >
            <span className="page-step__num">4</span>
            <span className="page-step__label">التدريب المباشر</span>
          </button>
          {answers.length > 0 && (
            <>
              <span className="page-step__connector" aria-hidden="true" />
              <button
                type="button"
                className={`page-step ${page === 'review' ? 'page-step--active' : ''}`}
                onClick={() => setPage('review')}
              >
                <span className="page-step__num">5</span>
                <span className="page-step__label">مراجعة التدريب</span>
              </button>
            </>
          )}
        </nav>

        <div className="app-content">
          {error && (
            <div className="alert alert--error mb-6" role="alert">
              <div className="flex items-center gap-3">
                <span>⚠️</span>
                <span style={{ color: 'var(--color-accent-danger)' }}>{error}</span>
                <button className="btn btn-ghost btn-sm alert__close" onClick={() => setError(null)} aria-label="إغلاق الخطأ">✕</button>
              </div>
            </div>
          )}

          {/* ── Setup Page ────────────────────────────────────── */}
          {page === 'setup' && (
            <div className="animate-fade-in flex flex-col gap-6">
              {!profile && !extraction && (
                <SetupUpload onUpload={handleUpload} loading={loading} />
              )}
              {extraction && !profile && (
                <ExtractionReview
                  extraction={extraction}
                  onVerify={handleVerify}
                  loading={loading}
                />
              )}
              {profile && (
                <ProfileDashboard
                  profile={profile}
                  onOpenRole={() => setPage('role')}
                  onOpenExpected={() => setPage('expected')}
                  onStartSession={() => setShowAudioConfig(true)}
                  loading={loading}
                />
              )}
            </div>
          )}

          {page === 'expected' && profile && (
            <ExpectedQuestionsPage
              profile={profile}
              onSave={handleSaveExpectedQuestions}
              onSkip={handleSkipExpectedQuestions}
              loading={loading}
            />
          )}

          {page === 'role' && profile && (
            <TargetRolePage profile={profile} onSave={handleAddRole} loading={loading} />
          )}

          {/* ── Session Page ──────────────────────────────────── */}
          {page === 'session' && (
            session ? (
              <LiveSessionContainer 
                session={session}
                lengthMode={lengthMode}
                langMode={langMode}
                onLangChange={setLangMode}
                audioConfig={audioConfig}
              />
            ) : (
              <div className="empty-state">
                <div className="empty-state__icon" aria-hidden="true">●</div>
                <h3 className="text-xl font-bold mb-2">لا توجد جلسة مباشرة نشطة</h3>
                <p className="text-muted mb-4 max-w-md">ابدأ جلسة تدريب مباشرة جديدة من لوحة الملف الشخصي.</p>
                <button className="btn btn-primary" onClick={() => setPage('setup')}>الذهاب إلى إعداد الملف</button>
              </div>
            )
          )}

          {/* ── Review Page ───────────────────────────────────── */}
          {page === 'review' && (
            answers.length > 0 ? <ReviewView answers={answers} /> : (
              <div className="empty-state">
                <div className="empty-state__icon" aria-hidden="true">↗</div>
                <h3 className="text-xl font-bold mb-2">لا توجد بيانات للمراجعة</h3>
                <p className="text-muted mb-4 max-w-md">أكمل جلسة مقابلة أولاً لعرض مراجعة التدريب التفصيلية.</p>
                <button className="btn btn-primary" onClick={() => setPage('setup')}>الذهاب إلى إعداد الملف</button>
              </div>
            )
          )}
        </div>
      </main>

      {showAudioConfig && (
        <AudioConfigModal 
          onStart={handleStartSession} 
          onCancel={() => setShowAudioConfig(false)} 
        />
      )}
    </div>
  );
}

// ── Live Session Wrapper ───────────────────────────────────────
/** Survives remounts so a transcript/answer is not wiped by React/Vite remounts. */
const liveUiCache = new Map<string, {
  answers: GeneratedAnswer[];
  activeQuestionText: string;
  sessionStatus: string;
  seenKeys: string[];
}>();

function LiveSessionContainer({ session, lengthMode, langMode, onLangChange, audioConfig }: any) {
  const cached = liveUiCache.get(session.id);
  const [answers, setAnswers] = useState<GeneratedAnswer[]>(() => cached?.answers ?? []);
  const [wsState, setWsState] = useState<string>('connecting');
  const [liveSessionState, setLiveSessionState] = useState<string>(session.state);
  const [activeQuestionText, setActiveQuestionText] = useState<string>(() => cached?.activeQuestionText ?? '');
  const [sessionStatus, setSessionStatus] = useState<string>(
    () => cached?.sessionStatus ?? 'جاري بدء التقاط الصوت...'
  );
  const seenAnswerKeys = useRef<Set<string>>(new Set(cached?.seenKeys ?? []));
  const pipelinePhaseRef = useRef<'idle' | 'listening' | 'dumping' | 'question' | 'generating'>('idle');
  const activeQuestionRef = useRef<string>(cached?.activeQuestionText ?? '');
  const answersRef = useRef<GeneratedAnswer[]>(cached?.answers ?? []);
  const lastAnsweredQuestionRef = useRef<string>('');

  const persistCache = (
    nextAnswers: GeneratedAnswer[],
    nextQuestion: string,
    nextStatus: string,
  ) => {
    liveUiCache.set(session.id, {
      answers: nextAnswers,
      activeQuestionText: nextQuestion,
      sessionStatus: nextStatus,
      seenKeys: Array.from(seenAnswerKeys.current),
    });
  };

  useEffect(() => {
    let cancelled = false;
    let startTimer: ReturnType<typeof setTimeout> | null = null;
    let liveStateTimer: ReturnType<typeof setInterval> | null = null;

    const normalizeQ = (text: string) => text.trim().toLowerCase().replace(/\s+/g, ' ');

    const setPhase = (phase: typeof pipelinePhaseRef.current) => {
      pipelinePhaseRef.current = phase;
    };

    const setQuestionText = (text: string) => {
      activeQuestionRef.current = text;
      setActiveQuestionText(text);
      persistCache(answersRef.current, text, sessionStatus);
    };

    const setStatus = (status: string) => {
      setSessionStatus(status);
      persistCache(answersRef.current, activeQuestionRef.current, status);
    };

    const storeAnswer = (answer: GeneratedAnswer) => {
      if (!answer) return;
      const key = answer.question_id || `${answer.question}\u0000${answer.answer_en}`;
      const prev = answersRef.current;
      let next = prev;
      const byId = answer.question_id
        ? prev.findIndex(a => a.question_id === answer.question_id)
        : -1;
      if (byId >= 0) {
        next = [...prev];
        next[byId] = answer;
      } else if (!seenAnswerKeys.current.has(key)) {
        seenAnswerKeys.current.add(key);
        next = [answer, ...prev];
      }
      answersRef.current = next;
      setAnswers(next);
      if (answer.question) {
        lastAnsweredQuestionRef.current = normalizeQ(answer.question);
      }
      setPhase('listening');
      const status = 'تم توليد الإجابة — بانتظار السؤال التالي';
      setSessionStatus(status);
      activeQuestionRef.current = '';
      setActiveQuestionText('');
      persistCache(next, '', status);
    };

    const storePartialAnswer = (answer: GeneratedAnswer) => {
      if (!answer) return;
      const prev = answersRef.current;
      let next = prev;
      const byId = answer.question_id
        ? prev.findIndex(a => a.question_id === answer.question_id)
        : -1;
      if (byId >= 0) {
        next = [...prev];
        next[byId] = { ...prev[byId], ...answer };
      } else {
        const key = answer.question_id || `${answer.question}\u0000${answer.answer_en}`;
        seenAnswerKeys.current.add(key);
        next = [answer, ...prev];
      }
      answersRef.current = next;
      setAnswers(next);
      setPhase('generating');
      persistCache(next, activeQuestionRef.current, 'جاري توليد الإجابة...');
    };

    const syncLiveState = async () => {
      if (cancelled) return;
      try {
        const latest = await getSession(session.id);
        setLiveSessionState(latest.state);
        const phase = pipelinePhaseRef.current;

        if (latest.current_answer) {
          const already = answersRef.current.some(
            a => a.question_id && a.question_id === latest.current_answer?.question_id
          );
          if (!already && (phase === 'generating' || phase === 'listening' || phase === 'idle')) {
            storeAnswer(latest.current_answer);
          }
        }

        // Never resurrect an already-answered question into the live strip.
        if (latest.current_question) {
          const norm = normalizeQ(latest.current_question);
          if (norm && norm === lastAnsweredQuestionRef.current) {
            return;
          }
          if (phase === 'dumping' || phase === 'question' || !activeQuestionRef.current) {
            if (norm !== normalizeQ(activeQuestionRef.current)) {
              setQuestionText(latest.current_question);
            }
            if (phase === 'dumping' || phase === 'idle' || phase === 'listening') {
              setPhase('question');
              setStatus('تم تفريغ السؤال، جاري التصنيف...');
            }
          }
        }
      } catch (error) {
        console.warn('Live-state synchronization failed', error);
      }
    };

    liveStateTimer = setInterval(syncLiveState, 1500);
    void syncLiveState();

    const offAnswer = interviewWS.on('ANSWER_READY', (msg: any) => {
      storeAnswer(msg.answer as GeneratedAnswer);
    });

    const offAnswerPartial = interviewWS.on('ANSWER_PARTIAL', (msg: any) => {
      storePartialAnswer(msg.answer as GeneratedAnswer);
    });

    const offQuestionDetected = interviewWS.on('QUESTION_DETECTED', (msg: any) => {
      if (msg.utterance) setQuestionText(msg.utterance);
      setPhase('question');
      setStatus('تم اكتشاف سؤال...');
    });

    const offTranscript = interviewWS.on('TRANSCRIPT_CREATED', (msg: any) => {
      if (msg.speaker === 'interviewer' && msg.text) {
        setQuestionText(msg.text);
        setPhase('question');
        setStatus('تم تفريغ السؤال، جاري التصنيف...');
      }
    });

    const offGenerating = interviewWS.on('ANSWER_GENERATING', () => {
      setPhase('generating');
      setStatus('جاري توليد الإجابة...');
    });

    const offIgnored = interviewWS.on('QUESTION_IGNORED', (msg: any) => {
      setPhase('listening');
      // Do not clear the transcript — show why we skipped answering.
      setStatus(
        msg?.reason
          ? `تم تجاهل المقطع (${msg.reason}) — جاري الاستماع...`
          : 'تم تجاهل المقطع — جاري الاستماع...'
      );
    });

    const offPartial = interviewWS.on('PARTIAL_TRANSCRIPT', (msg: any) => {
      if (msg.speaker && msg.speaker !== 'interviewer') return;
      setPhase('dumping');
      setStatus('المحاور يتحدث...');
    });

    const offFinalized = interviewWS.on('UTTERANCE_FINALIZED', () => {
      setPhase('dumping');
      setStatus('جاري تفريغ السؤال...');
    });

    const offSttRetrying = interviewWS.on('STT_RETRYING', (msg: any) => {
      if (msg.speaker && msg.speaker !== 'interviewer') return;
      setPhase('dumping');
      setStatus(msg.message || 'إعادة محاولة تفريغ السؤال...');
    });

    const offSttTimeout = interviewWS.on('STT_TIMEOUT', (msg: any) => {
      if (msg.speaker !== 'interviewer') return;
      // Soft timeout: keep listening so the next question can still be captured.
      if (activeQuestionRef.current) {
        setPhase('question');
        setStatus('تعذر تفريغ مقطع إضافي — الإبقاء على السؤال الحالي');
        return;
      }
      setPhase('listening');
      setStatus('تعذر التفريغ هذه المرة — تكلم السؤال بوضوح مرة أخرى');
    });

    const applyState = (msg: any) => {
      const nextState = msg.state || msg.new_state;
      if (nextState) setLiveSessionState(nextState);
    };
    const offState = interviewWS.on('STATE_CHANGED', applyState);
    const offLegacyState = interviewWS.on('state_change', applyState);

    let captureReady = false;
    const offCaptureReady = interviewWS.on('AUDIO_CAPTURE_READY', (msg: any) => {
      captureReady = true;
      if (pipelinePhaseRef.current === 'idle' || pipelinePhaseRef.current === 'listening') {
        setStatus(msg.message || 'بانتظار بدأ المقابله');
      }
    });

    const offStreamActive = interviewWS.on('AUDIO_STREAM_ACTIVE', (msg: any) => {
      if (pipelinePhaseRef.current === 'idle' || pipelinePhaseRef.current === 'listening') {
        setPhase('listening');
        setStatus(msg.message || 'بانتظار بدأ المقابله');
      }
    });

    const offCaptureStalled = interviewWS.on('AUDIO_CAPTURE_STALLED', (msg: any) => {
      setStatus(
        msg.message
        || 'تعذر التقاط صوت النظام. اختر جهاز الإخراج الحالي في Windows وتأكد أن صوت الاجتماع يعمل عليه.'
      );
    });

    const offCaptureSilent = interviewWS.on('AUDIO_CAPTURE_SILENT', (msg: any) => {
      if (pipelinePhaseRef.current === 'idle' || pipelinePhaseRef.current === 'listening') {
        setStatus(
          msg.message
          || 'بانتظار بدأ المقابله'
        );
      }
    });

    const offEmpty = interviewWS.on('STT_EMPTY', (msg: any) => {
      if (msg.speaker !== 'interviewer') return;
      // Soft empty must never erase a landed transcript.
      if (activeQuestionRef.current) return;
      if (pipelinePhaseRef.current === 'question' || pipelinePhaseRef.current === 'generating') return;
      setPhase('listening');
      setStatus('لم يُسمع سؤال واضح — جاري الاستماع مجدداً...');
    });

    const offError = interviewWS.on('error', (msg: any) => {
      setStatus(msg.message || 'خطأ في الصوت المباشر');
    });

    const offSpeech = interviewWS.on('SPEECH_DETECTED', (msg: any) => {
      if (msg.speaker && msg.speaker !== 'interviewer') return;
      setPhase('dumping');
      setStatus('المحاور يتحدث...');
    });

    interviewWS.configureAudio(
      audioConfig?.mic,
      audioConfig?.loopback,
      lengthMode,
      langMode,
    );
    interviewWS.startSession();
    interviewWS.connect(session.id).then(() => {
      if (cancelled) return;
      setWsState('connected');
      interviewWS.configureAudio(
        audioConfig?.mic,
        audioConfig?.loopback,
        lengthMode,
        langMode,
      );
      interviewWS.startSession();
      startTimer = setTimeout(() => {
        if (!cancelled && !captureReady) {
          interviewWS.startSession();
        }
      }, 2000);
    }).catch((e) => {
      console.error('WS Connect error', e);
      setWsState('error');
    });

    return () => {
      cancelled = true;
      if (startTimer) clearTimeout(startTimer);
      if (liveStateTimer) clearInterval(liveStateTimer);
      offAnswer();
      offAnswerPartial();
      offQuestionDetected();
      offTranscript();
      offGenerating();
      offIgnored();
      offPartial();
      offFinalized();
      offSttRetrying();
      offSttTimeout();
      offState();
      offLegacyState();
      offCaptureReady();
      offStreamActive();
      offCaptureStalled();
      offCaptureSilent();
      offEmpty();
      offError();
      offSpeech();
      interviewWS.disconnect();
    };
  }, [session.id]);

  const submitManualQuestion = (text: string) => {
    const question = text.trim();
    if (!question) return;
    pipelinePhaseRef.current = 'question';
    activeQuestionRef.current = question;
    setActiveQuestionText(question);
    const status = 'جاري توليد إجابة للسؤال المكتوب...';
    setSessionStatus(status);
    persistCache(answersRef.current, question, status);
    interviewWS.sendUtterance(question, lengthMode, langMode);
  };

  useEffect(() => {
    if (wsState === 'connected') {
      interviewWS.configureAudio(
        audioConfig?.mic,
        audioConfig?.loopback,
        lengthMode,
        langMode,
      );
    }
  }, [lengthMode, langMode, wsState, audioConfig?.mic, audioConfig?.loopback]);

  if (wsState === 'connecting') return <div className="text-center p-8">جاري الاتصال بمحرك صوت المقابلة...</div>;
  if (wsState === 'error') return <div className="text-center p-8 text-red-500">فشل الاتصال بمحرك الصوت.</div>;

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: 'var(--space-6)' }}>
      <SessionView
        session={{ ...session, state: liveSessionState }}
        answers={answers}
        langMode={langMode}
        onLangChange={onLangChange}
        sessionStatus={sessionStatus}
        activeQuestionText={activeQuestionText}
        onManualQuestion={submitManualQuestion}
      />
    </div>
  );
}

// ═══════════════════════════════════════════════════════════════
// COMPONENTS
// ═══════════════════════════════════════════════════════════════

// ── Upload Component ───────────────────────────────────────────
function SetupUpload({ onUpload, loading }: { onUpload: (f: File) => void; loading: boolean }) {
  const [dragActive, setDragActive] = useState(false);
  const [elapsedSeconds, setElapsedSeconds] = useState(0);

  useEffect(() => {
    if (!loading) {
      setElapsedSeconds(0);
      return;
    }

    const startedAt = Date.now();
    const timer = window.setInterval(() => {
      setElapsedSeconds(Math.floor((Date.now() - startedAt) / 1000));
    }, 1000);

    return () => window.clearInterval(timer);
  }, [loading]);

  const loadingMessage = elapsedSeconds < 5
    ? 'جاري رفع الملف وقراءته…'
    : elapsedSeconds < 25
      ? 'جاري استخراج السيرة بالكامل…'
      : 'ما زال الاستخراج يعمل — انتظر حتى يكتمل الملف…';
  const loadingDetail = elapsedSeconds < 5
    ? 'جارٍ رفع الملف وقراءته…'
    : 'لا تغلق الصفحة. يتم استخراج الخبرات والتعليم والمهارات الآن.';

  const handleDrop = (e: React.DragEvent) => {
    e.preventDefault();
    setDragActive(false);
    if (!loading && e.dataTransfer.files[0]) onUpload(e.dataTransfer.files[0]);
  };

  return (
    <section className="setup-hero">
      <div className="setup-hero__copy">
        <img
          className="setup-hero__photo"
          src="/hero-photo.jpg"
          alt="Interview"
        />
        <h2>حوّل خبرتك إلى إجابات واثقة.</h2>
      </div>

      <div className="upload-card upload-card--hero">
        <div className="upload-card__heading">
          <div className="upload-icon" aria-hidden="true">📄</div>
          <div>
            <span>الخطوة الأولى</span>
            <h3>رفع السيرة الذاتية</h3>
          </div>
        </div>
        <div
          className={`upload-zone upload-zone--hero ${dragActive ? 'upload-zone--active' : ''} ${loading ? 'upload-zone--loading' : ''}`}
          onDragOver={(e) => { e.preventDefault(); setDragActive(true); }}
          onDragLeave={() => setDragActive(false)}
          onDrop={handleDrop}
          onClick={() => {
            if (loading) return;
            const input = document.createElement('input');
            input.type = 'file';
            input.accept = '.pdf,.docx,.doc,.txt,.md';
            input.onchange = (e) => {
              const file = (e.target as HTMLInputElement).files?.[0];
              if (file) onUpload(file);
            };
            input.click();
          }}
          aria-disabled={loading}
          aria-busy={loading}
          role="button"
          tabIndex={0}
          onKeyDown={(e) => {
            if (e.key === 'Enter' || e.key === ' ') {
              e.preventDefault();
              (e.currentTarget as HTMLElement).click();
            }
          }}
        >
          <div className="upload-zone__glyph" aria-hidden="true">
            <span className="upload-zone__glyph-cloud">☁</span>
            <span className="upload-zone__glyph-arrow">↑</span>
          </div>
          <div className="upload-zone__text">
            <div className="upload-zone__title">
              {loading ? loadingMessage : 'اسحب الملف هنا أو اضغط للاختيار'}
            </div>
            {!loading && (
              <div className="upload-zone__subtitle">
                PDF · DOCX · DOC · TXT — جاهز للتحليل فوراً
              </div>
            )}
            {loading && (
              <div className="upload-zone__subtitle">
                {loadingDetail} ({elapsedSeconds} ث)
              </div>
            )}
            {loading && (
              <div className="upload-zone__progress">
                <div className="upload-zone__progress-bar" />
              </div>
            )}
          </div>
        </div>
      </div>
    </section>
  );
}

// ── Extraction Review ──────────────────────────────────────────
function ExtractionReview({
  extraction, onVerify, loading,
}: {
  extraction: ProfileExtractionResult;
  onVerify: () => void;
  loading: boolean;
}) {
  const p = extraction.extracted_profile;
  const visibleWarnings = extraction.warnings.filter((warning) => {
    if (warning.includes('جاري إكمال التفاصيل')) return false;
    const legacySkillWarning = warning.match(
      /^Skill '(.+)' listed without supporting project\/employment evidence$/,
    );
    if (!legacySkillWarning) return true;

    const skillName = legacySkillWarning[1].trim().toLocaleLowerCase();
    const skill = p.technical_skills.find(
      (item) => item.name.trim().toLocaleLowerCase() === skillName,
    );
    return !skill || (!skill.evidence.length && skill.confidence < 0.8);
  });

  return (
    <div className="page-stack">
      <div className="section-intro">
        <span className="eyebrow">الخطوة 2 من 3</span>
        <h2>راجع ملفك المستخرج</h2>
        <p className="mb-4">
          يرجى مراجعة المعلومات المستخرجة أدناه. صحّح أي أخطاء قبل التأكيد.
          <strong> تُستخدم فقط البيانات المؤكَّدة أثناء المقابلات.</strong>
        </p>
      </div>

      {visibleWarnings.length > 0 && (
        <div className="notice notice--warning">
          <h4 className="mb-2">تنبيهات</h4>
          <ul style={{ paddingInlineStart: 'var(--space-6)', color: 'var(--color-accent-warning)' }}>
            {visibleWarnings.map((w, i) => <li key={i} className="text-sm mb-1">{w}</li>)}
          </ul>
        </div>
      )}

      {extraction.missing_fields.length > 0 && (
        <div className="notice notice--info">
          <h4 className="mb-2">حقول ناقصة</h4>
          <ul style={{ paddingInlineStart: 'var(--space-6)', color: 'var(--color-accent-info)' }}>
            {extraction.missing_fields.map((f, i) => <li key={i} className="text-sm mb-1">{f}</li>)}
          </ul>
        </div>
      )}

      <div className="glass-card">
        <h3 className="section-title">المعلومات الشخصية</h3>
        <div className="info-grid">
          <InfoField label="الاسم" value={p.personal_profile.full_name} />
          <InfoField label="البريد الإلكتروني" value={p.personal_profile.email} />
          <InfoField label="الهاتف" value={p.personal_profile.phone} />
          <InfoField label="الموقع" value={p.personal_profile.location} />
        </div>
      </div>

      {p.professional_summary.summary && (
        <div className="glass-card">
          <h3 className="section-title">الملخص المهني</h3>
          <p>{p.professional_summary.summary}</p>
        </div>
      )}

      {p.employment_history.length > 0 && (
        <div className="glass-card">
          <h3 className="section-title">الخبرات الوظيفية <span>{p.employment_history.length}</span></h3>
          {p.employment_history.map((emp, i) => (
            <div key={i} style={{ padding: 'var(--space-4)', borderBottom: i < p.employment_history.length - 1 ? '1px solid var(--color-border)' : 'none' }}>
              <div className="flex justify-between items-center mb-2">
                <strong>{emp.title}</strong>
                <span className="badge badge--primary">{emp.company}</span>
              </div>
              <div className="text-xs text-muted mb-2">{emp.start_date} — {emp.end_date || 'حتى الآن'}</div>
              {emp.responsibilities.length > 0 && (
                <ul style={{ paddingInlineStart: 'var(--space-5)' }}>
                  {emp.responsibilities.map((r, j) => (
                    <li key={j} className="text-sm" style={{ color: 'var(--color-text-secondary)' }}>{r}</li>
                  ))}
                </ul>
              )}
              {emp.achievements?.length > 0 && (
                <ul style={{ paddingInlineStart: 'var(--space-5)', marginTop: 'var(--space-2)' }}>
                  {emp.achievements.map((a, j) => (
                    <li key={`ach-${j}`} className="text-sm" style={{ color: 'var(--color-text-secondary)' }}>{a}</li>
                  ))}
                </ul>
              )}
              {emp.technologies?.length > 0 && (
                <div className="flex gap-2 mt-2" style={{ flexWrap: 'wrap' }}>
                  {emp.technologies.map((t, j) => (
                    <span key={j} className="badge badge--info">{t}</span>
                  ))}
                </div>
              )}
            </div>
          ))}
        </div>
      )}

      {p.technical_skills.length > 0 && (
        <div className="glass-card">
          <h3 className="section-title">المهارات التقنية <span>{p.technical_skills.length}</span></h3>
          <div className="flex gap-2" style={{ flexWrap: 'wrap' }}>
            {p.technical_skills.map((skill, i) => (
              <span key={i} className="badge badge--info">{skill.name}</span>
            ))}
          </div>
        </div>
      )}

      {(p.management_skills?.length > 0 || p.soft_skills?.length > 0) && (
        <div className="glass-card">
          <h3 className="section-title">مهارات إضافية</h3>
          <div className="flex gap-2" style={{ flexWrap: 'wrap' }}>
            {(p.management_skills || []).map((skill, i) => (
              <span key={`m-${i}`} className="badge badge--primary">{skill.name}</span>
            ))}
            {(p.soft_skills || []).map((skill, i) => (
              <span key={`s-${i}`} className="badge badge--success">{skill.name}</span>
            ))}
          </div>
        </div>
      )}

      {p.education?.length > 0 && (
        <div className="glass-card">
          <h3 className="section-title">التعليم <span>{p.education.length}</span></h3>
          {p.education.map((edu, i) => (
            <div key={i} className="mb-4">
              <strong>{edu.institution}</strong>
              <div className="text-sm">{[edu.degree, edu.field].filter(Boolean).join(' — ')}</div>
              {edu.graduation_date && <div className="text-xs text-muted">{edu.graduation_date}</div>}
            </div>
          ))}
        </div>
      )}

      {p.projects?.length > 0 && (
        <div className="glass-card">
          <h3 className="section-title">المشاريع <span>{p.projects.length}</span></h3>
          {p.projects.map((project, i) => (
            <div key={i} className="mb-4">
              <strong>{project.name}</strong>
              {project.description && <p className="text-sm mt-2">{project.description}</p>}
              {project.technologies?.length > 0 && (
                <div className="flex gap-2 mt-2" style={{ flexWrap: 'wrap' }}>
                  {project.technologies.map((t, j) => (
                    <span key={j} className="badge badge--info">{t}</span>
                  ))}
                </div>
              )}
            </div>
          ))}
        </div>
      )}

      {p.certifications?.length > 0 && (
        <div className="glass-card">
          <h3 className="section-title">الشهادات <span>{p.certifications.length}</span></h3>
          <div className="flex gap-2" style={{ flexWrap: 'wrap' }}>
            {p.certifications.map((cert, i) => (
              <span key={i} className="badge badge--warning">{cert.name}{cert.issuer ? ` — ${cert.issuer}` : ''}</span>
            ))}
          </div>
        </div>
      )}

      <div className="action-row">
        <button className="btn btn-primary btn-lg" onClick={onVerify} disabled={loading}>
          {loading ? 'جاري التحقق…' : 'تأكيد وحفظ الملف'}
        </button>
      </div>
    </div>
  );
}

function InfoField({ label, value }: { label: string; value?: string }) {
  return (
    <div>
      <div className="input-label">{label}</div>
      <div className="text-sm">{value || <span className="text-muted">غير متوفر</span>}</div>
    </div>
  );
}

// ── Profile Dashboard ──────────────────────────────────────────
function ProfileDashboard({
  profile, onOpenRole, onOpenExpected, onStartSession, loading,
}: {
  profile: CandidateProfile;
  onOpenRole: () => void;
  onOpenExpected: () => void;
  onStartSession: () => void;
  loading: boolean;
}) {
  const activeRole = profile.target_roles.at(-1);

  return (
    <div className="page-stack">
      <div className="glass-card profile-hero">
        <div>
          <h2>{profile.personal_profile.full_name || 'مرشح'}</h2>
          <p className="mt-4">{profile.professional_summary.summary?.slice(0, 200)}</p>
        </div>
      </div>

      {/* Stats grid */}
      <div className="stats-grid">
        <StatCard label="المهارات" value={profile.technical_skills.length} />
        <StatCard label="الخبرات" value={profile.employment_history.length} />
        <StatCard label="المشاريع" value={profile.projects.length} />
        <StatCard label="التعليم" value={profile.education.length} />
        <StatCard label="الشهادات" value={profile.certifications.length} />
      </div>

      <div className="glass-card role-summary">
        <div>
          <h3>{activeRole?.specialization || activeRole?.position || 'لم يُحدد التخصص'}</h3>
          {activeRole?.field && <span className="badge badge--info mt-2">{activeRole.field}</span>}
          {activeRole && <p>ستبقى الإجابات التخصصية ضمن هذا المجال فقط.</p>}
          {!activeRole && <p className="text-muted">اختر التخصص أولاً لتفعيل التدريب المباشر.</p>}
        </div>
        <button className="btn btn-secondary" onClick={onOpenRole}>{activeRole ? 'تغيير التخصص' : 'إضافة تخصص'}</button>
      </div>

      <div className="glass-card role-summary">
        <div>
          <h3>أسئلة متوقعة</h3>
          <p>
            {(profile.expected_questions?.length ?? 0) > 0
              ? `محفوظ ${profile.expected_questions?.length} أسئلة. إذا سُئل سؤال بنفس المعنى تُستخدم إجابتك المكتوبة.`
              : 'اختياري. أضف أسئلة تتوقعها وإجاباتها الجاهزة.'}
          </p>
        </div>
        <button className="btn btn-secondary" onClick={onOpenExpected}>
          {(profile.expected_questions?.length ?? 0) > 0 ? 'تعديل الأسئلة' : 'إضافة أسئلة'}
        </button>
      </div>

      {/* Actions */}
      <div className="action-row action-row--wrap">
        <button
          className="btn btn-primary btn-lg"
          onClick={activeRole ? onStartSession : onOpenRole}
          disabled={loading}
        >
          {activeRole ? 'بدء التدريب المباشر' : 'تحديد التخصص ثم البدء'}
        </button>
      </div>
    </div>
  );
}

function ExpectedQuestionsPage({
  profile, onSave, onSkip, loading,
}: {
  profile: CandidateProfile;
  onSave: (items: ExpectedQuestion[]) => void;
  onSkip: () => void;
  loading: boolean;
}) {
  const [rows, setRows] = useState<ExpectedQuestion[]>(() => {
    const existing = profile.expected_questions ?? [];
    return existing.length > 0 ? existing.map((item) => ({ ...item })) : [{ prompt: '', answer: '' }];
  });

  const updateRow = (index: number, field: 'prompt' | 'answer', value: string) => {
    setRows((prev) => prev.map((row, i) => (i === index ? { ...row, [field]: value } : row)));
  };

  const addRow = () => setRows((prev) => [...prev, { prompt: '', answer: '' }]);
  const removeRow = (index: number) => {
    setRows((prev) => (prev.length <= 1 ? [{ prompt: '', answer: '' }] : prev.filter((_, i) => i !== index)));
  };

  return (
    <div className="animate-fade-in page-stack">
      <div className="section-intro">
        <span className="eyebrow">اختياري</span>
        <h2>أسئلة متوقعة</h2>
        <p>
          اكتب السؤال بالطريقة التي قد يُسأل بها، أو بمعنى قريب. إذا جاء السؤال نفسه أو بمعنى مشابه أثناء المقابلة، تُعرض إجابتك المكتوبة كما هي.
        </p>
      </div>

      {rows.map((row, index) => (
        <div className="glass-card expected-question-card" key={row.id || index}>
          <div className="expected-question-card__head">
            <h3 className="section-title">سؤال {index + 1}</h3>
            <button type="button" className="btn btn-ghost btn-sm" onClick={() => removeRow(index)}>
              حذف
            </button>
          </div>
          <label className="input-label" htmlFor={`expected-prompt-${index}`}>طريقة السؤال</label>
          <input
            id={`expected-prompt-${index}`}
            className="input-field"
            value={row.prompt}
            onChange={(e) => updateRow(index, 'prompt', e.target.value)}
            placeholder="مثال: Tell me about yourself أو عرف عن نفسك"
          />
          <label className="input-label mt-4" htmlFor={`expected-answer-${index}`}>الإجابة الجاهزة</label>
          <textarea
            id={`expected-answer-${index}`}
            className="input-field expected-question-card__answer"
            rows={5}
            value={row.answer}
            onChange={(e) => updateRow(index, 'answer', e.target.value)}
            placeholder="اكتب الإجابة التي تريد قولها حرفياً"
          />
        </div>
      ))}

      <div className="action-row action-row--wrap">
        <button type="button" className="btn btn-secondary" onClick={addRow}>إضافة سؤال</button>
        <button type="button" className="btn btn-primary btn-lg" onClick={() => onSave(rows)} disabled={loading}>
          {loading ? 'جاري الحفظ…' : 'حفظ والمتابعة'}
        </button>
        <button type="button" className="btn btn-ghost" onClick={onSkip} disabled={loading}>
          تخطي
        </button>
      </div>
    </div>
  );
}

function TargetRolePage({
  profile, onSave, loading,
}: {
  profile: CandidateProfile;
  onSave: (data: { field: string; specialization: string }) => void;
  loading: boolean;
}) {
  const activeRole = profile.target_roles.at(-1);
  const previousSpecialization = activeRole?.specialization || activeRole?.position || '';
  const inferredField = activeRole?.field || Object.entries(SPECIALIZATION_OPTIONS)
    .find(([, options]) => options.includes(previousSpecialization))?.[0] || '';
  const [field, setField] = useState(inferredField);
  const existingIsListed = TARGET_SPECIALIZATIONS.includes(previousSpecialization);
  const [specializationChoice, setSpecializationChoice] = useState(
    previousSpecialization
      ? (existingIsListed ? previousSpecialization : OTHER_SPECIALIZATION)
      : '',
  );
  const [customSpecialization, setCustomSpecialization] = useState(
    existingIsListed ? '' : previousSpecialization,
  );
  const specialization = specializationChoice === OTHER_SPECIALIZATION
    ? customSpecialization.trim()
    : specializationChoice;

  const handleSave = () => onSave({ field, specialization });

  return (
    <div className="animate-fade-in page-stack">
      <div className="section-intro section-intro--compact">
        <h2>اختر المجال والتخصص</h2>
      </div>

      <div className="glass-card target-role-form">
        <h3 className="section-title">المجال والتخصص المطلوبان</h3>
        <div className="flex flex-col gap-4">
          <div>
            <label className="input-label" htmlFor="primary-field">المجال الرئيسي *</label>
            <select
              id="primary-field"
              className="input-field"
              value={field}
              onChange={e => setField(e.target.value)}
            >
              <option value="">اختر مجالاً</option>
              {PRIMARY_FIELDS.map(option => <option key={option} value={option}>{option}</option>)}
            </select>
          </div>
          <div>
            <label className="input-label" htmlFor="target-specialization">التخصص المستهدف *</label>
            <select
              id="target-specialization"
              className="input-field"
              value={specializationChoice}
              onChange={e => setSpecializationChoice(e.target.value)}
            >
              <option value="">اختر تخصصاً</option>
              {TARGET_SPECIALIZATIONS.map(option => <option key={option} value={option}>{option}</option>)}
              <option value={OTHER_SPECIALIZATION}>تخصص آخر — غير مدرج</option>
            </select>
            {specializationChoice === OTHER_SPECIALIZATION && (
              <input
                className="input-field mt-2"
                value={customSpecialization}
                onChange={e => setCustomSpecialization(e.target.value)}
                placeholder="أدخل تخصصك"
                aria-label="تخصص مخصص"
                autoFocus
              />
            )}
          </div>
          <div className="action-row">
            <button className="btn btn-primary btn-lg" onClick={handleSave} disabled={loading || !field || specialization.length < 2}>
              {loading ? 'جاري الحفظ…' : activeRole ? 'تحديث التخصص' : 'حفظ التخصص'}
            </button>
          </div>
        </div>
      </div>
    </div>
  );
}

function StatCard({ label, value }: { label: string; value: number }) {
  return (
    <div className="stat-card">
      <div className="stat-card__value">{value}</div>
      <div className="stat-card__label">{label}</div>
    </div>
  );
}

// ── Session View ───────────────────────────────────────────────
function SessionView({
  session, answers, langMode, onLangChange,
  sessionStatus, activeQuestionText, onManualQuestion,
}: {
  session: InterviewSession;
  answers: GeneratedAnswer[];
  langMode: AnswerLanguageMode;
  onLangChange: (m: AnswerLanguageMode) => void;
  sessionStatus?: string;
  activeQuestionText?: string;
  onManualQuestion?: (text: string) => void;
}) {
  const [manualQuestion, setManualQuestion] = useState('');
  const [popupOpen, setPopupOpen] = useState(false);
  const [popupAnswer, setPopupAnswer] = useState<GeneratedAnswer | null>(null);
  const lastPopupKeyRef = useRef<string>('');

  const latestAnswer = answers[0] ?? null;
  const bilingualMode = langMode === 'SHOW_ARABIC_AND_ENGLISH';

  useEffect(() => {
    if (!latestAnswer) return;
    const key = latestAnswer.question_id
      || `${latestAnswer.question}\u0000${latestAnswer.answer_en}`;
    // New/changed answer → show (or refresh) the same popup without closing it.
    if (key !== lastPopupKeyRef.current) {
      lastPopupKeyRef.current = key;
      setPopupAnswer(latestAnswer);
      setPopupOpen(true);
      return;
    }
    // Same question, updated fields (e.g. Arabic filled later) → refresh content.
    setPopupAnswer(latestAnswer);
  }, [latestAnswer]);

  const submitManual = () => {
    if (!onManualQuestion || !manualQuestion.trim()) return;
    onManualQuestion(manualQuestion);
    setManualQuestion('');
  };

  return (
    <div className="animate-fade-in">
      {/* Controls bar */}
      <div className="glass-card session-toolbar mb-6">
        <div className="session-toolbar__inner">
          <div className="session-identity">
            <span className="status-dot status-dot--active" />
            {session.meeting_platform && (
              <span className="text-sm">البرنامج: {session.meeting_platform}</span>
            )}
            <span className="badge badge--info">{session.state}</span>
          </div>
          <div className="session-controls">
            <select className="input-field input-field--compact"
              value={langMode} onChange={e => onLangChange(e.target.value as AnswerLanguageMode)}>
              <option value="SHOW_ARABIC_AND_ENGLISH">عربي + إنجليزي</option>
              <option value="ANSWER_IN_QUESTION_LANGUAGE">حسب لغة السؤال</option>
              <option value="ALWAYS_ENGLISH">إنجليزي</option>
              <option value="ALWAYS_ARABIC">عربي</option>
            </select>
          </div>
        </div>
      </div>

      <div className="live-status mb-6">
        <div className="live-status__main"><span className="status-dot status-dot--active"></span>
        <span>{sessionStatus || 'بانتظار بدأ المقابله'}</span></div>
        {activeQuestionText && (
          <div className="live-status__question">
            <strong>السؤال:</strong> "{activeQuestionText}"
          </div>
        )}
      </div>

      {onManualQuestion && (
        <div className="glass-card manual-question mb-6">
          <label className="input-label" htmlFor="manual-question-input">
            اكتب السؤال يدوياً (إذا لم يُلتقط صوت Zoom)
          </label>
          <div className="manual-question__row">
            <input
              id="manual-question-input"
              className="input-field"
              value={manualQuestion}
              onChange={e => setManualQuestion(e.target.value)}
              onKeyDown={e => {
                if (e.key === 'Enter') {
                  e.preventDefault();
                  submitManual();
                }
              }}
              placeholder="مثال: Tell me about yourself"
            />
            <button
              type="button"
              className="btn btn-primary"
              onClick={submitManual}
              disabled={!manualQuestion.trim()}
            >
              توليد الإجابة
            </button>
          </div>
        </div>
      )}

      <div className="waiting-card">
        <span className="waiting-card__pulse" aria-hidden="true" />
        <h3>{latestAnswer ? 'الإجابة جاهزة في النافذة' : 'بانتظار بدأ المقابله'}</h3>
        <p>
          {latestAnswer
            ? 'الإجابة تظهر في النافذة المنبثقة. السؤال الجديد يستبدل المحتوى دون إغلاقها.'
            : 'عند سماع السؤال ستظهر الإجابة تلقائياً، أو اكتب السؤال يدوياً بالأعلى.'}
        </p>
        {latestAnswer && !popupOpen && (
          <button
            type="button"
            className="btn btn-primary mt-4"
            onClick={() => {
              setPopupAnswer(latestAnswer);
              setPopupOpen(true);
            }}
          >
            عرض الإجابة الحالية
          </button>
        )}
      </div>

      {popupOpen && popupAnswer && (
        <AnswerPopup
          answer={popupAnswer}
          bilingualMode={bilingualMode}
          onClose={() => setPopupOpen(false)}
        />
      )}
    </div>
  );
}

// ── Answer Popup ───────────────────────────────────────────────
function AnswerPopup({
  answer,
  bilingualMode = false,
  onClose,
}: {
  answer: GeneratedAnswer;
  bilingualMode?: boolean;
  onClose: () => void;
}) {
  const waitingForArabic = bilingualMode && !answer.answer_ar?.trim();
  const conf = answer.confidence;

  return (
    <div
      className="answer-popup-overlay"
      role="dialog"
      aria-modal="true"
      aria-labelledby="answer-popup-title"
    >
      <div className="answer-popup">
        <header className="answer-popup__header">
          <div>
            <span className="answer-card__label">السؤال</span>
            <h3 id="answer-popup-title">{answer.question}</h3>
          </div>
          <button
            type="button"
            className="answer-popup__close"
            onClick={onClose}
            aria-label="إغلاق"
          >
            ×
          </button>
        </header>

        <div className="answer-popup__body">
          <div className="teleprompter mb-4" dir="ltr">
            {answer.answer_ar && <div className="answer-card__label mb-2">English</div>}
            <div className="teleprompter__text teleprompter__text--en">
              {answer.answer_en}
            </div>
          </div>

          {answer.answer_ar ? (
            <div className="teleprompter mb-4" dir="rtl">
              <div className="answer-card__label mb-2">العربية</div>
              <div className="teleprompter__text teleprompter__text--ar">
                {answer.answer_ar}
              </div>
            </div>
          ) : waitingForArabic ? (
            <div className="teleprompter mb-4" dir="rtl">
              <div className="answer-card__label mb-2">العربية</div>
              <div className="text-sm" style={{ color: 'var(--color-text-secondary)' }}>
                جاري إعداد الترجمة العربية...
              </div>
            </div>
          ) : null}

          <div className="confidence-grid">
            <ConfidenceMeter label="السؤال" value={conf.question_confidence} />
            <ConfidenceMeter label="السياق" value={conf.context_confidence} />
            <ConfidenceMeter label="الإجابة" value={conf.answer_confidence} />
          </div>
        </div>
      </div>
    </div>
  );
}

// ── Answer Card ────────────────────────────────────────────────
function AnswerCard({
  answer,
  bilingualMode = false,
}: {
  answer: GeneratedAnswer;
  bilingualMode?: boolean;
}) {
  const conf = answer.confidence;
  const waitingForArabic = bilingualMode && !answer.answer_ar?.trim();

  return (
    <article className="glass-card answer-card animate-slide-in">
      {/* Question */}
      <div className="answer-card__header">
        <div><span className="answer-card__label">السؤال</span><h4>{answer.question}</h4></div>
      </div>

      {/* Answer text — teleprompter-like */}
      <div className="teleprompter mb-4" dir="ltr">
        {answer.answer_ar && <div className="answer-card__label mb-2">English</div>}
        <div className="teleprompter__text teleprompter__text--en">
          {answer.answer_en}
        </div>
      </div>

      {/* Arabic answer */}
      {answer.answer_ar ? (
        <div className="teleprompter mb-4" dir="rtl">
          <div className="answer-card__label mb-2">العربية</div>
          <div className="teleprompter__text teleprompter__text--ar">
            {answer.answer_ar}
          </div>
        </div>
      ) : waitingForArabic ? (
        <div className="teleprompter mb-4" dir="rtl">
          <div className="answer-card__label mb-2">العربية</div>
          <div className="text-sm" style={{ color: 'var(--color-text-secondary)' }}>
            جاري إعداد الترجمة العربية...
          </div>
        </div>
      ) : null}

      {/* Confidence meters */}
      <div className="confidence-grid">
        <ConfidenceMeter label="السؤال" value={conf.question_confidence} />
        <ConfidenceMeter label="السياق" value={conf.context_confidence} />
        <ConfidenceMeter label="الإجابة" value={conf.answer_confidence} />
      </div>

      {/* Validation warnings */}
      {!answer.validation.is_valid && (
        <div className="mt-4 p-4" style={{ background: 'rgba(239,68,68,0.1)', borderRadius: 'var(--radius-lg)' }}>
          {answer.validation.hallucination_detected && (
            <div className="text-sm" style={{ color: 'var(--color-accent-danger)' }}>
              ⚠️ تم اكتشاف معلومة غير موثوقة: {answer.validation.hallucinated_claims.join(', ')}
            </div>
          )}
          {answer.validation.missing_context && (
            <div className="text-sm" style={{ color: 'var(--color-accent-warning)' }}>
              📝 {answer.validation.missing_context_details}
            </div>
          )}
        </div>
      )}
    </article>
  );
}

function ConfidenceMeter({ label, value }: { label: string; value: number }) {
  const pct = Math.round(value * 100);
  const level = pct >= 70 ? 'high' : pct >= 40 ? 'medium' : 'low';
  return (
    <div className="confidence-meter">
      <span className="text-xs text-muted" style={{ minWidth: 60 }}>{label}</span>
      <div className="confidence-bar">
        <div className={`confidence-bar__fill confidence-bar__fill--${level}`} style={{ width: `${pct}%` }} />
      </div>
      <span className="text-xs font-mono">{pct}%</span>
    </div>
  );
}

// ── Review View ────────────────────────────────────────────────
function ReviewView({ answers }: { answers: GeneratedAnswer[] }) {
  const avgConf = answers.reduce((sum, a) => sum + a.confidence.answer_confidence, 0) / answers.length;
  const validCount = answers.filter(a => a.validation.is_valid).length;

  return (
    <div className="animate-fade-in page-stack">
      <div className="section-intro section-intro--compact">
        <span className="eyebrow">ملخص التدريب</span>
        <h2>مراجعة الجلسة</h2>
        <p>تمت معالجة {answers.length} أسئلة</p>
      </div>

      <div className="stats-grid stats-grid--three">
        <StatCard label="الأسئلة" value={answers.length} />
        <StatCard label="إجابات صالحة" value={validCount} />
        <StatCard label="متوسط الثقة" value={Math.round(avgConf * 100)} />
      </div>

      {answers.map((answer, i) => (
        <div key={i} className="glass-card">
          <h4 className="mb-2" style={{ color: 'var(--color-accent-secondary)' }}>{answer.question}</h4>
          <p className="text-sm mb-2">{answer.answer_en.slice(0, 200)}...</p>
          <ConfidenceMeter label="الثقة" value={answer.confidence.answer_confidence} />
        </div>
      ))}
    </div>
  );
}
