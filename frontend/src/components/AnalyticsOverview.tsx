'use client';

import React, { useState, useEffect } from 'react';
import { AnalyticsData } from '@/types';
import { fetchDailyReport, triggerSendWhatsAppReport, DailyReportSummary } from '@/lib/api';
import {
  Compass,
  CheckCircle2,
  Send,
  MessageSquareReply,
  Activity,
  Layers,
  Sparkles,
  ArrowUpRight,
  Clock,
  Check,
  AlertTriangle,
  MessageSquare,
  Copy,
  ExternalLink
} from 'lucide-react';

interface AnalyticsOverviewProps {
  analytics: AnalyticsData | null;
  onSelectStatusFilter: (status: string) => void;
  onQuickAction: () => void;
}

export function AnalyticsOverview({
  analytics,
  onSelectStatusFilter,
  onQuickAction
}: AnalyticsOverviewProps) {
  const [dailyReport, setDailyReport] = useState<DailyReportSummary | null>(null);
  const [isSendingWhatsApp, setIsSendingWhatsApp] = useState(false);
  const [copied, setCopied] = useState(false);
  const [reportFeedback, setReportFeedback] = useState<string | null>(null);

  useEffect(() => {
    fetchDailyReport().then(setDailyReport).catch(() => {});
  }, [analytics]);

  const handleSendWhatsApp = async () => {
    setIsSendingWhatsApp(true);
    setReportFeedback(null);
    try {
      const res = await triggerSendWhatsAppReport();
      setReportFeedback(res.message);
      if (res.metrics) setDailyReport(res.metrics);
    } catch (e: any) {
      setReportFeedback(e.message || 'Failed to dispatch report');
    } finally {
      setIsSendingWhatsApp(false);
    }
  };

  const handleCopyReport = () => {
    if (!dailyReport) return;
    navigator.clipboard.writeText(dailyReport.formatted_message);
    setCopied(true);
    setTimeout(() => setCopied(false), 2000);
  };

  if (!analytics) {
    return (
      <div className="grid grid-cols-1 md:grid-cols-4 gap-4 animate-pulse">
        {[...Array(4)].map((_, i) => (
          <div key={i} className="h-28 bg-slate-900/60 rounded-xl border border-slate-800" />
        ))}
      </div>
    );
  }

  const kpis = [
    {
      title: 'Scraped Today',
      value: analytics.scraped_today,
      subtitle: `${analytics.total_leads} total harvested`,
      icon: Compass,
      color: 'from-blue-500/20 to-cyan-500/10',
      iconColor: 'text-blue-400',
      borderColor: 'border-blue-500/20',
      filter: 'ALL'
    },
    {
      title: 'Valid Leads',
      value: analytics.valid_leads,
      subtitle: 'Intent verified by Gemini 2.5 Flash',
      icon: CheckCircle2,
      color: 'from-purple-500/20 to-indigo-500/10',
      iconColor: 'text-purple-400',
      borderColor: 'border-purple-500/20',
      filter: 'ANALYZED'
    },
    {
      title: 'Dispatched via SMTP',
      value: analytics.emails_dispatched,
      subtitle: 'Native TLS/SSL (No 3rd party APIs)',
      icon: Send,
      color: 'from-indigo-500/20 to-blue-500/10',
      iconColor: 'text-indigo-400',
      borderColor: 'border-indigo-500/20',
      filter: 'SENT'
    },
    {
      title: 'Reply Rate',
      value: `${analytics.reply_rate}%`,
      subtitle: `${analytics.replies_received} replies via IMAP listener`,
      icon: MessageSquareReply,
      color: 'from-emerald-500/20 to-teal-500/10',
      iconColor: 'text-emerald-400',
      borderColor: 'border-emerald-500/20',
      filter: 'REPLIED'
    }
  ];

  const statusMap = [
    { key: 'RAW', label: 'Raw Harvested', count: analytics.status_counts['RAW'] || 0, color: 'bg-slate-700 text-slate-300' },
    { key: 'ANALYZED', label: 'Analyzed & Drafted', count: analytics.status_counts['ANALYZED'] || 0, color: 'bg-purple-900/50 text-purple-300 border border-purple-700/50' },
    { key: 'SCHEDULED', label: 'Timezone Queued', count: analytics.status_counts['SCHEDULED'] || 0, color: 'bg-amber-900/50 text-amber-300 border border-amber-700/50' },
    { key: 'SENT', label: 'Sent via SMTP', count: analytics.status_counts['SENT'] || 0, color: 'bg-blue-900/50 text-blue-300 border border-blue-700/50' },
    { key: 'REPLIED', label: 'Client Replied', count: analytics.status_counts['REPLIED'] || 0, color: 'bg-emerald-900/50 text-emerald-300 border border-emerald-700/50' },
    { key: 'BOUNCED', label: 'Bounced / Invalid', count: analytics.status_counts['BOUNCED'] || 0, color: 'bg-red-950/60 text-red-400 border border-red-800/50' },
    { key: 'NEEDS_EMAIL', label: 'No Email Found', count: analytics.status_counts['NEEDS_EMAIL'] || 0, color: 'bg-zinc-800 text-zinc-400 border border-zinc-700' },
    { key: 'FILTERED_OUT', label: 'Filtered Out', count: analytics.status_counts['FILTERED_OUT'] || 0, color: 'bg-rose-900/40 text-rose-300 border border-rose-800/40' },
  ];

  return (
    <div className="space-y-6">
      {/* KPI Cards */}
      <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4">
        {kpis.map((kpi, idx) => {
          const Icon = kpi.icon;
          return (
            <div
              key={idx}
              onClick={() => onSelectStatusFilter(kpi.filter)}
              className={`relative overflow-hidden rounded-2xl bg-gradient-to-br ${kpi.color} bg-slate-900/60 p-5 border ${kpi.borderColor} shadow-lg backdrop-blur-sm cursor-pointer hover:scale-[1.02] transition-transform`}
            >
              <div className="flex items-center justify-between">
                <span className="text-xs font-semibold uppercase tracking-wider text-slate-400">
                  {kpi.title}
                </span>
                <div className={`p-2 rounded-xl bg-slate-900/80 border border-slate-800 ${kpi.iconColor}`}>
                  <Icon className="w-4 h-4" />
                </div>
              </div>

              <div className="mt-4 flex items-baseline justify-between">
                <span className="text-3xl font-extrabold text-white tracking-tight">
                  {kpi.value}
                </span>
                <span className="text-[11px] text-slate-400 font-medium flex items-center">
                  View <ArrowUpRight className="w-3 h-3 ml-0.5" />
                </span>
              </div>

              <p className="mt-1 text-xs text-slate-400">{kpi.subtitle}</p>
            </div>
          );
        })}
      </div>

      {/* Pipeline Status Breakdown Bar */}
      <div className="rounded-2xl bg-slate-900/60 border border-slate-800 p-5 backdrop-blur-sm shadow-sm">
        <div className="flex items-center justify-between mb-4">
          <div className="flex items-center space-x-2">
            <Layers className="w-4 h-4 text-blue-400" />
            <h3 className="text-sm font-semibold text-slate-200">Outreach Pipeline Stages</h3>
          </div>
          <span className="text-xs text-slate-400">Click any stage to filter pipeline</span>
        </div>

        <div className="grid grid-cols-2 sm:grid-cols-3 lg:grid-cols-6 gap-3">
          {statusMap.map((st) => (
            <button
              key={st.key}
              onClick={() => onSelectStatusFilter(st.key)}
              className={`p-3 rounded-xl flex flex-col items-start transition hover:border-blue-500/50 ${st.color}`}
            >
              <span className="text-xs opacity-80">{st.label}</span>
              <span className="text-xl font-bold mt-1">{st.count}</span>
            </button>
          ))}
        </div>
      </div>

      {/* WhatsApp Daily Digest Card */}
      {dailyReport && (
        <div className="rounded-2xl bg-gradient-to-r from-emerald-950/40 via-slate-900/60 to-slate-900/60 border border-emerald-500/30 p-5 backdrop-blur-sm shadow-sm">
          <div className="flex flex-col sm:flex-row items-start sm:items-center justify-between gap-4 mb-4 pb-3 border-b border-slate-800/80">
            <div className="flex items-center space-x-3">
              <div className="w-10 h-10 rounded-xl bg-emerald-500/20 border border-emerald-500/30 text-emerald-400 flex items-center justify-center">
                <MessageSquare className="w-5 h-5" />
              </div>
              <div>
                <div className="flex items-center space-x-2">
                  <h3 className="text-sm font-bold text-white">Daily WhatsApp Outreach Digest</h3>
                  <span className="px-2 py-0.5 rounded-full text-[10px] font-semibold bg-emerald-500/20 text-emerald-300 border border-emerald-500/30 font-mono">
                    {dailyReport.target_phone}
                  </span>
                </div>
                <p className="text-xs text-slate-400 mt-0.5">
                  Automated summary of daily harvested leads, AI validity, sent pitches & replies.
                </p>
              </div>
            </div>

            <div className="flex items-center space-x-2 w-full sm:w-auto">
              <button
                onClick={handleCopyReport}
                className="px-3 py-1.5 rounded-lg bg-slate-800 hover:bg-slate-700 text-slate-300 text-xs font-medium transition flex items-center space-x-1.5"
                title="Copy formatted message"
              >
                {copied ? <Check className="w-3.5 h-3.5 text-emerald-400" /> : <Copy className="w-3.5 h-3.5" />}
                <span>{copied ? 'Copied' : 'Copy'}</span>
              </button>
              
              <a
                href={dailyReport.whatsapp_direct_url}
                target="_blank"
                rel="noopener noreferrer"
                className="px-3.5 py-1.5 rounded-lg bg-emerald-600 hover:bg-emerald-500 text-white text-xs font-medium transition flex items-center space-x-1.5 shadow-sm shadow-emerald-500/20"
              >
                <ExternalLink className="w-3.5 h-3.5" />
                <span>Open in WhatsApp</span>
              </a>

              <button
                onClick={handleSendWhatsApp}
                disabled={isSendingWhatsApp}
                className="px-3.5 py-1.5 rounded-lg bg-slate-800 hover:bg-slate-700 border border-slate-700 text-emerald-400 text-xs font-medium transition flex items-center space-x-1.5"
              >
                <Send className={`w-3.5 h-3.5 ${isSendingWhatsApp ? 'animate-pulse' : ''}`} />
                <span>{isSendingWhatsApp ? 'Sending...' : 'Auto-Dispatch'}</span>
              </button>
            </div>
          </div>

          <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
            {/* Live Message Preview Box */}
            <div className="bg-slate-950/70 border border-slate-800/80 rounded-xl p-3.5 font-mono text-xs text-slate-300 whitespace-pre-line leading-relaxed shadow-inner">
              {dailyReport.formatted_message}
            </div>

            {/* Quick Metrics Breakdown & Delivery Info */}
            <div className="space-y-2 text-xs">
              <div className="grid grid-cols-2 gap-2">
                <div className="p-2.5 rounded-lg bg-slate-950/40 border border-slate-800/60">
                  <span className="text-slate-400 block text-[11px]">Total Harvested</span>
                  <span className="text-sm font-bold text-white mt-0.5 block">{dailyReport.total_leads} leads</span>
                </div>
                <div className="p-2.5 rounded-lg bg-slate-950/40 border border-slate-800/60">
                  <span className="text-emerald-400 block text-[11px]">Valid (Hiring)</span>
                  <span className="text-sm font-bold text-white mt-0.5 block">{dailyReport.valid_leads} leads</span>
                </div>
                <div className="p-2.5 rounded-lg bg-slate-950/40 border border-slate-800/60">
                  <span className="text-blue-400 block text-[11px]">Emails Dispatched</span>
                  <span className="text-sm font-bold text-white mt-0.5 block">{dailyReport.message_send_to_user} sent</span>
                </div>
                <div className="p-2.5 rounded-lg bg-slate-950/40 border border-slate-800/60">
                  <span className="text-purple-400 block text-[11px]">Client Replies</span>
                  <span className="text-sm font-bold text-white mt-0.5 block">{dailyReport.reply_back_by_user} received</span>
                </div>
              </div>

              {reportFeedback && (
                <div className="p-2 rounded-lg bg-emerald-500/10 border border-emerald-500/20 text-emerald-300 text-[11px] font-mono">
                  {reportFeedback}
                </div>
              )}
            </div>
          </div>
        </div>
      )}

      {/* 2 Column: Sources & Live Activity Feed */}
      <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
        {/* Source Distribution */}
        <div className="rounded-2xl bg-slate-900/60 border border-slate-800 p-5 backdrop-blur-sm">
          <div className="flex items-center justify-between mb-4">
            <h3 className="text-sm font-semibold text-slate-200 flex items-center space-x-2">
              <Compass className="w-4 h-4 text-purple-400 mr-2" />
              Lead Channels
            </h3>
            <span className="text-xs text-slate-400">Daily 10:00 AM IST</span>
          </div>

          <div className="space-y-3">
            {Object.entries(analytics.source_counts || {}).map(([source, count]) => {
              const total = analytics.total_leads || 1;
              const pct = Math.round((count / total) * 100);
              return (
                <div key={source} className="p-3 rounded-xl bg-slate-950/60 border border-slate-850">
                  <div className="flex justify-between items-center text-xs mb-1.5">
                    <span className="font-medium text-slate-300">{source}</span>
                    <span className="text-slate-400 font-mono">
                      {count} leads ({pct}%)
                    </span>
                  </div>
                  <div className="w-full bg-slate-800 rounded-full h-1.5 overflow-hidden">
                    <div
                      className={`h-1.5 rounded-full ${
                        source === 'Reddit'
                          ? 'bg-orange-500'
                          : source === 'LinkedIn'
                          ? 'bg-blue-500'
                          : 'bg-emerald-500'
                      }`}
                      style={{ width: `${pct}%` }}
                    />
                  </div>
                </div>
              );
            })}
          </div>
        </div>

        {/* Live System Operational Log */}
        <div className="lg:col-span-2 rounded-2xl bg-slate-900/60 border border-slate-800 p-5 backdrop-blur-sm">
          <div className="flex items-center justify-between mb-4">
            <h3 className="text-sm font-semibold text-slate-200 flex items-center">
              <Activity className="w-4 h-4 text-emerald-400 mr-2" />
              Operational Activity Feed
            </h3>
            <span className="text-xs text-emerald-400 font-mono flex items-center">
              <span className="w-2 h-2 rounded-full bg-emerald-400 mr-1.5 animate-pulse" />
              Live Background Services
            </span>
          </div>

          <div className="space-y-2 max-h-64 overflow-y-auto pr-1">
            {analytics.recent_activity.length === 0 ? (
              <p className="text-xs text-slate-500 py-4 text-center">No recent logs recorded yet.</p>
            ) : (
              analytics.recent_activity.map((log) => (
                <div
                  key={log.id}
                  className="flex items-start justify-between p-2.5 rounded-lg bg-slate-950/40 border border-slate-800/60 text-xs font-mono"
                >
                  <div className="flex items-start space-x-2">
                    <span
                      className={`px-1.5 py-0.5 rounded text-[10px] font-bold ${
                        log.module === 'SMTP'
                          ? 'bg-blue-500/20 text-blue-400'
                          : log.module === 'IMAP'
                          ? 'bg-emerald-500/20 text-emerald-400'
                          : log.module === 'GEMINI'
                          ? 'bg-purple-500/20 text-purple-400'
                          : 'bg-slate-700 text-slate-300'
                      }`}
                    >
                      {log.module}
                    </span>
                    <span className="text-slate-300 break-words">{log.message}</span>
                  </div>
                  <span className="text-slate-500 text-[11px] whitespace-nowrap ml-2">
                    {log.time}
                  </span>
                </div>
              ))
            )}
          </div>
        </div>
      </div>
    </div>
  );
}

