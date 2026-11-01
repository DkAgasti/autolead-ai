'use client';

import React, { useState } from 'react';
import { Lead } from '@/types';
import {
  X,
  Sparkles,
  Send,
  Calendar,
  Globe,
  Clock,
  ExternalLink,
  Mail,
  CheckCircle,
  AlertCircle,
  MessageSquare,
  FileText,
  ShieldCheck,
  Hash,
  Reply
} from 'lucide-react';
import { analyzeLead, sendLeadNow, scheduleLead, updateLeadDraft, sendReplyFollowup } from '@/lib/api';

interface LeadDetailModalProps {
  lead: Lead | null;
  onClose: () => void;
  onRefresh: () => void;
}

export function LeadDetailModal({ lead, onClose, onRefresh }: LeadDetailModalProps) {
  const [activeTab, setActiveTab] = useState<'pitch' | 'audit' | 'original' | 'thread'>('pitch');
  const [editedSubject, setEditedSubject] = useState(lead?.subject_line || '');
  const [editedBody, setEditedBody] = useState(lead?.email_body || '');
  const [editedEmail, setEditedEmail] = useState(lead?.email || '');
  const [replyText, setReplyText] = useState('');
  const [isSaving, setIsSaving] = useState(false);
  const [isAnalyzing, setIsAnalyzing] = useState(false);
  const [isSending, setIsSending] = useState(false);
  const [statusMsg, setStatusMsg] = useState<{ text: string; success: boolean } | null>(null);

  React.useEffect(() => {
    if (lead) {
      setEditedSubject(lead.subject_line || '');
      setEditedBody(lead.email_body || '');
      setEditedEmail(lead.email || '');
      setStatusMsg(null);
    }
  }, [lead]);

  if (!lead) return null;

  // Parse pain points
  let painPoints: string[] = [];
  try {
    if (lead.pain_points) painPoints = JSON.parse(lead.pain_points);
  } catch (e) {
    painPoints = [];
  }

  const handleSaveDraft = async () => {
    setIsSaving(true);
    setStatusMsg(null);
    try {
      await updateLeadDraft(lead.id, {
        subject_line: editedSubject,
        email_body: editedBody,
        email: editedEmail
      });
      setStatusMsg({ text: 'Draft updated successfully!', success: true });
      onRefresh();
    } catch (err: any) {
      setStatusMsg({ text: 'Failed to update draft', success: false });
    } finally {
      setIsSaving(false);
    }
  };

  const handleAnalyze = async () => {
    setIsAnalyzing(true);
    setStatusMsg(null);
    try {
      const updated = await analyzeLead(lead.id);
      setEditedSubject(updated.subject_line || '');
      setEditedBody(updated.email_body || '');
      setStatusMsg({ text: 'Analyzed with Gemini 2.5 Flash!', success: true });
      onRefresh();
    } catch (err: any) {
      setStatusMsg({ text: 'Analysis failed', success: false });
    } finally {
      setIsAnalyzing(false);
    }
  };

  const handleSendNow = async () => {
    if (!editedEmail) {
      setStatusMsg({ text: 'Recipient email is required for SMTP dispatch.', success: false });
      return;
    }
    setIsSending(true);
    setStatusMsg(null);
    try {
      const res = await sendLeadNow(lead.id, {
        subject: editedSubject,
        body: editedBody,
        recipient_override: editedEmail
      });
      setStatusMsg({ text: `Dispatched via direct SMTP! Message-ID: ${res.message_id || 'ok'}`, success: true });
      onRefresh();
    } catch (err: any) {
      setStatusMsg({ text: err.message || 'SMTP dispatch error', success: false });
    } finally {
      setIsSending(false);
    }
  };

  const handleSchedule = async () => {
    try {
      await scheduleLead(lead.id);
      setStatusMsg({ text: `Queued for recipient timezone (${lead.timezone})!`, success: true });
      onRefresh();
    } catch (err: any) {
      setStatusMsg({ text: 'Scheduling failed', success: false });
    }
  };

  const handleSendReply = async () => {
    if (!replyText.trim()) return;
    try {
      await sendReplyFollowup(lead.id, replyText);
      setReplyText('');
      setStatusMsg({ text: 'Follow-up reply dispatched via SMTP!', success: true });
      onRefresh();
    } catch (err: any) {
      setStatusMsg({ text: err.message || 'Failed to dispatch reply', success: false });
    }
  };

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-black/80 backdrop-blur-sm overflow-y-auto">
      <div className="relative w-full max-w-4xl bg-slate-900 border border-slate-800 rounded-3xl shadow-2xl overflow-hidden my-8">
        {/* Top Header */}
        <div className="flex items-center justify-between px-6 py-4 border-b border-slate-800 bg-slate-950/60">
          <div className="flex items-center space-x-3">
            <span
              className={`px-2 py-0.5 rounded-md text-xs font-bold uppercase ${
                lead.source === 'Reddit'
                  ? 'bg-orange-500/10 text-orange-400'
                  : lead.source === 'LinkedIn'
                  ? 'bg-blue-500/10 text-blue-400'
                  : 'bg-emerald-500/10 text-emerald-400'
              }`}
            >
              {lead.source}
            </span>
            <span className="text-xs text-slate-400 font-mono">Lead #{lead.id}</span>
            <div className="flex items-center space-x-1.5 text-xs text-slate-400">
              <Globe className="w-3.5 h-3.5 text-blue-400" />
              <span>{lead.detected_country}</span>
              <span className="text-slate-600">•</span>
              <Clock className="w-3.5 h-3.5 text-amber-400" />
              <span>{lead.timezone}</span>
            </div>
          </div>

          <button
            onClick={onClose}
            className="p-1 rounded-lg text-slate-400 hover:text-white hover:bg-slate-800 transition"
          >
            <X className="w-5 h-5" />
          </button>
        </div>

        {/* Status notification banner */}
        {statusMsg && (
          <div
            className={`px-6 py-2.5 text-xs font-medium flex items-center space-x-2 border-b ${
              statusMsg.success
                ? 'bg-emerald-950/60 border-emerald-500/30 text-emerald-300'
                : 'bg-rose-950/60 border-rose-500/30 text-rose-300'
            }`}
          >
            {statusMsg.success ? <CheckCircle className="w-4 h-4 text-emerald-400" /> : <AlertCircle className="w-4 h-4 text-rose-400" />}
            <span>{statusMsg.text}</span>
          </div>
        )}

        {/* Modal Body */}
        <div className="p-6 space-y-6 max-h-[75vh] overflow-y-auto">
          {/* Post Header */}
          <div>
            <h2 className="text-lg font-bold text-white">{lead.title}</h2>
            <div className="flex flex-wrap items-center gap-3 mt-2 text-xs text-slate-400">
              <span>Author: <strong className="text-slate-200">@{lead.author_id || 'unknown'}</strong></span>
              {lead.source_url && (
                <a
                  href={lead.source_url}
                  target="_blank"
                  rel="noreferrer"
                  className="flex items-center space-x-1 text-blue-400 hover:underline"
                >
                  <span>Original Link</span>
                  <ExternalLink className="w-3 h-3" />
                </a>
              )}
              {lead.message_id && (
                <span className="flex items-center space-x-1 font-mono text-[11px] text-indigo-400 bg-indigo-950/40 px-2 py-0.5 rounded border border-indigo-800/40">
                  <Hash className="w-3 h-3" />
                  <span className="truncate max-w-[200px]">{lead.message_id}</span>
                </span>
              )}
            </div>
          </div>

          {/* Sub Navigation */}
          <div className="flex space-x-1 border-b border-slate-800 pb-2">
            <button
              onClick={() => setActiveTab('pitch')}
              className={`flex items-center space-x-1.5 px-3 py-1.5 rounded-lg text-xs font-medium ${
                activeTab === 'pitch' ? 'bg-blue-600 text-white' : 'text-slate-400 hover:text-slate-200'
              }`}
            >
              <Mail className="w-3.5 h-3.5" />
              <span>Cold Pitch Draft</span>
            </button>

            <button
              onClick={() => setActiveTab('audit')}
              className={`flex items-center space-x-1.5 px-3 py-1.5 rounded-lg text-xs font-medium ${
                activeTab === 'audit' ? 'bg-blue-600 text-white' : 'text-slate-400 hover:text-slate-200'
              }`}
            >
              <Sparkles className="w-3.5 h-3.5" />
              <span>Technical Audit & Angles</span>
            </button>

            <button
              onClick={() => setActiveTab('original')}
              className={`flex items-center space-x-1.5 px-3 py-1.5 rounded-lg text-xs font-medium ${
                activeTab === 'original' ? 'bg-blue-600 text-white' : 'text-slate-400 hover:text-slate-200'
              }`}
            >
              <FileText className="w-3.5 h-3.5" />
              <span>Original Scraped Text</span>
            </button>

            <button
              onClick={() => setActiveTab('thread')}
              className={`flex items-center space-x-1.5 px-3 py-1.5 rounded-lg text-xs font-medium relative ${
                activeTab === 'thread' ? 'bg-blue-600 text-white' : 'text-slate-400 hover:text-slate-200'
              }`}
            >
              <MessageSquare className="w-3.5 h-3.5" />
              <span>Thread Messages</span>
              {lead.threads && lead.threads.length > 0 && (
                <span className="ml-1 px-1.5 py-0.2 rounded-full text-[10px] bg-emerald-500 text-white">
                  {lead.threads.length}
                </span>
              )}
            </button>
          </div>

          {/* TAB 1: PITCH DRAFT */}
          {activeTab === 'pitch' && (
            <div className="space-y-4">
              <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                <div className="space-y-1">
                  <label className="text-xs font-semibold text-slate-400">Recipient Email (Destination)</label>
                  <input
                    type="email"
                    value={editedEmail}
                    onChange={(e) => setEditedEmail(e.target.value)}
                    placeholder="client@example.com"
                    className="w-full px-3 py-2 text-xs bg-slate-950 rounded-xl border border-slate-800 text-slate-200 font-mono focus:outline-none focus:border-blue-500"
                  />
                </div>

                <div className="space-y-1">
                  <label className="text-xs font-semibold text-slate-400">Delivery Window Status</label>
                  <div className="px-3 py-2 text-xs bg-slate-950 rounded-xl border border-slate-800 text-slate-300 flex items-center justify-between">
                    <span>9:30 AM - 11:00 AM in {lead.timezone}</span>
                    <span className="px-2 py-0.5 rounded text-[10px] font-bold bg-blue-500/20 text-blue-400">
                      {lead.status}
                    </span>
                  </div>
                </div>
              </div>

              <div className="space-y-1">
                <label className="text-xs font-semibold text-slate-400">Subject Line</label>
                <input
                  type="text"
                  value={editedSubject}
                  onChange={(e) => setEditedSubject(e.target.value)}
                  className="w-full px-3 py-2 text-xs font-medium bg-slate-950 rounded-xl border border-slate-800 text-slate-100 focus:outline-none focus:border-blue-500"
                />
              </div>

              <div className="space-y-1">
                <div className="flex justify-between items-center">
                  <label className="text-xs font-semibold text-slate-400">Personalized Body (100-130 Words)</label>
                  <span className="text-[11px] text-slate-500 font-mono">
                    {editedBody.split(/\s+/).filter(Boolean).length} words
                  </span>
                </div>
                <textarea
                  rows={8}
                  value={editedBody}
                  onChange={(e) => setEditedBody(e.target.value)}
                  className="w-full px-3 py-2 text-xs bg-slate-950 rounded-xl border border-slate-800 text-slate-200 focus:outline-none focus:border-blue-500 leading-relaxed font-sans"
                />
              </div>

              <div className="flex flex-wrap items-center justify-between gap-3 pt-2">
                <button
                  onClick={handleSaveDraft}
                  disabled={isSaving}
                  className="px-4 py-2 rounded-xl text-xs font-medium text-slate-300 bg-slate-800 hover:bg-slate-700 transition"
                >
                  {isSaving ? 'Saving...' : 'Save Draft Edits'}
                </button>

                <div className="flex items-center space-x-2">
                  <button
                    onClick={handleSchedule}
                    className="flex items-center space-x-1.5 px-3.5 py-2 rounded-xl text-xs font-semibold text-amber-300 bg-amber-500/10 hover:bg-amber-500/20 border border-amber-500/30 transition"
                  >
                    <Calendar className="w-3.5 h-3.5" />
                    <span>Queue for Timezone</span>
                  </button>

                  <button
                    onClick={handleSendNow}
                    disabled={isSending}
                    className="flex items-center space-x-2 px-5 py-2 rounded-xl text-xs font-bold text-white bg-blue-600 hover:bg-blue-500 transition shadow-lg shadow-blue-500/20 disabled:opacity-50"
                  >
                    <Send className="w-3.5 h-3.5" />
                    <span>{isSending ? 'Sending SMTP...' : 'Send Now (Direct SMTP)'}</span>
                  </button>
                </div>
              </div>
            </div>
          )}

          {/* TAB 2: AUDIT & CRITIQUES */}
          {activeTab === 'audit' && (
            <div className="space-y-4">
              <div className="p-4 rounded-2xl bg-purple-950/20 border border-purple-800/30 space-y-3">
                <div className="flex items-center justify-between">
                  <div className="flex items-center space-x-2 text-purple-300 font-bold text-xs">
                    <Sparkles className="w-4 h-4 text-purple-400" />
                    <span>Gemini 2.5 Flash Technical Angle</span>
                  </div>
                  <button
                    onClick={handleAnalyze}
                    disabled={isAnalyzing}
                    className="text-xs text-purple-300 hover:text-white underline disabled:opacity-50"
                  >
                    {isAnalyzing ? 'Re-analyzing...' : 'Re-run Analysis'}
                  </button>
                </div>
                <p className="text-xs text-purple-200 leading-relaxed">
                  {lead.audit_summary || 'Analysis pending.'}
                </p>
              </div>

              {painPoints.length > 0 && (
                <div className="space-y-2">
                  <h4 className="text-xs font-semibold uppercase text-slate-400">Identified Client Pain Points</h4>
                  <ul className="space-y-1.5 text-xs text-slate-300">
                    {painPoints.map((pt, i) => (
                      <li key={i} className="flex items-center space-x-2">
                        <span className="w-1.5 h-1.5 rounded-full bg-blue-400" />
                        <span>{pt}</span>
                      </li>
                    ))}
                  </ul>
                </div>
              )}

              {lead.website_url && (
                <div className="p-3 rounded-xl bg-slate-950 border border-slate-800 text-xs">
                  <span className="text-slate-400">Audited Website Target: </span>
                  <a href={lead.website_url} target="_blank" rel="noreferrer" className="text-blue-400 underline">
                    {lead.website_url}
                  </a>
                </div>
              )}
            </div>
          )}

          {/* TAB 3: ORIGINAL POST */}
          {activeTab === 'original' && (
            <div className="p-4 rounded-2xl bg-slate-950 border border-slate-800 text-xs text-slate-300 leading-relaxed whitespace-pre-wrap font-mono">
              {lead.raw_text}
            </div>
          )}

          {/* TAB 4: EMAIL THREAD MESSAGES */}
          {activeTab === 'thread' && (
            <div className="space-y-4">
              <div className="space-y-3">
                {(!lead.threads || lead.threads.length === 0) ? (
                  <p className="text-xs text-slate-500 py-4 text-center">
                    No emails sent or received yet for this lead.
                  </p>
                ) : (
                  lead.threads.map((msg) => (
                    <div
                      key={msg.id}
                      className={`p-4 rounded-2xl border text-xs space-y-2 ${
                        msg.direction === 'OUTBOUND'
                          ? 'bg-blue-950/20 border-blue-800/40 ml-6'
                          : 'bg-emerald-950/20 border-emerald-800/40 mr-6'
                      }`}
                    >
                      <div className="flex items-center justify-between">
                        <div className="flex items-center space-x-2">
                          <span
                            className={`px-1.5 py-0.5 rounded text-[10px] font-bold ${
                              msg.direction === 'OUTBOUND'
                                ? 'bg-blue-500/20 text-blue-400'
                                : 'bg-emerald-500/20 text-emerald-400'
                            }`}
                          >
                            {msg.direction}
                          </span>
                          <span className="font-semibold text-slate-200">{msg.sender}</span>
                          {msg.sentiment && (
                            <span className="px-2 py-0.5 rounded-full text-[10px] font-bold bg-purple-500/20 text-purple-300">
                              Sentiment: {msg.sentiment}
                            </span>
                          )}
                        </div>
                        <span className="text-slate-500 font-mono text-[11px]">
                          {new Date(msg.created_at).toLocaleString()}
                        </span>
                      </div>

                      <div className="font-medium text-slate-300">Subject: {msg.subject}</div>
                      <div className="text-slate-300 whitespace-pre-wrap leading-relaxed bg-slate-950/60 p-3 rounded-xl border border-slate-850">
                        {msg.body_text}
                      </div>

                      {msg.auto_reply_draft && (
                        <div className="mt-2 p-3 rounded-xl bg-purple-950/30 border border-purple-800/40 space-y-1.5">
                          <span className="text-[11px] font-bold text-purple-300 flex items-center">
                            <Sparkles className="w-3 h-3 mr-1" />
                            Gemini AI Auto-Reply Draft:
                          </span>
                          <p className="text-xs text-purple-200 whitespace-pre-wrap">
                            {msg.auto_reply_draft}
                          </p>
                        </div>
                      )}
                    </div>
                  ))
                )}
              </div>

              {/* Reply Box */}
              <div className="p-4 rounded-2xl bg-slate-950 border border-slate-800 space-y-2">
                <label className="text-xs font-semibold text-slate-300 flex items-center space-x-1.5">
                  <Reply className="w-3.5 h-3.5 text-blue-400" />
                  <span>Send Follow-up / Direct Reply (Native SMTP)</span>
                </label>
                <textarea
                  rows={4}
                  value={replyText}
                  onChange={(e) => setReplyText(e.target.value)}
                  placeholder="Type your follow-up reply..."
                  className="w-full p-2.5 text-xs bg-slate-900 rounded-xl border border-slate-800 text-slate-200 focus:outline-none focus:border-blue-500"
                />
                <div className="flex justify-end">
                  <button
                    onClick={handleSendReply}
                    disabled={!replyText.trim()}
                    className="flex items-center space-x-1.5 px-4 py-2 rounded-xl text-xs font-bold text-white bg-blue-600 hover:bg-blue-500 disabled:opacity-40"
                  >
                    <Send className="w-3.5 h-3.5" />
                    <span>Send Reply via SMTP</span>
                  </button>
                </div>
              </div>
            </div>
          )}
        </div>
      </div>
    </div>
  );
}

