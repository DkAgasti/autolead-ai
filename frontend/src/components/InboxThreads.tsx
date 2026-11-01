'use client';

import React, { useState } from 'react';
import { Lead, EmailThread } from '@/types';
import {
  Inbox,
  Sparkles,
  Send,
  MessageSquare,
  CheckCircle2,
  Clock,
  User,
  Mail,
  ExternalLink,
  ThumbsUp,
  Calendar,
  AlertCircle
} from 'lucide-react';
import { sendReplyFollowup } from '@/lib/api';

interface InboxThreadsProps {
  leads: Lead[];
  onRefresh: () => void;
  onOpenLead: (lead: Lead) => void;
}

export function InboxThreads({ leads, onRefresh, onOpenLead }: InboxThreadsProps) {
  // Aggregate all inbound threads from leads
  const inboundItems: { lead: Lead; thread: EmailThread }[] = [];
  leads.forEach((lead) => {
    if (lead.threads) {
      lead.threads.forEach((t) => {
        if (t.direction === 'INBOUND') {
          inboundItems.push({ lead, thread: t });
        }
      });
    }
  });

  // Sort by thread creation date desc
  inboundItems.sort(
    (a, b) => new Date(b.thread.created_at).getTime() - new Date(a.thread.created_at).getTime()
  );

  const [activeItem, setActiveItem] = useState<{ lead: Lead; thread: EmailThread } | null>(
    inboundItems[0] || null
  );
  const [draftReply, setDraftReply] = useState('');
  const [isSending, setIsSending] = useState(false);
  const [sentNotice, setSentNotice] = useState<string | null>(null);

  // Update draft text when active item changes
  React.useEffect(() => {
    if (activeItem) {
      setDraftReply(activeItem.thread.auto_reply_draft || '');
      setSentNotice(null);
    }
  }, [activeItem]);

  const handleApproveSend = async () => {
    if (!activeItem || !draftReply.trim()) return;
    setIsSending(true);
    try {
      await sendReplyFollowup(activeItem.lead.id, draftReply);
      setSentNotice('Follow-up response dispatched via direct SMTP!');
      setTimeout(() => {
        onRefresh();
      }, 1200);
    } catch (err: any) {
      alert(err.message || 'Failed to dispatch reply');
    } finally {
      setIsSending(false);
    }
  };

  const getSentimentBadge = (sentiment?: string | null) => {
    switch (sentiment) {
      case 'INTERESTED':
        return 'bg-emerald-500/20 text-emerald-300 border-emerald-500/30';
      case 'SCHEDULING':
        return 'bg-blue-500/20 text-blue-300 border-blue-500/30';
      case 'OBJECTION':
        return 'bg-amber-500/20 text-amber-300 border-amber-500/30';
      case 'NOT_INTERESTED':
        return 'bg-rose-500/20 text-rose-300 border-rose-500/30';
      default:
        return 'bg-slate-700 text-slate-300 border-slate-600';
    }
  };

  if (inboundItems.length === 0) {
    return (
      <div className="rounded-2xl bg-slate-900/60 border border-slate-800 p-12 text-center max-w-xl mx-auto space-y-4">
        <div className="w-16 h-16 rounded-2xl bg-emerald-500/10 border border-emerald-500/20 text-emerald-400 flex items-center justify-center mx-auto">
          <Inbox className="w-8 h-8" />
        </div>
        <h3 className="text-xl font-bold text-white">No Client Replies Yet</h3>
        <p className="text-sm text-slate-400">
          The native IMAP listener is polling your Gmail INBOX (Port 993 SSL) every 2 minutes. When a client replies to your outreach, it will appear here automatically with Gemini sentiment classification.
        </p>
      </div>
    );
  }

  return (
    <div className="space-y-4">
      <div className="flex items-center justify-between bg-slate-900/60 border border-slate-800 p-4 rounded-2xl">
        <div className="flex items-center space-x-2">
          <Inbox className="w-4 h-4 text-emerald-400" />
          <h2 className="text-sm font-bold text-white">IMAP Inbound Listener & Auto-Reply Agent</h2>
          <span className="px-2 py-0.5 rounded-full text-xs font-bold bg-emerald-500/20 text-emerald-300 border border-emerald-500/30">
            {inboundItems.length} Replies Detected
          </span>
        </div>
        <span className="text-xs text-slate-400 hidden sm:block">
          Matches RFC 2822 In-Reply-To and client email addresses
        </span>
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-12 gap-6">
        {/* Left Column: List of Detected Replies (5 Cols) */}
        <div className="lg:col-span-5 space-y-2">
          {inboundItems.map(({ lead, thread }) => {
            const isSelected = activeItem?.thread.id === thread.id;
            return (
              <div
                key={thread.id}
                onClick={() => setActiveItem({ lead, thread })}
                className={`p-4 rounded-2xl border transition cursor-pointer space-y-2 ${
                  isSelected
                    ? 'bg-slate-850 border-blue-500/50 shadow-md'
                    : 'bg-slate-900/60 border-slate-800 hover:border-slate-700'
                }`}
              >
                <div className="flex items-center justify-between text-xs">
                  <span className="font-semibold text-slate-200 truncate max-w-[180px]">
                    {thread.sender}
                  </span>
                  <span
                    className={`px-2 py-0.5 rounded-full text-[10px] font-bold border ${getSentimentBadge(
                      thread.sentiment
                    )}`}
                  >
                    {thread.sentiment || 'NEUTRAL'}
                  </span>
                </div>

                <div className="text-xs font-medium text-slate-300 truncate">
                  {thread.subject}
                </div>

                <p className="text-xs text-slate-400 line-clamp-2">
                  {thread.body_text}
                </p>

                <div className="flex items-center justify-between text-[11px] text-slate-500 pt-1 border-t border-slate-800/80">
                  <span>Lead #{lead.id} ({lead.title.substring(0, 20)}...)</span>
                  <span>{new Date(thread.created_at).toLocaleDateString()}</span>
                </div>
              </div>
            );
          })}
        </div>

        {/* Right Column: Inbound Message Detail & AI Auto-Reply Draft (7 Cols) */}
        {activeItem && (
          <div className="lg:col-span-7 space-y-4">
            <div className="rounded-2xl bg-slate-900/60 border border-slate-800 p-5 space-y-4">
              {/* Header */}
              <div className="flex items-center justify-between pb-3 border-b border-slate-800">
                <div>
                  <h3 className="text-sm font-bold text-white">{activeItem.thread.subject}</h3>
                  <p className="text-xs text-slate-400 mt-0.5">
                    From: <span className="font-mono text-slate-200">{activeItem.thread.sender}</span>
                  </p>
                </div>
                <span
                  className={`px-2.5 py-1 rounded-full text-xs font-bold border ${getSentimentBadge(
                    activeItem.thread.sentiment
                  )}`}
                >
                  {activeItem.thread.sentiment}
                </span>
              </div>

              {/* Inbound Email Body */}
              <div className="space-y-1">
                <label className="text-[11px] font-semibold uppercase text-slate-400">
                  Client Response Body (IMAP Port 993)
                </label>
                <div className="p-3.5 rounded-xl bg-slate-950 border border-slate-800 text-xs text-slate-200 whitespace-pre-wrap leading-relaxed max-h-48 overflow-y-auto">
                  {activeItem.thread.body_text}
                </div>
              </div>

              {/* Gemini Drafted Reply */}
              <div className="space-y-2 pt-2">
                <div className="flex items-center justify-between">
                  <div className="flex items-center space-x-1.5 text-xs font-bold text-purple-300">
                    <Sparkles className="w-3.5 h-3.5 text-purple-400" />
                    <span>Gemini 2.5 Flash Drafted Reply</span>
                  </div>
                  <span className="text-[10px] text-slate-400">
                    Includes calendar proposals & Calendly link
                  </span>
                </div>

                <textarea
                  rows={7}
                  value={draftReply}
                  onChange={(e) => setDraftReply(e.target.value)}
                  className="w-full p-3 text-xs bg-slate-950 rounded-xl border border-slate-800 text-slate-200 focus:outline-none focus:border-blue-500 leading-relaxed"
                />
              </div>

              {sentNotice && (
                <div className="p-2.5 rounded-xl bg-emerald-950/60 border border-emerald-500/30 text-xs text-emerald-300 flex items-center space-x-2">
                  <CheckCircle2 className="w-4 h-4 text-emerald-400" />
                  <span>{sentNotice}</span>
                </div>
              )}

              {/* Actions */}
              <div className="flex items-center justify-between pt-2 border-t border-slate-800">
                <button
                  onClick={() => onOpenLead(activeItem.lead)}
                  className="text-xs text-blue-400 hover:text-blue-300 flex items-center space-x-1"
                >
                  <span>Open Full Lead Context</span>
                  <ExternalLink className="w-3 h-3" />
                </button>

                <button
                  onClick={handleApproveSend}
                  disabled={isSending || !draftReply.trim()}
                  className="flex items-center space-x-2 px-5 py-2 rounded-xl text-xs font-bold text-white bg-emerald-600 hover:bg-emerald-500 shadow-md shadow-emerald-500/20 transition disabled:opacity-50"
                >
                  <Send className="w-3.5 h-3.5" />
                  <span>{isSending ? 'Dispatching...' : 'Approve & Send Follow-up'}</span>
                </button>
              </div>
            </div>
          </div>
        )}
      </div>
    </div>
  );
}

