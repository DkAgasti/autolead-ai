export type LeadStatus = 'RAW' | 'ANALYZED' | 'FILTERED_OUT' | 'SCHEDULED' | 'SENT' | 'REPLIED' | 'BOUNCED' | 'NEEDS_EMAIL';

export type LeadSource = 'Reddit' | 'LinkedIn' | 'Web' | string;

export interface EmailThread {
  id: number;
  lead_id: number;
  direction: 'OUTBOUND' | 'INBOUND';
  sender: string;
  recipient: string;
  subject: string;
  body_text: string;
  body_html?: string | null;
  message_id?: string | null;
  in_reply_to?: string | null;
  sentiment?: 'INTERESTED' | 'SCHEDULING' | 'NOT_INTERESTED' | 'OBJECTION' | 'NEUTRAL' | null;
  auto_reply_draft?: string | null;
  status: 'SENT' | 'RECEIVED' | 'NEEDS_REVIEW' | 'AUTO_REPLIED' | 'BOUNCED';
  created_at: string;
}

export interface Lead {
  id: number;
  source: LeadSource;
  source_url?: string | null;
  title: string;
  raw_text: string;
  author_id?: string | null;
  email?: string | null;
  website_url?: string | null;
  detected_country: string;
  timezone: string;
  status: LeadStatus;
  is_hiring?: boolean | null;
  lead_name?: string | null;
  pain_points?: string | null; // JSON string
  audit_summary?: string | null;
  subject_line?: string | null;
  email_body?: string | null;
  scheduled_at?: string | null;
  sent_at?: string | null;
  message_id?: string | null;
  created_at: string;
  updated_at: string;
  threads: EmailThread[];
}

export interface AnalyticsData {
  total_leads: number;
  scraped_today: number;
  valid_leads: number;
  emails_dispatched: number;
  replies_received: number;
  reply_rate: number;
  status_counts: Record<string, number>;
  source_counts: Record<string, number>;
  recent_activity: {
    id: number;
    level: string;
    module: string;
    message: string;
    time: string;
  }[];
}

export interface AppSettings {
  gemini_api_key?: string;
  email_user?: string;
  email_app_password?: string;
  brevo_api_key?: string;
  resend_api_key?: string;
  smtp_host?: string;
  smtp_port?: number;
  imap_host?: string;
  imap_port?: number;
  sender_name?: string;
  portfolio_url?: string;
  calendly_url?: string;
  auto_reply_mode?: 'manual' | 'autonomous';
  daily_scrape_time_ist?: string;
  email_throttle_min_sec?: number;
  email_throttle_max_sec?: number;
}

