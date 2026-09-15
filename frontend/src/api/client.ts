/**
 * AI Interview Coach — REST API Client
 */

import type { ProfileExtractionResult } from '../types';

// Use same-origin /api and let Vite proxy to the FastAPI backend.
// This avoids CORS failures when the UI runs on any Vite port (5173/5175/…).
const API_BASE = '/api';

async function request<T>(
  path: string,
  options: RequestInit = {},
  retries = 2,
): Promise<T> {
  const url = `${API_BASE}${path}`;
  let lastError: unknown;

  for (let attempt = 0; attempt <= retries; attempt++) {
    try {
      const response = await fetch(url, {
        headers: {
          'Content-Type': 'application/json',
          ...options.headers,
        },
        ...options,
      });

      if (!response.ok) {
        const error = await response.json().catch(() => ({ detail: response.statusText }));
        const detail = error.detail || response.statusText || `Request failed: ${response.status}`;
        // Retry transient proxy/backend restarts (502/503/504).
        if ([502, 503, 504].includes(response.status) && attempt < retries) {
          await new Promise(r => setTimeout(r, 600 * (attempt + 1)));
          continue;
        }
        if (response.status === 502) {
          throw new Error('تعذر الوصول للخادم (Bad Gateway). أعد المحاولة بعد لحظات.');
        }
        throw new Error(typeof detail === 'string' ? detail : JSON.stringify(detail));
      }

      return response.json();
    } catch (error) {
      lastError = error;
      if (error instanceof TypeError && attempt < retries) {
        await new Promise(r => setTimeout(r, 600 * (attempt + 1)));
        continue;
      }
      if (error instanceof TypeError) {
        throw new Error('تعذر الاتصال بالخادم. تأكد أن الـ backend يعمل على المنفذ 8000.');
      }
      throw error;
    }
  }

  throw lastError instanceof Error ? lastError : new Error('Request failed');
}

// ── Candidate API ──────────────────────────────────────────────

export async function uploadCV(file: File) {
  const formData = new FormData();
  formData.append('file', file);

  const controller = new AbortController();
  const timeout = window.setTimeout(() => controller.abort(), 180_000);

  try {
    let lastError: unknown;
    for (let attempt = 0; attempt <= 2; attempt++) {
      const response = await fetch(`${API_BASE}/candidates/upload-cv`, {
        method: 'POST',
        body: formData,
        signal: controller.signal,
      });

      if (!response.ok) {
        const error = await response.json().catch(() => ({ detail: response.statusText }));
        const detail = error.detail || response.statusText || 'Upload failed';
        if ([502, 503, 504].includes(response.status) && attempt < 2) {
          await new Promise(r => setTimeout(r, 800 * (attempt + 1)));
          continue;
        }
        if (response.status === 502) {
          throw new Error('تعذر الوصول للخادم (Bad Gateway). أعد المحاولة بعد لحظات.');
        }
        const message = Array.isArray(detail)
          ? detail.map((item) => item?.msg || JSON.stringify(item)).join(' | ')
          : (typeof detail === 'string' ? detail : JSON.stringify(detail));
        throw new Error(message || `Upload failed (${response.status})`);
      }

      const result = await response.json();
      if (!result?.extracted_profile) {
        throw new Error('The server returned an invalid profile. Please try again.');
      }
      return result;
    }
    throw lastError instanceof Error ? lastError : new Error('Upload failed');
  } catch (error) {
    if (error instanceof DOMException && error.name === 'AbortError') {
      throw new Error('استغرق استخراج السيرة وقتاً طويلاً. جرّب ملف أصغر أو بصيغة DOCX/TXT.');
    }
    if (error instanceof TypeError) {
      throw new Error('تعذر الاتصال بالخادم. تأكد أن الـ backend يعمل على المنفذ 8000.');
    }
    throw error;
  } finally {
    window.clearTimeout(timeout);
  }
}

export async function getCVEnrichment(jobId: string) {
  return request<{
    status: 'running' | 'complete' | 'failed';
    result?: ProfileExtractionResult;
    error?: string;
  }>(`/candidates/cv-enrichment/${jobId}`);
}

export async function verifyProfile(profile: unknown) {
  return request('/candidates/verify-profile', {
    method: 'POST',
    body: JSON.stringify(profile),
  });
}

export async function addTargetRole(profileId: string, roleData: unknown) {
  return request(`/candidates/profiles/${profileId}/target-role`, {
    method: 'POST',
    body: JSON.stringify(roleData),
  });
}

export async function saveExpectedQuestions(
  profileId: string,
  items: { id?: string; prompt: string; answer: string }[],
) {
  return request(`/candidates/profiles/${profileId}/expected-questions`, {
    method: 'POST',
    body: JSON.stringify({ items }),
  });
}

// ── Interview API ──────────────────────────────────────────────

export async function createSession(data: {
  candidate_id: string;
  mode?: string;
  target_role_id?: string;
  meeting_platform?: string;
}) {
  return request('/interviews/sessions', {
    method: 'POST',
    body: JSON.stringify(data),
  });
}

export async function getSession(sessionId: string) {
  return request<import('../types').InterviewSession>(`/interviews/sessions/${sessionId}`);
}
