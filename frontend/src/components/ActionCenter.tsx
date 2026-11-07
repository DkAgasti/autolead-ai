'use client';

import React, { useState } from 'react';
import { Lead } from '@/types';
import {
  Sparkles,
  Send,
  Calendar,
  Trash2,
  Edit3,
  ExternalLink,
  Clock,
  Globe,
  AlertCircle,
  CheckCircle,
  RefreshCw,
  Mail,
  Zap
} from 'lucide-react';
import { sendLeadNow, scheduleLead, discardLead, updateLeadDraft, bulkAnalyzeRaw, dispatchQueueNow } from '@/lib/api';

interface ActionCenterProps {
  leads: Lead[];
  onRefresh: () => void;
  onOpenLead: (lead: Lead) => void;
}

export function ActionCenter({ leads, onRefresh, onOpenLead }: ActionCenterProps) {
  // Focus on leads that are ANALYZED (ready for review) or RAW (ready for analysis)
  const pendingReviewLeads = leads.filter((l) => l.status === 'ANALYZED');
  const rawLeads = leads.filter((l) => l.status === 'RAW');

  const [activeLeadIndex, setActiveLeadIndex] = useState(0);
  const [isEditing, setIsEditing] = useState(false);
  const [editedSubject, setEditedSubject] = useState('');
  const [editedBody, setEditedBody] = useState('');
  const [editedEmail, setEditedEmail] = useState('');
  const [isSending, setIsSending] = useState(false);
  const [isBulkAnalyzing, setIsBulkAnalyzing] = useState(false);
  const [isDispatchingQueue, setIsDispatchingQueue] = useState(false);
  const [actionMessage, setActionMessage] = useState<{ text: string; type: 'success' | 'error' } | null>(null);

  const currentLead = pendingReviewLeads[activeLeadIndex] || null;

  // Initialize draft inputs when active lead changes
  React.useEffect(() => {
    if (currentLead) {
      setEditedSubject(currentLead.subject_line || '');
      setEditedBody(currentLead.email_body || '');
      setEditedEmail(currentLead.email || '');
      setIsEditing(false);
    }
  }, [currentLead]);

  const handleSendNow = async () => {
    if (!currentLead) return;
    setIsSending(true);
    setActionMessage(null);
    try {
      const res = await sendLeadNow(currentLead.id, {
        subject: editedSubject,
        body: editedBody,
        recipient_override: editedEmail
      });
      setActionMessage({ text: `Dispatched via SMTP to ${editedEmail || currentLead.email}!`, type: 'success' });
      setTimeout(() => {
        setActionMessage(null);
        onRefresh();
      }, 1500);
    } catch (err: any) {
      setActionMessage({ text: err.message || 'SMTP Dispatch failed', type: 'error' });
    } finally {
      setIsSending(false);
    }
  };

  const handleScheduleTimezone = async () => {
    if (!currentLead) return;
    try {
      // First save draft if changed
      await updateLeadDraft(currentLead.id, {
        subject_line: editedSubject,
        email_body: editedBody,
        email: editedEmail
      });
      await scheduleLead(currentLead.id);
      setActionMessage({
        text: `Queued for ${currentLead.timezone} (9:30 AM - 11:00 AM local delivery window)`,
        type: 'success'
      });
      setTimeout(() => {
        setActionMessage(null);
        onRefresh();
      }, 1500);
    } catch (err: any) {
      setActionMessage({ text: err.message || 'Scheduling failed', type: 'error' });
    }
  };

  const handleDiscard = async () => {
    if (!currentLead) return;
    try {
      await discardLead(currentLead.id);
      onRefresh();
    } catch (err: any) {
      alert('Failed to discard lead');
    }
  };

  const handleBulkAnalyze = async () => {
    setIsBulkAnalyzing(true);
    try {
      const res = await bulkAnalyzeRaw();
      setActionMessage({ text: `Analyzed ${res.analyzed_count} raw leads with Gemini 2.5 Flash!`, type: 'success' });
      onRefresh();
    } catch (err: any) {
      setActionMessage({ text: 'Bulk analysis failed', type: 'error' });
    } finally {
      setIsBulkAnalyzing(false);
    }
  };

  const handleDispatchQueue = async () => {
    setIsDispatchingQueue(true);
    try {
      const res = await dispatchQueueNow();
      setActionMessage({ text: res.message || 'Auto-dispatch queue started in background!', type: 'success' });
      setTimeout(() => {
        onRefresh();
      }, 2000);
    } catch (err: any) {
      setActionMessage({ text: err.message || 'Dispatch queue failed', type: 'error' });
    } finally {
      setIsDispatchingQueue(false);
    }
  };

  if (pendingReviewLeads.length === 0) {
    return (
      <div className="rounded-2xl bg-slate-900/60 border border-slate-800 p-12 text-center max-w-2xl mx-auto space-y-4">
        <div className="w-16 h-16 rounded-2xl bg-purple-500/10 border border-purple-500/20 text-purple-400 flex items-center justify-center mx-auto">
          <Sparkles className="w-8 h-8" />
        </div>
        <h3 className="text-xl font-bold text-white">Action Center Clear</h3>
        <p className="text-sm text-slate-400">
          There are currently no pitches awaiting approval. You have {rawLeads.length} raw harvested leads ready for Gemini 2.5 Flash analysis.
        </p>
        {rawLeads.length > 0 && (
          <button
            onClick={handleBulkAnalyze}
            disabled={isBulkAnalyzing}
            className="inline-flex items-center space-x-2 px-5 py-2.5 rounded-xl bg-purple-600 hover:bg-purple-500 text-white font-medium text-sm transition shadow-lg shadow-purple-500/20"
          >
            <RefreshCw className={`w-4 h-4 ${isBulkAnalyzing ? 'animate-spin' : ''}`} />
            <span>Analyze {rawLeads.length} Raw Leads Now</span>
          </button>
        )}
      </div>
    );
  }

  // Parse pain points
  let parsedPainPoints: string[] = [];
  try {
    if (currentLead.pain_points) {
      parsedPainPoints = JSON.parse(currentLead.pain_points);
    }
  } catch (e) {
    parsedPainPoints = [];
  }

  return (
    <div className="space-y-6">
      {/* Action Center Header Bar */}
      <div className="flex flex-col sm:flex-row justify-between items-start sm:items-center gap-4 bg-slate-900/60 border border-slate-800 p-4 rounded-2xl backdrop-blur-sm">
        <div>
          <div className="flex items-center space-x-2">
            <span className="flex h-2 w-2 rounded-full bg-purple-400" />
            <h2 className="text-base font-bold text-white">1-Click Outreach Review</h2>
            <span className="px-2 py-0.5 rounded-full text-xs font-semibold bg-purple-500/20 text-purple-300 border border-purple-500/30">
              {pendingReviewLeads.length} Pending Approval
            </span>
          </div>
          <p className="text-xs text-slate-400 mt-0.5">
            Review personalized Gemini 2.5 Flash pitches before native SMTP delivery
          </p>
        </div>

        <div className="flex items-center space-x-2">
          {pendingReviewLeads.length > 0 && (
            <button
              onClick={handleDispatchQueue}
              disabled={isDispatchingQueue}
              className="flex items-center space-x-1.5 px-3 py-1.5 rounded-lg text-xs font-semibold bg-gradient-to-r from-blue-600 to-indigo-600 hover:from-blue-500 hover:to-indigo-500 text-white shadow-md shadow-blue-500/20 transition disabled:opacity-50"
              title="Automatically dispatch all analyzed leads via direct Gmail SMTP"
            >
              <Send className={`w-3.5 h-3.5 ${isDispatchingQueue ? 'animate-bounce' : ''}`} />
              <span>{isDispatchingQueue ? 'Dispatching...' : `Auto-Send All (${pendingReviewLeads.length})`}</span>
            </button>
          )}

          {rawLeads.length > 0 && (
            <button
              onClick={handleBulkAnalyze}
              disabled={isBulkAnalyzing}
              className="flex items-center space-x-1 px-3 py-1.5 rounded-lg text-xs bg-slate-800 hover:bg-slate-700 text-slate-200 border border-slate-700 transition"
            >
              <Zap className="w-3.5 h-3.5 text-amber-400" />
              <span>Analyze {rawLeads.length} Raw Leads</span>
            </button>
          )}

          {/* Lead Navigator */}
          <div className="flex items-center space-x-1 bg-slate-950 px-2 py-1 rounded-xl border border-slate-800">
            <button
              onClick={() => setActiveLeadIndex((i) => Math.max(0, i - 1))}
              disabled={activeLeadIndex === 0}
              className="px-2 py-1 text-xs text-slate-400 hover:text-white disabled:opacity-30"
            >
              Prev
            </button>
            <span className="text-xs font-mono text-slate-300 px-1">
              {activeLeadIndex + 1} / {pendingReviewLeads.length}
            </span>
            <button
              onClick={() => setActiveLeadIndex((i) => Math.min(pendingReviewLeads.length - 1, i + 1))}
              disabled={activeLeadIndex >= pendingReviewLeads.length - 1}
              className="px-2 py-1 text-xs text-slate-400 hover:text-white disabled:opacity-30"
            >
              Next
            </button>
          </div>
        </div>
      </div>

      {actionMessage && (
        <div
          className={`p-3 rounded-xl border text-xs font-medium flex items-center space-x-2 ${
            actionMessage.type === 'success'
              ? 'bg-emerald-950/60 border-emerald-500/40 text-emerald-300'
              : 'bg-rose-950/60 border-rose-500/40 text-rose-300'
          }`}
        >
          {actionMessage.type === 'success' ? (
            <CheckCircle className="w-4 h-4 text-emerald-400" />
          ) : (
            <AlertCircle className="w-4 h-4 text-rose-400" />
          )}
          <span>{actionMessage.text}</span>
        </div>
      )}

      {/* Main Review Card */}
      <div className="grid grid-cols-1 lg:grid-cols-12 gap-6">
        {/* Left Column: Client Post Context & Technical Audit (5 Cols) */}
        <div className="lg:col-span-5 space-y-4">
          <div className="rounded-2xl bg-slate-900/60 border border-slate-800 p-5 space-y-4">
            <div className="flex items-center justify-between">
              <span className="px-2.5 py-1 rounded-md text-xs font-bold uppercase bg-slate-800 text-slate-300">
                {currentLead.source}
              </span>
              <div className="flex items-center space-x-1.5 text-xs text-slate-400">
                <Globe className="w-3.5 h-3.5 text-blue-400" />
                <span>{currentLead.detected_country}</span>
                <span className="text-slate-600">•</span>
                <Clock className="w-3.5 h-3.5 text-amber-400" />
                <span>{currentLead.timezone}</span>
              </div>
            </div>

            <div>
              <h3 className="text-sm font-bold text-white line-clamp-2">{currentLead.title}</h3>
              <p className="text-xs text-slate-400 mt-1">Author: {currentLead.author_id || 'Client'}</p>
            </div>

            <div className="p-3 rounded-xl bg-slate-950/80 border border-slate-850 text-xs text-slate-300 max-h-48 overflow-y-auto leading-relaxed">
              {currentLead.raw_text}
            </div>

            {/* Audit / Commercial Benefit Summary */}
            <div className="p-3.5 rounded-xl bg-purple-950/30 border border-purple-800/40 space-y-2">
              <div className="flex items-center space-x-1.5 text-purple-300 font-semibold text-xs">
                <Sparkles className="w-3.5 h-3.5 text-purple-400" />
                <span>Gemini Technical Audit & Angle</span>
              </div>
              <p className="text-xs text-purple-200/90 leading-relaxed">
                {currentLead.audit_summary || 'No audit summary generated.'}
              </p>
            </div>

            {/* Deliverables / Pain Points */}
            {parsedPainPoints.length > 0 && (
              <div className="space-y-1.5">
                <span className="text-[11px] font-semibold text-slate-400 uppercase tracking-wider">
                  Target Deliverables
                </span>
                <div className="flex flex-wrap gap-1.5">
                  {parsedPainPoints.map((pt, i) => (
                    <span
                      key={i}
                      className="px-2 py-0.5 rounded-md text-[11px] font-medium bg-slate-800 text-slate-300 border border-slate-700/50"
                    >
                      {pt}
                    </span>
                  ))}
                </div>
              </div>
            )}

            {currentLead.website_url && (
              <a
                href={currentLead.website_url}
                target="_blank"
                rel="noreferrer"
                className="inline-flex items-center text-xs text-blue-400 hover:text-blue-300 space-x-1"
              >
                <span>Audit Target: {currentLead.website_url}</span>
                <ExternalLink className="w-3 h-3" />
              </a>
            )}
          </div>
        </div>

        {/* Right Column: Cold Pitch Draft & Instant Dispatch Actions (7 Cols) */}
        <div className="lg:col-span-7 space-y-4">
          <div className="rounded-2xl bg-slate-900/60 border border-slate-800 p-5 space-y-4">
            <div className="flex items-center justify-between">
              <div className="flex items-center space-x-2">
                <Mail className="w-4 h-4 text-blue-400" />
                <h3 className="text-sm font-bold text-white">Generated Cold Pitch (100-130 Words)</h3>
              </div>
              <button
                onClick={() => setIsEditing(!isEditing)}
                className="flex items-center space-x-1 text-xs text-slate-400 hover:text-blue-400 transition"
              >
                <Edit3 className="w-3.5 h-3.5" />
                <span>{isEditing ? 'Editing Mode' : 'Edit Pitch'}</span>
              </button>
            </div>

            {/* Recipient Email Input */}
            <div className="space-y-1">
              <label className="text-[11px] font-semibold uppercase text-slate-400">
                Recipient Email (Direct SMTP Destination)
              </label>
              <input
                type="email"
                value={editedEmail}
                onChange={(e) => setEditedEmail(e.target.value)}
                placeholder="client@company.com"
                className="w-full px-3 py-2 text-xs bg-slate-950 rounded-xl border border-slate-800 text-slate-200 focus:outline-none focus:border-blue-500 font-mono"
              />
            </div>

            {/* Subject Line */}
            <div className="space-y-1">
              <label className="text-[11px] font-semibold uppercase text-slate-400">Subject Line</label>
              <input
                type="text"
                value={editedSubject}
                onChange={(e) => setEditedSubject(e.target.value)}
                className="w-full px-3 py-2 text-xs font-medium bg-slate-950 rounded-xl border border-slate-800 text-slate-100 focus:outline-none focus:border-blue-500"
              />
            </div>

            {/* Email Body */}
            <div className="space-y-1">
              <div className="flex justify-between items-center">
                <label className="text-[11px] font-semibold uppercase text-slate-400">Email Pitch</label>
                <span className="text-[10px] text-slate-500 font-mono">
                  {editedBody.split(/\s+/).filter(Boolean).length} words (Target: 100-130)
                </span>
              </div>
              <textarea
                rows={9}
                value={editedBody}
                onChange={(e) => setEditedBody(e.target.value)}
                className="w-full px-3 py-2.5 text-xs bg-slate-950 rounded-xl border border-slate-800 text-slate-200 focus:outline-none focus:border-blue-500 leading-relaxed font-sans"
              />
            </div>

            {/* 1-Click Action Buttons */}
            <div className="pt-2 flex flex-wrap items-center justify-between gap-3 border-t border-slate-800">
              <button
                onClick={handleDiscard}
                className="flex items-center space-x-1.5 px-3 py-2 rounded-xl text-xs font-semibold text-rose-400 hover:bg-rose-500/10 border border-rose-500/20 transition"
              >
                <Trash2 className="w-3.5 h-3.5" />
                <span>Discard</span>
              </button>

              <div className="flex items-center space-x-2">
                <button
                  onClick={handleScheduleTimezone}
                  className="flex items-center space-x-1.5 px-3.5 py-2 rounded-xl text-xs font-semibold text-amber-300 bg-amber-500/10 hover:bg-amber-500/20 border border-amber-500/30 transition"
                  title="Queue to dispatch at 9:30 AM - 11:00 AM recipient local time"
                >
                  <Calendar className="w-3.5 h-3.5" />
                  <span>Queue for Timezone</span>
                </button>

                <button
                  onClick={handleSendNow}
                  disabled={isSending}
                  className="flex items-center space-x-2 px-5 py-2 rounded-xl text-xs font-bold text-white bg-gradient-to-r from-blue-600 to-indigo-600 hover:from-blue-500 hover:to-indigo-500 shadow-md shadow-blue-500/20 transition disabled:opacity-50"
                >
                  <Send className={`w-3.5 h-3.5 ${isSending ? 'animate-bounce' : ''}`} />
                  <span>{isSending ? 'Sending via SMTP...' : 'Approve & Send Now'}</span>
                </button>
              </div>
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}

