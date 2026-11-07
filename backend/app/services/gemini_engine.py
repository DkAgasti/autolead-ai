import json
import re
import logging
from typing import Dict, Any, List, Optional
from google import genai
from google.genai import types

from app.config import settings
from app.models import AppSetting
from app.database import SessionLocal

logger = logging.getLogger(__name__)

def get_effective_gemini_api_key() -> str:
    """Check database app_settings first, then fall back to environment settings."""
    try:
        db = SessionLocal()
        setting = db.query(AppSetting).filter(AppSetting.key == "gemini_api_key").first()
        db.close()
        if setting and setting.value and setting.value.strip():
            return setting.value.strip()
    except Exception:
        pass
    return settings.GEMINI_API_KEY.strip() if settings.GEMINI_API_KEY else ""

def get_effective_links() -> Dict[str, str]:
    portfolio = settings.PORTFOLIO_URL
    calendly = settings.CALENDLY_URL
    sender = settings.SENDER_NAME
    try:
        db = SessionLocal()
        p = db.query(AppSetting).filter(AppSetting.key == "portfolio_url").first()
        c = db.query(AppSetting).filter(AppSetting.key == "calendly_url").first()
        s = db.query(AppSetting).filter(AppSetting.key == "sender_name").first()
        db.close()
        if p and p.value:
            portfolio = p.value
        if c and c.value:
            calendly = c.value
        if s and s.value:
            sender = s.value
    except Exception:
        pass
    return {"portfolio_url": portfolio, "calendly_url": calendly, "sender_name": sender}

async def analyze_lead_with_gemini(
    title: str,
    raw_text: str,
    website_url: Optional[str] = None,
    audit_data: Optional[Dict[str, Any]] = None
) -> Dict[str, Any]:
    """
    Passes a post to Gemini 3/3.5 Flash via google-genai SDK.
    Filters intent, extracts niche & pain points, applies website audit,
    and drafts an ultra-personalized 100-130 word cold pitch.
    """
    api_key = get_effective_gemini_api_key()
    links = get_effective_links()

    # Clean title if it comes from HackerNews or Reddit comment headers
    clean_title = title
    if "new comment by" in title.lower() and raw_text:
        first_line = raw_text.strip().split("\n")[0].strip()
        if len(first_line) > 5 and not first_line.lower().startswith("new comment by"):
            clean_title = first_line[:100]

    # Validate website_url - discard malformed or broken URLs like 'https:///'
    if website_url:
        domain_part = website_url.replace("https://", "").replace("http://", "").strip("/")
        if "." not in domain_part or len(domain_part) < 4:
            website_url = None

    audit_context = ""
    if website_url and audit_data and audit_data.get("critiques"):
        critiques_str = "\n".join([f"- {c}" for c in audit_data["critiques"]])
        audit_context = f"""
WEBSITE AUDIT CONTEXT FOR {website_url}:
Response time: {audit_data.get('response_time_ms', 0)}ms
Critiques identified:
{critiques_str}
Instruction: Incorporate 1-2 of these technical critiques smoothly into the pitch.
"""
    else:
        audit_context = """
NO WEBSITE URL PROVIDED.
Instruction: Outline 2-3 specific commercial/technical advantages (e.g. Next.js SSR performance, conversion rate optimization, clean API architecture) tailored to their job post.
"""

    system_instruction = f"""
You are the AI personalization engine of AutoLead AI, a premier engineering cold outreach specialist.
Your goal is to parse job posts/freelance requests, verify hiring intent, identify technical pain points,
and write an authentic, punchy, non-salesy 100-130 word email pitch.

Outreach details to incorporate:
- Sender Name: {links['sender_name']}
- Portfolio: {links['portfolio_url']}
- Scheduling Link: {links['calendly_url']}

Rules:
1. Intent Filter: Determine if this post is genuinely an employer, founder, or client looking to hire (`is_hiring: true`). If it is a freelancer promoting themselves or a general discussion, return `is_hiring: false`.
2. Extract specific technical deliverables (e.g. Next.js landing page, Shopify overhaul, API bug fix, database migration).
3. The email body must:
   - Be strictly between 100 and 130 words.
   - Address the client respectfully (e.g. "Hi [Company/Team]" or "Hi [Name]"). NEVER write "I came across your post about New comment by...".
   - Refer directly to the company name or exact role they are hiring for.
   - Mention specific technical deliverables without generic buzzwords.
   - Provide a low-friction Call to Action (e.g., "Are you open to a quick 10-minute sync this week? You can also review some of my recent work at {links['portfolio_url']}").
   - Tone: Engineer-to-founder, concise, competent, zero cheesy fluff or corporate buzzwords.
4. Return ONLY valid JSON in this exact structure:
{{
  "is_hiring": true,
  "lead_name": "client name or team name",
  "pain_points": ["point 1", "point 2"],
  "audit_summary": "1-2 sentence summary of technical or commercial insights",
  "subject_line": "Catchy, relevant 4-7 word subject line without emojis",
  "email_body": "Full personalized 100-130 word cold pitch email text"
}}
"""

    user_prompt = f"""
JOB POST TITLE: {clean_title}
JOB POST TEXT:
{raw_text}

{audit_context}
"""

    if api_key:
        try:
            client = genai.Client(api_key=api_key)
            config = types.GenerateContentConfig(
                system_instruction=system_instruction,
                response_mime_type="application/json",
                temperature=0.4,
            )
            response = None
            for model_candidate in ["gemini-3-flash-preview", "gemini-3.5-flash", "gemini-3.8-flash"]:
                try:
                    response = client.models.generate_content(
                        model=model_candidate,
                        contents=user_prompt,
                        config=config
                    )
                    if response and response.text:
                        break
                except Exception as me:
                    logger.warning(f"Model {model_candidate} attempt notice: {me}")
                    continue

            if not response or not response.text:
                raise ValueError("No response generated from Gemini models")

            text_output = response.text.strip()
            # Clean possible markdown fence
            if text_output.startswith("```json"):
                text_output = text_output[7:]
            if text_output.startswith("```"):
                text_output = text_output[3:]
            if text_output.endswith("```"):
                text_output = text_output[:-3]
            
            data = json.loads(text_output.strip())
            return {
                "is_hiring": bool(data.get("is_hiring", True)),
                "lead_name": str(data.get("lead_name", "Hiring Team")),
                "pain_points": data.get("pain_points", []),
                "audit_summary": str(data.get("audit_summary", "")),
                "subject_line": str(data.get("subject_line", f"Regarding your {clean_title[:30]} opening")),
                "email_body": str(data.get("email_body", ""))
            }
        except Exception as e:
            logger.error(f"Gemini API error: {e}. Falling back to rule-based engine.")

    # High-quality fallback if Gemini API key is not configured or in offline test mode
    return generate_fallback_analysis(clean_title, raw_text, website_url, audit_data, links)

def generate_fallback_analysis(
    title: str,
    raw_text: str,
    website_url: Optional[str],
    audit_data: Optional[Dict[str, Any]],
    links: Dict[str, str]
) -> Dict[str, Any]:
    """Generates a contextual analysis when offline or waiting for user API key."""
    lower_content = (title + " " + raw_text).lower()
    is_freelancer_promo = any(phrase in lower_content for phrase in ["for hire", "[for hire]", "hire me", "i am a developer", "my portfolio", "available for work"])
    is_hiring_signals = any(phrase in lower_content for phrase in ["[hiring]", "looking for", "need a developer", "seeking", "budget:", "$", "wanted", "we are building"])
    
    is_hiring = is_hiring_signals and not (is_freelancer_promo and "[hiring]" not in lower_content)
    
    # Extract deliverables
    pain_points = []
    if "next" in lower_content or "react" in lower_content:
        pain_points.append("Modern Next.js / React frontend architecture")
    if "shopify" in lower_content or "ecommerce" in lower_content:
        pain_points.append("E-commerce performance and checkout conversion")
    if "design" in lower_content or "ui" in lower_content:
        pain_points.append("Clean UI/UX refresh and responsive mobile layout")
    if "api" in lower_content or "backend" in lower_content or "fastapi" in lower_content or "node" in lower_content:
        pain_points.append("Scalable API endpoints and database optimization")
    if not pain_points:
        pain_points.append("Full-stack engineering & scalable web infrastructure")
        pain_points.append("Clean, maintainable, production-grade code")

    # Company or role recognition
    clean_target = title
    if "|" in title:
        parts = [p.strip() for p in title.split("|")]
        company = parts[0]
        role = parts[1] if len(parts) > 1 else "Engineering"
        clean_target = f"{company}'s {role} opening"
        lead_name = f"{company} Team"
    elif "new comment by" in title.lower():
        clean_target = "your engineering requirements"
        lead_name = "Hiring Team"
    else:
        clean_target = title[:45].strip()
        lead_name = "there"

    # Contextual critique without broken URLs
    critique_str = ""
    if website_url and audit_data and audit_data.get("critiques") and "." in website_url:
        critique_str = f"I reviewed {website_url} and identified opportunities to optimize performance: {audit_data['critiques'][0].lower()}."
    else:
        critique_str = f"My engineering approach focuses on sub-second Core Web Vitals, high conversion, and maintainable architecture for {pain_points[0].lower()}."

    subject = f"Regarding {clean_target[:35]}"
    
    body = (
        f"Hi {lead_name},\n\n"
        f"I noticed your requirement regarding {clean_target} and wanted to reach out.\n\n"
        f"{critique_str} I specialize in full-stack Next.js and resilient backend systems, helping teams deploy polished, production-grade software without accumulating technical debt.\n\n"
        f"You can review several of my recent client builds here: {links['portfolio_url']}.\n\n"
        f"Would you be open to a brief 10-minute introductory call this week? Feel free to pick a convenient slot here: {links['calendly_url']}.\n\n"
        f"Best regards,\n{links['sender_name']}"
    )

    return {
        "is_hiring": is_hiring,
        "lead_name": lead_name,
        "pain_points": pain_points,
        "audit_summary": f"Identified core focus: {', '.join(pain_points)}. {critique_str}",
        "subject_line": subject,
        "email_body": body
    }

async def analyze_inbound_reply(
    lead_context: str,
    inbound_subject: str,
    inbound_body: str
) -> Dict[str, Any]:
    """
    Analyzes client reply sentiment using Gemini 2.5 Flash and drafts a follow-up response.
    Classifications: 'INTERESTED', 'SCHEDULING', 'NOT_INTERESTED', 'OBJECTION', 'NEUTRAL'
    """
    api_key = get_effective_gemini_api_key()
    links = get_effective_links()

    prompt = f"""
You are the AI follow-up specialist for AutoLead AI.
Analyze the following client reply to an outreach email.

ORIGINAL OUTREACH CONTEXT:
{lead_context}

INCOMING CLIENT EMAIL:
Subject: {inbound_subject}
Body:
{inbound_body}

Your Tasks:
1. Classify sentiment: MUST BE one of ['INTERESTED', 'SCHEDULING', 'NOT_INTERESTED', 'OBJECTION', 'NEUTRAL'].
2. If INTERESTED or SCHEDULING: Draft a professional, courteous reply confirming availability, proposing 2 realistic timeslots, and providing the Calendly link: {links['calendly_url']}.
3. If OBJECTION: Draft a helpful, polite clarification addressing their concern without being pushy.
4. If NOT_INTERESTED: Draft a brief, polite acknowledgment ("Understood, thanks for letting me know. Wish you the best!").
5. Return JSON only:
{{
  "sentiment": "INTERESTED",
  "reasoning": "brief explanation",
  "auto_reply_draft": "drafted response email"
}}
"""

    if api_key:
        try:
            client = genai.Client(api_key=api_key)
            config = types.GenerateContentConfig(
                response_mime_type="application/json",
                temperature=0.3,
            )
            response = None
            for model_candidate in ["gemini-3.8-flash", "gemini-2.5-flash", "gemini-flash-latest"]:
                try:
                    response = client.models.generate_content(
                        model=model_candidate,
                        contents=prompt,
                        config=config
                    )
                    if response and response.text:
                        break
                except Exception as me:
                    logger.warning(f"Reply model {model_candidate} notice: {me}")
                    continue

            if not response or not response.text:
                raise ValueError("No response generated from Gemini models")

            text_output = response.text.strip()
            if text_output.startswith("```json"):
                text_output = text_output[7:]
            if text_output.startswith("```"):
                text_output = text_output[3:]
            if text_output.endswith("```"):
                text_output = text_output[:-3]
            
            data = json.loads(text_output.strip())
            return {
                "sentiment": data.get("sentiment", "INTERESTED"),
                "auto_reply_draft": data.get("auto_reply_draft", ""),
                "reasoning": data.get("reasoning", "")
            }
        except Exception as e:
            logger.error(f"Gemini reply analysis error: {e}")

    # Fallback sentiment analysis
    lower_body = inbound_body.lower()
    if any(w in lower_body for w in ["yes", "interested", "lets talk", "let's talk", "call", "schedule", "portfolio", "rate"]):
        sentiment = "INTERESTED"
        draft = (
            f"Hi,\n\n"
            f"Thanks for getting back to me! I'd love to chat through your requirements.\n\n"
            f"Would tomorrow afternoon work for a quick 15-minute call? Alternatively, feel free to pick any slot that fits your schedule here: {links['calendly_url']}.\n\n"
            f"Looking forward to speaking,\n{links['sender_name']}"
        )
    elif any(w in lower_body for w in ["no", "not interested", "unsubscribe", "stop", "already hired"]):
        sentiment = "NOT_INTERESTED"
        draft = f"Thanks for letting me know! Wishing you all the best with your project.\n\nBest,\n{links['sender_name']}"
    else:
        sentiment = "NEUTRAL"
        draft = (
            f"Hi,\n\n"
            f"Thanks for your message. Happy to answer any questions or share more details whenever convenient.\n\n"
            f"Best,\n{links['sender_name']}"
        )

    return {
        "sentiment": sentiment,
        "auto_reply_draft": draft,
        "reasoning": "Determined via pattern heuristics"
    }

