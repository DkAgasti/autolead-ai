'use client';

import React from 'react';
import {
  Bot,
  Zap,
  Mail,
  RefreshCw,
  Settings as SettingsIcon,
  Inbox,
  LayoutDashboard,
  KanbanSquare,
  CheckCircle2,
  ShieldCheck
} from 'lucide-react';

interface HeaderProps {
  activeTab: 'dashboard' | 'pipeline' | 'action_center' | 'inbox';
  setActiveTab: (tab: 'dashboard' | 'pipeline' | 'action_center' | 'inbox') => void;
  onOpenSettings: () => void;
  onTriggerScrape: () => void;
  onTriggerImap: () => void;
  isScraping: boolean;
  isPollingImap: boolean;
  unreviewedCount?: number;
  analyzedCount?: number;
}

export function Header({
  activeTab,
  setActiveTab,
  onOpenSettings,
  onTriggerScrape,
  onTriggerImap,
  isScraping,
  isPollingImap,
  unreviewedCount = 0,
  analyzedCount = 0
}: HeaderProps) {
  return (
    <header className="sticky top-0 z-40 w-full border-b border-slate-800 bg-slate-950/80 backdrop-blur-md">
      <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
        <div className="flex items-center justify-between h-16">
          {/* Logo & Brand */}
          <div className="flex items-center space-x-3">
            <div className="flex items-center justify-center w-10 h-10 rounded-xl bg-gradient-to-tr from-blue-600 via-indigo-600 to-purple-600 shadow-lg shadow-indigo-500/20 text-white">
              <Bot className="w-5 h-5" />
            </div>
            <div>
              <div className="flex items-center space-x-2">
                <span className="text-lg font-bold tracking-tight text-white">AutoLead AI</span>
                <span className="inline-flex items-center px-2 py-0.5 rounded text-[10px] font-medium bg-emerald-500/10 text-emerald-400 border border-emerald-500/20">
                  <ShieldCheck className="w-2.5 h-2.5 mr-1" />
                  Native SMTP/IMAP
                </span>
              </div>
              <p className="text-xs text-slate-400 hidden sm:block">
                Autonomous Outreach & Follow-up Agent • Gemini 2.5 Flash
              </p>
            </div>
          </div>

          {/* Navigation Tabs */}
          <nav className="hidden md:flex items-center space-x-1 bg-slate-900/90 p-1 rounded-xl border border-slate-800">
            <button
              onClick={() => setActiveTab('dashboard')}
              className={`flex items-center space-x-1.5 px-3 py-1.5 rounded-lg text-xs font-medium transition-all ${
                activeTab === 'dashboard'
                  ? 'bg-blue-600 text-white shadow-sm'
                  : 'text-slate-400 hover:text-slate-200 hover:bg-slate-800/50'
              }`}
            >
              <LayoutDashboard className="w-3.5 h-3.5" />
              <span>Overview</span>
            </button>

            <button
              onClick={() => setActiveTab('action_center')}
              className={`flex items-center space-x-1.5 px-3 py-1.5 rounded-lg text-xs font-medium transition-all relative ${
                activeTab === 'action_center'
                  ? 'bg-blue-600 text-white shadow-sm'
                  : 'text-slate-400 hover:text-slate-200 hover:bg-slate-800/50'
              }`}
            >
              <CheckCircle2 className="w-3.5 h-3.5" />
              <span>Action Center</span>
              {analyzedCount > 0 && (
                <span className="ml-1 px-1.5 py-0.2 rounded-full text-[10px] font-bold bg-purple-500 text-white">
                  {analyzedCount}
                </span>
              )}
            </button>

            <button
              onClick={() => setActiveTab('pipeline')}
              className={`flex items-center space-x-1.5 px-3 py-1.5 rounded-lg text-xs font-medium transition-all ${
                activeTab === 'pipeline'
                  ? 'bg-blue-600 text-white shadow-sm'
                  : 'text-slate-400 hover:text-slate-200 hover:bg-slate-800/50'
              }`}
            >
              <KanbanSquare className="w-3.5 h-3.5" />
              <span>Pipeline & Leads</span>
            </button>

            <button
              onClick={() => setActiveTab('inbox')}
              className={`flex items-center space-x-1.5 px-3 py-1.5 rounded-lg text-xs font-medium transition-all relative ${
                activeTab === 'inbox'
                  ? 'bg-blue-600 text-white shadow-sm'
                  : 'text-slate-400 hover:text-slate-200 hover:bg-slate-800/50'
              }`}
            >
              <Inbox className="w-3.5 h-3.5" />
              <span>Replies & Threads</span>
              {unreviewedCount > 0 && (
                <span className="ml-1 px-1.5 py-0.2 rounded-full text-[10px] font-bold bg-emerald-500 text-white animate-pulse">
                  {unreviewedCount}
                </span>
              )}
            </button>
          </nav>

          {/* Quick Actions */}
          <div className="flex items-center space-x-2">
            <button
              onClick={onTriggerScrape}
              disabled={isScraping}
              className="flex items-center space-x-1.5 px-2.5 py-1.5 rounded-lg text-xs font-medium text-slate-300 bg-slate-900 hover:bg-slate-800 border border-slate-750 disabled:opacity-50 transition"
              title="Scrape Reddit RSS & Web Feeds Now"
            >
              <RefreshCw className={`w-3.5 h-3.5 text-blue-400 ${isScraping ? 'animate-spin' : ''}`} />
              <span className="hidden lg:inline">{isScraping ? 'Scraping...' : 'Harvest Feeds'}</span>
            </button>

            <button
              onClick={onTriggerImap}
              disabled={isPollingImap}
              className="flex items-center space-x-1.5 px-2.5 py-1.5 rounded-lg text-xs font-medium text-slate-300 bg-slate-900 hover:bg-slate-800 border border-slate-750 disabled:opacity-50 transition"
              title="Poll Gmail INBOX via IMAP (Port 993 SSL)"
            >
              <Mail className={`w-3.5 h-3.5 text-emerald-400 ${isPollingImap ? 'animate-pulse' : ''}`} />
              <span className="hidden lg:inline">{isPollingImap ? 'Polling IMAP...' : 'Check Inbox'}</span>
            </button>

            <button
              onClick={onOpenSettings}
              className="p-1.5 rounded-lg text-slate-400 hover:text-slate-200 hover:bg-slate-900 border border-slate-800 transition"
              title="Settings & SMTP/IMAP Credentials"
            >
              <SettingsIcon className="w-4 h-4" />
            </button>
          </div>
        </div>
      </div>
    </header>
  );
}

