'use client';

import React, { useState, useEffect } from 'react';
import { AppSettings } from '@/types';
import {
  X,
  ShieldCheck,
  Key,
  Mail,
  Lock,
  Server,
  Link as LinkIcon,
  Clock,
  Sparkles,
  CheckCircle,
  AlertTriangle,
  RefreshCw,
  ExternalLink
} from 'lucide-react';
import { fetchSettings, updateSettings, testSmtp, testImap } from '@/lib/api';

interface SettingsModalProps {
  isOpen: boolean;
  onClose: () => void;
}

export function SettingsModal({ isOpen, onClose }: SettingsModalProps) {
  if (!isOpen) return null;

  const [formData, setFormData] = useState<AppSettings>({
    gemini_api_key: '',
    email_user: '',
    email_app_password: '',
    smtp_host: 'smtp.gmail.com',
    smtp_port: 465,
    imap_host: 'imap.gmail.com',
    imap_port: 993,
    sender_name: 'Alex Rivera',
    portfolio_url: 'https://alexrivera.dev',
    calendly_url: 'https://calendly.com/alexrivera/30min',
    auto_reply_mode: 'manual',
    daily_scrape_time_ist: '10:00',
    email_throttle_min_sec: 45,
    email_throttle_max_sec: 90
  });

  const [isLoading, setIsLoading] = useState(true);
  const [isSaving, setIsSaving] = useState(false);
  const [smtpTesting, setSmtpTesting] = useState(false);
  const [imapTesting, setImapTesting] = useState(false);
  const [smtpTestResult, setSmtpTestResult] = useState<{ success: boolean; message: string } | null>(null);
  const [imapTestResult, setImapTestResult] = useState<{ success: boolean; message: string } | null>(null);
  const [saveSuccess, setSaveSuccess] = useState(false);

  useEffect(() => {
    async function load() {
      try {
        const data = await fetchSettings();
        setFormData(data);
      } catch (err) {
        console.error(err);
      } finally {
        setIsLoading(false);
      }
    }
    load();
  }, []);

  const handleChange = (field: keyof AppSettings, val: any) => {
    setFormData((prev) => ({ ...prev, [field]: val }));
  };

  const handleSave = async (e: React.FormEvent) => {
    e.preventDefault();
    setIsSaving(true);
    setSaveSuccess(false);
    try {
      await updateSettings(formData);
      setSaveSuccess(true);
      setTimeout(() => setSaveSuccess(false), 2500);
    } catch (err) {
      alert('Failed to save settings');
    } finally {
      setIsSaving(false);
    }
  };

  const handleTestSmtp = async () => {
    setSmtpTesting(true);
    setSmtpTestResult(null);
    try {
      const res = await testSmtp();
      setSmtpTestResult(res);
    } catch (err: any) {
      setSmtpTestResult({ success: false, message: err.message || 'SMTP Test Failed' });
    } finally {
      setSmtpTesting(false);
    }
  };

  const handleTestImap = async () => {
    setImapTesting(true);
    setImapTestResult(null);
    try {
      const res = await testImap();
      setImapTestResult(res);
    } catch (err: any) {
      setImapTestResult({ success: false, message: err.message || 'IMAP Test Failed' });
    } finally {
      setImapTesting(false);
    }
  };

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-black/80 backdrop-blur-sm overflow-y-auto">
      <div className="relative w-full max-w-2xl bg-slate-900 border border-slate-800 rounded-3xl shadow-2xl overflow-hidden my-8">
        {/* Header */}
        <div className="flex items-center justify-between px-6 py-4 border-b border-slate-800 bg-slate-950/60">
          <div className="flex items-center space-x-2.5">
            <div className="p-2 rounded-xl bg-blue-600/10 text-blue-400 border border-blue-500/20">
              <ShieldCheck className="w-5 h-5" />
            </div>
            <div>
              <h2 className="text-base font-bold text-white">System Settings & Engine Config</h2>
              <p className="text-xs text-slate-400">
                Direct Gmail SMTP/IMAP protocol & Gemini 2.5 Flash credentials
              </p>
            </div>
          </div>
          <button
            onClick={onClose}
            className="p-1 rounded-lg text-slate-400 hover:text-white hover:bg-slate-800 transition"
          >
            <X className="w-5 h-5" />
          </button>
        </div>

        {/* Content */}
        <form onSubmit={handleSave} className="p-6 space-y-6 max-h-[75vh] overflow-y-auto text-xs">
          {saveSuccess && (
            <div className="p-3 rounded-xl bg-emerald-950/60 border border-emerald-500/40 text-emerald-300 flex items-center space-x-2">
              <CheckCircle className="w-4 h-4 text-emerald-400" />
              <span>Configuration successfully saved to database!</span>
            </div>
          )}

          {/* Section 1: AI Engine (Gemini 2.5 Flash) */}
          <div className="space-y-3 p-4 rounded-2xl bg-slate-950/60 border border-slate-800">
            <div className="flex items-center space-x-2 text-purple-300 font-bold">
              <Sparkles className="w-4 h-4 text-purple-400" />
              <span>Google Gemini 2.5 Flash AI Engine</span>
            </div>

            <div className="space-y-1">
              <label className="text-[11px] font-semibold text-slate-400 uppercase">
                Gemini API Key
              </label>
              <div className="relative">
                <Key className="w-4 h-4 absolute left-3 top-2.5 text-slate-500" />
                <input
                  type="password"
                  value={formData.gemini_api_key || ''}
                  onChange={(e) => handleChange('gemini_api_key', e.target.value)}
                  placeholder="AIzaSy..."
                  className="w-full pl-9 pr-3 py-2 bg-slate-900 rounded-xl border border-slate-800 text-slate-200 font-mono focus:outline-none focus:border-blue-500"
                />
              </div>
              <p className="text-[10px] text-slate-500">
                Uses the official google-genai SDK for intent classification, pain point extraction, and cold pitch synthesis.
              </p>
            </div>
          </div>

          {/* Section 2: Direct Gmail SMTP & IMAP Credentials */}
          <div className="space-y-4 p-4 rounded-2xl bg-slate-950/60 border border-slate-800">
            <div className="flex items-center justify-between">
              <div className="flex items-center space-x-2 text-blue-300 font-bold">
                <Mail className="w-4 h-4 text-blue-400" />
                <span>Native Gmail Direct SMTP & IMAP Engine (No 3rd Party APIs)</span>
              </div>
            </div>

            <div className="p-2.5 rounded-xl bg-blue-950/20 border border-blue-800/30 text-[11px] text-blue-200 flex items-start space-x-2">
              <ShieldCheck className="w-4 h-4 text-blue-400 shrink-0 mt-0.5" />
              <div>
                <span>Create a 16-character Google App Password at </span>
                <a
                  href="https://myaccount.google.com/apppasswords"
                  target="_blank"
                  rel="noreferrer"
                  className="text-blue-400 underline font-semibold inline-flex items-center"
                >
                  myaccount.google.com/apppasswords
                  <ExternalLink className="w-3 h-3 ml-1" />
                </a>
                <span> with 2-Factor Authentication enabled.</span>
              </div>
            </div>

            <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
              <div className="space-y-1">
                <label className="text-[11px] font-semibold text-slate-400 uppercase">
                  Gmail / Google Workspace User
                </label>
                <input
                  type="email"
                  value={formData.email_user || ''}
                  onChange={(e) => handleChange('email_user', e.target.value)}
                  placeholder="alex.developer@gmail.com"
                  className="w-full px-3 py-2 bg-slate-900 rounded-xl border border-slate-800 text-slate-200 font-mono focus:outline-none focus:border-blue-500"
                />
              </div>

              <div className="space-y-1">
                <label className="text-[11px] font-semibold text-slate-400 uppercase">
                  Google 16-Char App Password
                </label>
                <input
                  type="password"
                  value={formData.email_app_password || ''}
                  onChange={(e) => handleChange('email_app_password', e.target.value)}
                  placeholder="abcd efgh ijkl mnop"
                  className="w-full px-3 py-2 bg-slate-900 rounded-xl border border-slate-800 text-slate-200 font-mono focus:outline-none focus:border-blue-500"
                />
              </div>
            </div>

            {/* Host & Port grid */}
            <div className="grid grid-cols-2 sm:grid-cols-4 gap-3 text-[11px]">
              <div className="space-y-1">
                <label className="text-slate-400 uppercase">SMTP Host</label>
                <input
                  type="text"
                  value={formData.smtp_host || 'smtp.gmail.com'}
                  onChange={(e) => handleChange('smtp_host', e.target.value)}
                  className="w-full px-2.5 py-1.5 bg-slate-900 rounded-lg border border-slate-800 text-slate-200 font-mono"
                />
              </div>
              <div className="space-y-1">
                <label className="text-slate-400 uppercase">SMTP Port</label>
                <input
                  type="number"
                  value={formData.smtp_port || 465}
                  onChange={(e) => handleChange('smtp_port', parseInt(e.target.value))}
                  className="w-full px-2.5 py-1.5 bg-slate-900 rounded-lg border border-slate-800 text-slate-200 font-mono"
                />
              </div>
              <div className="space-y-1">
                <label className="text-slate-400 uppercase">IMAP Host</label>
                <input
                  type="text"
                  value={formData.imap_host || 'imap.gmail.com'}
                  onChange={(e) => handleChange('imap_host', e.target.value)}
                  className="w-full px-2.5 py-1.5 bg-slate-900 rounded-lg border border-slate-800 text-slate-200 font-mono"
                />
              </div>
              <div className="space-y-1">
                <label className="text-slate-400 uppercase">IMAP Port</label>
                <input
                  type="number"
                  value={formData.imap_port || 993}
                  onChange={(e) => handleChange('imap_port', parseInt(e.target.value))}
                  className="w-full px-2.5 py-1.5 bg-slate-900 rounded-lg border border-slate-800 text-slate-200 font-mono"
                />
              </div>
            </div>

            {/* Diagnostics Buttons */}
            <div className="flex flex-wrap items-center gap-2 pt-2 border-t border-slate-900">
              <button
                type="button"
                onClick={handleTestSmtp}
                disabled={smtpTesting}
                className="px-3 py-1.5 rounded-lg bg-blue-600/20 text-blue-300 hover:bg-blue-600/30 border border-blue-500/30 text-xs font-medium flex items-center space-x-1.5"
              >
                <Server className="w-3.5 h-3.5" />
                <span>{smtpTesting ? 'Testing SMTP...' : 'Test SMTP Connection'}</span>
              </button>

              <button
                type="button"
                onClick={handleTestImap}
                disabled={imapTesting}
                className="px-3 py-1.5 rounded-lg bg-emerald-600/20 text-emerald-300 hover:bg-emerald-600/30 border border-emerald-500/30 text-xs font-medium flex items-center space-x-1.5"
              >
                <Server className="w-3.5 h-3.5" />
                <span>{imapTesting ? 'Testing IMAP...' : 'Test IMAP Connection'}</span>
              </button>
            </div>

            {/* Diagnostic results */}
            {smtpTestResult && (
              <div
                className={`p-2.5 rounded-xl border text-[11px] flex items-start space-x-2 ${
                  smtpTestResult.success
                    ? 'bg-emerald-950/60 border-emerald-500/40 text-emerald-300'
                    : 'bg-rose-950/60 border-rose-500/40 text-rose-300'
                }`}
              >
                {smtpTestResult.success ? <CheckCircle className="w-3.5 h-3.5 mt-0.5" /> : <AlertTriangle className="w-3.5 h-3.5 mt-0.5" />}
                <span>{smtpTestResult.message}</span>
              </div>
            )}

            {imapTestResult && (
              <div
                className={`p-2.5 rounded-xl border text-[11px] flex items-start space-x-2 ${
                  imapTestResult.success
                    ? 'bg-emerald-950/60 border-emerald-500/40 text-emerald-300'
                    : 'bg-rose-950/60 border-rose-500/40 text-rose-300'
                }`}
              >
                {imapTestResult.success ? <CheckCircle className="w-3.5 h-3.5 mt-0.5" /> : <AlertTriangle className="w-3.5 h-3.5 mt-0.5" />}
                <span>{imapTestResult.message}</span>
              </div>
            )}
          </div>

          {/* Section 3: Sender Persona & Links */}
          <div className="space-y-3 p-4 rounded-2xl bg-slate-950/60 border border-slate-800">
            <span className="text-xs font-bold text-slate-300">Outreach Persona & Booking Links</span>

            <div className="grid grid-cols-1 sm:grid-cols-3 gap-3">
              <div className="space-y-1">
                <label className="text-[11px] font-semibold text-slate-400 uppercase">Sender Name</label>
                <input
                  type="text"
                  value={formData.sender_name || ''}
                  onChange={(e) => handleChange('sender_name', e.target.value)}
                  className="w-full px-3 py-2 bg-slate-900 rounded-xl border border-slate-800 text-slate-200"
                />
              </div>

              <div className="space-y-1">
                <label className="text-[11px] font-semibold text-slate-400 uppercase">Portfolio URL</label>
                <input
                  type="url"
                  value={formData.portfolio_url || ''}
                  onChange={(e) => handleChange('portfolio_url', e.target.value)}
                  className="w-full px-3 py-2 bg-slate-900 rounded-xl border border-slate-800 text-slate-200"
                />
              </div>

              <div className="space-y-1">
                <label className="text-[11px] font-semibold text-slate-400 uppercase">Calendly / Sync Link</label>
                <input
                  type="url"
                  value={formData.calendly_url || ''}
                  onChange={(e) => handleChange('calendly_url', e.target.value)}
                  className="w-full px-3 py-2 bg-slate-900 rounded-xl border border-slate-800 text-slate-200"
                />
              </div>
            </div>
          </div>

          {/* Section 4: Auto-Reply Mode & Throttling */}
          <div className="space-y-3 p-4 rounded-2xl bg-slate-950/60 border border-slate-800">
            <span className="text-xs font-bold text-slate-300">Inbound Follow-up Engine & Anti-Ban Rate Limit</span>

            <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
              <div className="space-y-1">
                <label className="text-[11px] font-semibold text-slate-400 uppercase">
                  Inbound Auto-Reply Mode
                </label>
                <select
                  value={formData.auto_reply_mode || 'manual'}
                  onChange={(e) => handleChange('auto_reply_mode', e.target.value)}
                  className="w-full px-3 py-2 bg-slate-900 rounded-xl border border-slate-800 text-slate-200"
                >
                  <option value="manual">Manual Approval (Flags as NEEDS_REVIEW)</option>
                  <option value="autonomous">Autonomous (Auto-dispatches to interested leads)</option>
                </select>
              </div>

              <div className="space-y-1">
                <label className="text-[11px] font-semibold text-slate-400 uppercase">
                  Daily Scraper Schedule (IST)
                </label>
                <div className="px-3 py-2 bg-slate-900 rounded-xl border border-slate-800 text-slate-300 font-mono">
                  10:00 AM IST (Asia/Kolkata)
                </div>
              </div>
            </div>

            <div className="grid grid-cols-2 gap-3">
              <div className="space-y-1">
                <label className="text-[11px] font-semibold text-slate-400 uppercase">Min Anti-Ban Delay (s)</label>
                <input
                  type="number"
                  value={formData.email_throttle_min_sec || 45}
                  onChange={(e) => handleChange('email_throttle_min_sec', parseInt(e.target.value))}
                  className="w-full px-3 py-2 bg-slate-900 rounded-xl border border-slate-800 text-slate-200 font-mono"
                />
              </div>
              <div className="space-y-1">
                <label className="text-[11px] font-semibold text-slate-400 uppercase">Max Anti-Ban Delay (s)</label>
                <input
                  type="number"
                  value={formData.email_throttle_max_sec || 90}
                  onChange={(e) => handleChange('email_throttle_max_sec', parseInt(e.target.value))}
                  className="w-full px-3 py-2 bg-slate-900 rounded-xl border border-slate-800 text-slate-200 font-mono"
                />
              </div>
            </div>
          </div>

          {/* Form Actions */}
          <div className="flex justify-end space-x-2 pt-2 border-t border-slate-800">
            <button
              type="button"
              onClick={onClose}
              className="px-4 py-2 rounded-xl text-slate-300 hover:bg-slate-800 transition"
            >
              Cancel
            </button>
            <button
              type="submit"
              disabled={isSaving}
              className="px-6 py-2 rounded-xl bg-blue-600 hover:bg-blue-500 font-bold text-white transition shadow-lg shadow-blue-500/20 disabled:opacity-50"
            >
              {isSaving ? 'Saving...' : 'Save Settings'}
            </button>
          </div>
        </form>
      </div>
    </div>
  );
}
