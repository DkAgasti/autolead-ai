'use client';

import React, { useState } from 'react';
import { Lead, LeadStatus } from '@/types';
import {
  Table,
  Kanban,
  Search,
  Filter,
  Sparkles,
  Send,
  Eye,
  Globe,
  Clock,
  ExternalLink,
  ChevronRight,
  Trash2,
  Calendar
} from 'lucide-react';
import { analyzeLead, sendLeadNow, scheduleLead, discardLead } from '@/lib/api';

interface LeadsPipelineProps {
  leads: Lead[];
  currentStatusFilter: string;
  setStatusFilter: (st: string) => void;
  onOpenLead: (lead: Lead) => void;
  onRefresh: () => void;
}

const STATUS_COLUMNS: { key: LeadStatus; label: string; badge: string }[] = [
  { key: 'RAW', label: 'Raw Harvested', badge: 'bg-slate-800 text-slate-300 border-slate-700' },
  { key: 'ANALYZED', label: 'Analyzed & Drafted', badge: 'bg-purple-900/40 text-purple-300 border-purple-700/50' },
  { key: 'SCHEDULED', label: 'Timezone Queued', badge: 'bg-amber-900/40 text-amber-300 border-amber-700/50' },
  { key: 'SENT', label: 'Dispatched via SMTP', badge: 'bg-blue-900/40 text-blue-300 border-blue-700/50' },
  { key: 'REPLIED', label: 'Replied by Client', badge: 'bg-emerald-900/40 text-emerald-300 border-emerald-700/50' },
  { key: 'FILTERED_OUT', label: 'Filtered Out', badge: 'bg-rose-900/40 text-rose-300 border-rose-800/40' },
];

export function LeadsPipeline({
  leads,
  currentStatusFilter,
  setStatusFilter,
  onOpenLead,
  onRefresh
}: LeadsPipelineProps) {
  const [viewMode, setViewMode] = useState<'kanban' | 'table'>('kanban');
  const [sourceFilter, setSourceFilter] = useState<string>('ALL');
  const [searchQuery, setSearchQuery] = useState<string>('');
  const [analyzingId, setAnalyzingId] = useState<number | null>(null);

  // Filter leads
  const filteredLeads = leads.filter((lead) => {
    if (currentStatusFilter !== 'ALL' && lead.status !== currentStatusFilter) return false;
    if (sourceFilter !== 'ALL' && lead.source !== sourceFilter) return false;
    if (searchQuery) {
      const q = searchQuery.toLowerCase();
      const matchTitle = lead.title.toLowerCase().includes(q);
      const matchText = lead.raw_text.toLowerCase().includes(q);
      const matchEmail = (lead.email || '').toLowerCase().includes(q);
      const matchAuthor = (lead.author_id || '').toLowerCase().includes(q);
      if (!matchTitle && !matchText && !matchEmail && !matchAuthor) return false;
    }
    return true;
  });

  const handleAnalyze = async (id: number) => {
    setAnalyzingId(id);
    try {
      await analyzeLead(id);
      onRefresh();
    } catch (err) {
      alert('Analysis failed');
    } finally {
      setAnalyzingId(null);
    }
  };

  const handleSendNow = async (lead: Lead) => {
    if (!lead.email) {
      alert('Please set recipient email first.');
      onOpenLead(lead);
      return;
    }
    try {
      await sendLeadNow(lead.id);
      alert(`Dispatched email via direct SMTP to ${lead.email}!`);
      onRefresh();
    } catch (err: any) {
      alert(err.message || 'SMTP dispatch failed');
    }
  };

  const handleSchedule = async (id: number) => {
    try {
      await scheduleLead(id);
      onRefresh();
    } catch (err) {
      alert('Failed to schedule lead');
    }
  };

  const handleDiscard = async (id: number) => {
    try {
      await discardLead(id);
      onRefresh();
    } catch (err) {
      alert('Failed to discard lead');
    }
  };

  const getStatusBadge = (status: string) => {
    const col = STATUS_COLUMNS.find((c) => c.key === status);
    return col ? col.badge : 'bg-slate-800 text-slate-300';
  };

  return (
    <div className="space-y-4">
      {/* Filters and Controls */}
      <div className="flex flex-col md:flex-row justify-between items-start md:items-center gap-3 bg-slate-900/60 border border-slate-800 p-4 rounded-2xl backdrop-blur-sm">
        {/* Search */}
        <div className="relative w-full md:w-72">
          <Search className="w-4 h-4 absolute left-3 top-2.5 text-slate-500" />
          <input
            type="text"
            value={searchQuery}
            onChange={(e) => setSearchQuery(e.target.value)}
            placeholder="Search leads, keywords, email..."
            className="w-full pl-9 pr-3 py-2 text-xs bg-slate-950 rounded-xl border border-slate-800 text-slate-200 focus:outline-none focus:border-blue-500"
          />
        </div>

        {/* Filters */}
        <div className="flex flex-wrap items-center gap-2 w-full md:w-auto">
          {/* Status filter */}
          <select
            value={currentStatusFilter}
            onChange={(e) => setStatusFilter(e.target.value)}
            className="px-3 py-1.5 text-xs bg-slate-950 border border-slate-800 rounded-xl text-slate-300 focus:outline-none"
          >
            <option value="ALL">All Statuses ({leads.length})</option>
            <option value="RAW">Raw</option>
            <option value="ANALYZED">Analyzed</option>
            <option value="SCHEDULED">Scheduled</option>
            <option value="SENT">Sent</option>
            <option value="REPLIED">Replied</option>
            <option value="FILTERED_OUT">Filtered Out</option>
          </select>

          {/* Source filter */}
          <select
            value={sourceFilter}
            onChange={(e) => setSourceFilter(e.target.value)}
            className="px-3 py-1.5 text-xs bg-slate-950 border border-slate-800 rounded-xl text-slate-300 focus:outline-none"
          >
            <option value="ALL">All Channels</option>
            <option value="Reddit">Reddit RSS</option>
            <option value="LinkedIn">LinkedIn</option>
            <option value="Web">Web Dorks</option>
          </select>

          {/* View toggle */}
          <div className="flex items-center bg-slate-950 p-1 rounded-xl border border-slate-800">
            <button
              onClick={() => setViewMode('kanban')}
              className={`p-1.5 rounded-lg text-xs ${
                viewMode === 'kanban' ? 'bg-blue-600 text-white' : 'text-slate-400 hover:text-slate-200'
              }`}
              title="Kanban Board View"
            >
              <Kanban className="w-3.5 h-3.5" />
            </button>
            <button
              onClick={() => setViewMode('table')}
              className={`p-1.5 rounded-lg text-xs ${
                viewMode === 'table' ? 'bg-blue-600 text-white' : 'text-slate-400 hover:text-slate-200'
              }`}
              title="Data Table View"
            >
              <Table className="w-3.5 h-3.5" />
            </button>
          </div>
        </div>
      </div>

      {/* Render Kanban or Table View */}
      {viewMode === 'kanban' ? (
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 xl:grid-cols-6 gap-3 overflow-x-auto pb-4">
          {STATUS_COLUMNS.map((column) => {
            const colLeads = filteredLeads.filter((l) => l.status === column.key);
            return (
              <div
                key={column.key}
                className="rounded-2xl bg-slate-900/40 border border-slate-800/80 p-3 flex flex-col min-w-[240px] max-h-[750px]"
              >
                {/* Column Header */}
                <div className="flex items-center justify-between pb-2 mb-2 border-b border-slate-800">
                  <span className="text-xs font-bold text-slate-300">{column.label}</span>
                  <span className="px-1.5 py-0.5 rounded-full text-[10px] font-mono font-bold bg-slate-800 text-slate-400">
                    {colLeads.length}
                  </span>
                </div>

                {/* Cards List */}
                <div className="space-y-2.5 overflow-y-auto flex-1 pr-0.5">
                  {colLeads.length === 0 ? (
                    <div className="py-8 text-center text-[11px] text-slate-600 italic">No leads in stage</div>
                  ) : (
                    colLeads.map((lead) => (
                      <div
                        key={lead.id}
                        onClick={() => onOpenLead(lead)}
                        className="p-3 rounded-xl bg-slate-950/80 border border-slate-850 hover:border-slate-700 transition cursor-pointer shadow-sm hover:shadow group space-y-2"
                      >
                        <div className="flex items-center justify-between text-[10px]">
                          <span
                            className={`px-1.5 py-0.5 rounded font-bold uppercase ${
                              lead.source === 'Reddit'
                                ? 'bg-orange-500/10 text-orange-400'
                                : lead.source === 'LinkedIn'
                                ? 'bg-blue-500/10 text-blue-400'
                                : 'bg-emerald-500/10 text-emerald-400'
                            }`}
                          >
                            {lead.source}
                          </span>
                          <span className="text-slate-500 font-mono">#{lead.id}</span>
                        </div>

                        <h4 className="text-xs font-semibold text-slate-200 line-clamp-2 leading-snug group-hover:text-blue-400 transition">
                          {lead.title}
                        </h4>

                        <div className="flex items-center justify-between text-[10px] text-slate-400 pt-1 border-t border-slate-900">
                          <span className="truncate max-w-[120px] font-mono">{lead.email || lead.author_id}</span>
                          <span>{lead.timezone.split('/')[1] || lead.timezone}</span>
                        </div>

                        {/* Quick Action buttons */}
                        <div
                          className="pt-1 flex items-center justify-between gap-1"
                          onClick={(e) => e.stopPropagation()}
                        >
                          {lead.status === 'RAW' && (
                            <button
                              onClick={() => handleAnalyze(lead.id)}
                              disabled={analyzingId === lead.id}
                              className="w-full flex items-center justify-center space-x-1 py-1 rounded-lg text-[10px] font-medium bg-purple-600/20 text-purple-300 hover:bg-purple-600/30 border border-purple-500/30"
                            >
                              <Sparkles className="w-2.5 h-2.5" />
                              <span>{analyzingId === lead.id ? 'Analyzing...' : 'Analyze'}</span>
                            </button>
                          )}

                          {lead.status === 'ANALYZED' && (
                            <button
                              onClick={() => handleSendNow(lead)}
                              className="w-full flex items-center justify-center space-x-1 py-1 rounded-lg text-[10px] font-medium bg-blue-600 text-white hover:bg-blue-500 shadow-sm"
                            >
                              <Send className="w-2.5 h-2.5" />
                              <span>Send SMTP</span>
                            </button>
                          )}

                          {lead.status === 'REPLIED' && (
                            <button
                              onClick={() => onOpenLead(lead)}
                              className="w-full flex items-center justify-center space-x-1 py-1 rounded-lg text-[10px] font-medium bg-emerald-600/20 text-emerald-300 border border-emerald-500/30"
                            >
                              <span>View Reply</span>
                            </button>
                          )}
                        </div>
                      </div>
                    ))
                  )}
                </div>
              </div>
            );
          })}
        </div>
      ) : (
        /* Data Table View */
        <div className="rounded-2xl bg-slate-900/60 border border-slate-800 overflow-hidden backdrop-blur-sm shadow-sm">
          <div className="overflow-x-auto">
            <table className="w-full text-left text-xs">
              <thead className="bg-slate-950/80 text-slate-400 font-semibold border-b border-slate-800 uppercase tracking-wider text-[10px]">
                <tr>
                  <th className="px-4 py-3">ID / Source</th>
                  <th className="px-4 py-3">Title & Post Context</th>
                  <th className="px-4 py-3">Recipient / Author</th>
                  <th className="px-4 py-3">Location & Timezone</th>
                  <th className="px-4 py-3">Status</th>
                  <th className="px-4 py-3 text-right">Actions</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-slate-850">
                {filteredLeads.map((lead) => (
                  <tr
                    key={lead.id}
                    onClick={() => onOpenLead(lead)}
                    className="hover:bg-slate-850/50 cursor-pointer transition"
                  >
                    <td className="px-4 py-3 whitespace-nowrap">
                      <div className="flex items-center space-x-2">
                        <span className="font-mono text-slate-500">#{lead.id}</span>
                        <span
                          className={`px-1.5 py-0.5 rounded text-[10px] font-bold uppercase ${
                            lead.source === 'Reddit'
                              ? 'bg-orange-500/10 text-orange-400'
                              : lead.source === 'LinkedIn'
                              ? 'bg-blue-500/10 text-blue-400'
                              : 'bg-emerald-500/10 text-emerald-400'
                          }`}
                        >
                          {lead.source}
                        </span>
                      </div>
                    </td>

                    <td className="px-4 py-3 max-w-sm">
                      <div className="font-semibold text-slate-200 line-clamp-1">{lead.title}</div>
                      <div className="text-slate-400 text-[11px] line-clamp-1">{lead.raw_text}</div>
                    </td>

                    <td className="px-4 py-3 whitespace-nowrap">
                      <div className="text-slate-200 font-mono text-[11px]">{lead.email || '—'}</div>
                      <div className="text-slate-500 text-[10px]">@{lead.author_id}</div>
                    </td>

                    <td className="px-4 py-3 whitespace-nowrap text-slate-400 text-[11px]">
                      <div>{lead.detected_country}</div>
                      <div className="text-[10px] text-slate-500">{lead.timezone}</div>
                    </td>

                    <td className="px-4 py-3 whitespace-nowrap">
                      <span className={`px-2 py-0.5 rounded-md text-[10px] font-semibold border ${getStatusBadge(lead.status)}`}>
                        {lead.status}
                      </span>
                    </td>

                    <td className="px-4 py-3 whitespace-nowrap text-right" onClick={(e) => e.stopPropagation()}>
                      <div className="flex items-center justify-end space-x-1.5">
                        {lead.status === 'RAW' && (
                          <button
                            onClick={() => handleAnalyze(lead.id)}
                            disabled={analyzingId === lead.id}
                            className="p-1.5 rounded-lg bg-purple-500/10 hover:bg-purple-500/20 text-purple-400 border border-purple-500/20"
                            title="Analyze with Gemini 2.5 Flash"
                          >
                            <Sparkles className="w-3.5 h-3.5" />
                          </button>
                        )}

                        {lead.status === 'ANALYZED' && (
                          <button
                            onClick={() => handleSendNow(lead)}
                            className="p-1.5 rounded-lg bg-blue-500/10 hover:bg-blue-500/20 text-blue-400 border border-blue-500/20"
                            title="Send Now via SMTP"
                          >
                            <Send className="w-3.5 h-3.5" />
                          </button>
                        )}

                        <button
                          onClick={() => onOpenLead(lead)}
                          className="p-1.5 rounded-lg bg-slate-800 hover:bg-slate-700 text-slate-300"
                          title="Open Details"
                        >
                          <Eye className="w-3.5 h-3.5" />
                        </button>
                      </div>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>
      )}
    </div>
  );
}

