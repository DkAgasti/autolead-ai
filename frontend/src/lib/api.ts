import { Lead, AnalyticsData, AppSettings } from '@/types';

const API_BASE = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000';

export async function fetchAnalytics(): Promise<AnalyticsData> {
  const res = await fetch(`${API_BASE}/api/analytics`, { cache: 'no-store' });
  if (!res.ok) throw new Error('Failed to fetch analytics');
  return res.json();
}

export async function fetchLeads(params?: {
  status?: string;
  source?: string;
  country?: string;
  search?: string;
  limit?: number;
}): Promise<Lead[]> {
  const query = new URLSearchParams();
  if (params?.status && params.status !== 'ALL') query.append('status', params.status);
  if (params?.source && params.source !== 'ALL') query.append('source', params.source);
  if (params?.country && params.country !== 'ALL') query.append('country', params.country);
  if (params?.search) query.append('search', params.search);
  if (params?.limit) query.append('limit', params.limit.toString());

  const url = `${API_BASE}/api/leads?${query.toString()}`;
  const res = await fetch(url, { cache: 'no-store' });
  if (!res.ok) throw new Error('Failed to fetch leads');
  return res.json();
}

export async function fetchLeadDetail(id: number): Promise<Lead> {
  const res = await fetch(`${API_BASE}/api/leads/${id}`, { cache: 'no-store' });
  if (!res.ok) throw new Error('Failed to fetch lead');
  return res.json();
}

export async function analyzeLead(id: number): Promise<Lead> {
  const res = await fetch(`${API_BASE}/api/leads/${id}/analyze`, { method: 'POST' });
  if (!res.ok) throw new Error('Failed to analyze lead');
  return res.json();
}

export async function bulkAnalyzeRaw(): Promise<{ status: string; analyzed_count: number }> {
  const res = await fetch(`${API_BASE}/api/leads/analyze-all-raw`, { method: 'POST' });
  if (!res.ok) throw new Error('Failed to bulk analyze');
  return res.json();
}

export async function scheduleLead(id: number): Promise<Lead> {
  const res = await fetch(`${API_BASE}/api/leads/${id}/schedule`, { method: 'POST' });
  if (!res.ok) throw new Error('Failed to schedule lead');
  return res.json();
}

export async function sendLeadNow(
  id: number,
  data?: { subject?: string; body?: string; recipient_override?: string }
): Promise<{ status: string; message: string; message_id?: string; lead: Lead }> {
  const res = await fetch(`${API_BASE}/api/leads/${id}/send-now`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(data || {})
  });
  if (!res.ok) {
    const err = await res.json().catch(() => ({ detail: 'Failed to send pitch' }));
    throw new Error(err.detail || 'Failed to send pitch');
  }
  return res.json();
}

export async function discardLead(id: number): Promise<Lead> {
  const res = await fetch(`${API_BASE}/api/leads/${id}/discard`, { method: 'POST' });
  if (!res.ok) throw new Error('Failed to discard lead');
  return res.json();
}

export async function updateLeadDraft(
  id: number,
  data: { subject_line?: string; email_body?: string; email?: string }
): Promise<Lead> {
  const res = await fetch(`${API_BASE}/api/leads/${id}`, {
    method: 'PATCH',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(data)
  });
  if (!res.ok) throw new Error('Failed to update lead');
  return res.json();
}

export async function sendReplyFollowup(
  id: number,
  replyBody: string,
  subject?: string
): Promise<{ status: string; message_id?: string }> {
  const res = await fetch(`${API_BASE}/api/leads/${id}/reply`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ reply_body: replyBody, subject })
  });
  if (!res.ok) {
    const err = await res.json().catch(() => ({ detail: 'Failed to send reply' }));
    throw new Error(err.detail || 'Failed to send reply');
  }
  return res.json();
}

export async function fetchSettings(): Promise<AppSettings> {
  const res = await fetch(`${API_BASE}/api/settings`, { cache: 'no-store' });
  if (!res.ok) throw new Error('Failed to fetch settings');
  return res.json();
}

export async function updateSettings(data: AppSettings): Promise<{ status: string; message: string }> {
  const res = await fetch(`${API_BASE}/api/settings`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(data)
  });
  if (!res.ok) throw new Error('Failed to update settings');
  return res.json();
}

export async function testSmtp(): Promise<{ success: boolean; message: string }> {
  const res = await fetch(`${API_BASE}/api/settings/test-smtp`, { method: 'POST' });
  return res.json();
}

export async function testImap(): Promise<{ success: boolean; message: string }> {
  const res = await fetch(`${API_BASE}/api/settings/test-imap`, { method: 'POST' });
  return res.json();
}

export async function triggerHarvest(): Promise<{ status: string; added: number; skipped: number }> {
  const res = await fetch(`${API_BASE}/api/system/harvest-now`, { method: 'POST' });
  if (!res.ok) throw new Error('Harvester trigger failed');
  return res.json();
}

export async function triggerPollImap(): Promise<{ status: string; matched_replies: number }> {
  const res = await fetch(`${API_BASE}/api/system/poll-imap-now`, { method: 'POST' });
  if (!res.ok) throw new Error('IMAP poll trigger failed');
  return res.json();
}

export async function triggerQueueDispatch(): Promise<{ status: string; message: string }> {
  const res = await fetch(`${API_BASE}/api/system/dispatch-queue-now`, { method: 'POST' });
  if (!res.ok) throw new Error('Queue dispatch failed');
  return res.json();
}
