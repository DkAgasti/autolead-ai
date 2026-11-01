'use client';

import React, { useState, useEffect, useCallback } from 'react';
import { Lead, AnalyticsData } from '@/types';
import {
  fetchAnalytics,
  fetchLeads,
  triggerHarvest,
  triggerPollImap
} from '@/lib/api';
import { Header } from '@/components/Header';
import { AnalyticsOverview } from '@/components/AnalyticsOverview';
import { ActionCenter } from '@/components/ActionCenter';
import { LeadsPipeline } from '@/components/LeadsPipeline';
import { InboxThreads } from '@/components/InboxThreads';
import { LeadDetailModal } from '@/components/LeadDetailModal';
import { SettingsModal } from '@/components/SettingsModal';
import { Sparkles, AlertCircle, CheckCircle2 } from 'lucide-react';

export default function DashboardPage() {
  const [activeTab, setActiveTab] = useState<'dashboard' | 'pipeline' | 'action_center' | 'inbox'>('dashboard');
  const [analytics, setAnalytics] = useState<AnalyticsData | null>(null);
  const [leads, setLeads] = useState<Lead[]>([]);
  const [selectedLead, setSelectedLead] = useState<Lead | null>(null);
  const [isSettingsOpen, setIsSettingsOpen] = useState(false);
  const [statusFilter, setStatusFilter] = useState<string>('ALL');

  // Triggering state
  const [isScraping, setIsScraping] = useState(false);
  const [isPollingImap, setIsPollingImap] = useState(false);
  const [toastMessage, setToastMessage] = useState<{ text: string; type: 'success' | 'info' | 'error' } | null>(null);

  const showToast = (text: string, type: 'success' | 'info' | 'error' = 'info') => {
    setToastMessage({ text, type });
    setTimeout(() => setToastMessage(null), 4000);
  };

  const loadData = useCallback(async () => {
    try {
      const [analyticsData, leadsData] = await Promise.all([
        fetchAnalytics(),
        fetchLeads()
      ]);
      setAnalytics(analyticsData);
      setLeads(leadsData);
    } catch (err) {
      console.error('Error loading dashboard data:', err);
    }
  }, []);

  useEffect(() => {
    loadData();
    // Refresh every 15 seconds
    const interval = setInterval(loadData, 15000);
    return () => clearInterval(interval);
  }, [loadData]);

  const handleTriggerScrape = async () => {
    setIsScraping(true);
    try {
      const res = await triggerHarvest();
      showToast(`Harvester finished! Added ${res.added} new leads, skipped ${res.skipped} duplicates.`, 'success');
      loadData();
    } catch (err: any) {
      showToast(err.message || 'Harvester failed', 'error');
    } finally {
      setIsScraping(false);
    }
  };

  const handleTriggerImap = async () => {
    setIsPollingImap(true);
    try {
      const res = await triggerPollImap();
      showToast(`IMAP poll completed: matched ${res.matched_replies} client replies.`, 'success');
      loadData();
    } catch (err: any) {
      showToast(err.message || 'IMAP polling failed', 'error');
    } finally {
      setIsPollingImap(false);
    }
  };

  const handleSelectStatusFilter = (st: string) => {
    setStatusFilter(st);
    setActiveTab('pipeline');
  };

  // Count unreviewed replies
  const unreviewedCount = leads.reduce((acc, lead) => {
    const unrev = (lead.threads || []).filter((t) => t.direction === 'INBOUND' && t.status === 'NEEDS_REVIEW');
    return acc + unrev.length;
  }, 0);

  const analyzedCount = leads.filter((l) => l.status === 'ANALYZED').length;

  return (
    <div className="min-h-screen bg-slate-950 text-slate-100 flex flex-col font-sans selection:bg-blue-600 selection:text-white">
      {/* Top Navigation */}
      <Header
        activeTab={activeTab}
        setActiveTab={setActiveTab}
        onOpenSettings={() => setIsSettingsOpen(true)}
        onTriggerScrape={handleTriggerScrape}
        onTriggerImap={handleTriggerImap}
        isScraping={isScraping}
        isPollingImap={isPollingImap}
        unreviewedCount={unreviewedCount}
        analyzedCount={analyzedCount}
      />

      {/* Floating Toast Notification */}
      {toastMessage && (
        <div className="fixed bottom-6 right-6 z-50 flex items-center space-x-2 px-4 py-3 rounded-2xl bg-slate-900 border border-slate-700 shadow-2xl text-xs font-medium animate-in fade-in slide-in-from-bottom-5">
          {toastMessage.type === 'success' ? (
            <CheckCircle2 className="w-4 h-4 text-emerald-400" />
          ) : toastMessage.type === 'error' ? (
            <AlertCircle className="w-4 h-4 text-rose-400" />
          ) : (
            <Sparkles className="w-4 h-4 text-blue-400" />
          )}
          <span>{toastMessage.text}</span>
        </div>
      )}

      {/* Main Container */}
      <main className="flex-1 max-w-7xl w-full mx-auto px-4 sm:px-6 lg:px-8 py-8 space-y-6">
        {/* Banner Pill */}
        <div className="flex flex-col sm:flex-row items-start sm:items-center justify-between gap-3 p-3.5 rounded-2xl bg-gradient-to-r from-blue-900/30 via-indigo-900/20 to-purple-900/30 border border-indigo-500/20 text-xs">
          <div className="flex items-center space-x-2">
            <span className="flex h-2 w-2 rounded-full bg-emerald-400 animate-ping" />
            <span className="font-semibold text-slate-200">
              AutoLead AI Native Engine Active
            </span>
            <span className="text-slate-400 hidden md:inline">
              • Direct SMTP (`smtp.gmail.com:465`) & IMAP (`imap.gmail.com:993`) via Google App Password
            </span>
          </div>

          <div className="flex items-center space-x-3 text-slate-400">
            <span>Next Harvester: <strong className="text-slate-200">10:00 AM IST</strong></span>
            <span>Anti-ban: <strong className="text-slate-200">45-90s</strong></span>
          </div>
        </div>

        {/* Tab Views */}
        {activeTab === 'dashboard' && (
          <AnalyticsOverview
            analytics={analytics}
            onSelectStatusFilter={handleSelectStatusFilter}
            onQuickAction={() => setActiveTab('action_center')}
          />
        )}

        {activeTab === 'action_center' && (
          <ActionCenter
            leads={leads}
            onRefresh={loadData}
            onOpenLead={(lead) => setSelectedLead(lead)}
          />
        )}

        {activeTab === 'pipeline' && (
          <LeadsPipeline
            leads={leads}
            currentStatusFilter={statusFilter}
            setStatusFilter={setStatusFilter}
            onOpenLead={(lead) => setSelectedLead(lead)}
            onRefresh={loadData}
          />
        )}

        {activeTab === 'inbox' && (
          <InboxThreads
            leads={leads}
            onRefresh={loadData}
            onOpenLead={(lead) => setSelectedLead(lead)}
          />
        )}
      </main>

      {/* Footer */}
      <footer className="border-t border-slate-900 py-6 text-center text-xs text-slate-500">
        <p>AutoLead AI • Native Direct SMTP/IMAP Outbound & Inbound Engine • Powered by Google Gemini 2.5 Flash</p>
      </footer>

      {/* Modals */}
      <LeadDetailModal
        lead={selectedLead}
        onClose={() => setSelectedLead(null)}
        onRefresh={loadData}
      />

      <SettingsModal
        isOpen={isSettingsOpen}
        onClose={() => {
          setIsSettingsOpen(false);
          loadData();
        }}
      />
    </div>
  );
}
