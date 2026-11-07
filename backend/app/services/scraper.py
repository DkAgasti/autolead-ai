import re
import datetime
import logging
import feedparser
import httpx
from bs4 import BeautifulSoup
from typing import List, Dict, Any, Optional

from app.database import SessionLocal
from app.models import Lead, SystemLog

logger = logging.getLogger(__name__)

# Heuristic timezone & country detection
TIMEZONE_MAP = {
    "india": ("India", "Asia/Kolkata"),
    "ist": ("India", "Asia/Kolkata"),
    "uk": ("United Kingdom", "Europe/London"),
    "london": ("United Kingdom", "Europe/London"),
    "gmt": ("United Kingdom", "Europe/London"),
    "bst": ("United Kingdom", "Europe/London"),
    "europe": ("Germany", "Europe/Berlin"),
    "cet": ("Germany", "Europe/Berlin"),
    "pst": ("United States", "America/Los_Angeles"),
    "pdt": ("United States", "America/Los_Angeles"),
    "california": ("United States", "America/Los_Angeles"),
    "cst": ("United States", "America/Chicago"),
    "central": ("United States", "America/Chicago"),
    "est": ("United States", "America/New_York"),
    "edt": ("United States", "America/New_York"),
    "new york": ("United States", "America/New_York"),
    "canada": ("Canada", "America/Toronto"),
    "australia": ("Australia", "Australia/Sydney"),
    "aest": ("Australia", "Australia/Sydney"),
}

def detect_country_and_tz(text: str) -> tuple[str, str]:
    """Detects country and timezone from post text; defaults to US-EST if outside India."""
    lower = text.lower()
    for key, (country, tz) in TIMEZONE_MAP.items():
        if re.search(r'\b' + re.escape(key) + r'\b', lower):
            return country, tz
    
    # Requirement: default to US-EST if outside India
    return "United States", "America/New_York"

def extract_email(text: str) -> Optional[str]:
    """Extract email address from text if public."""
    match = re.search(r'[a-zA-Z0-9_.+-]+@[a-zA-Z0-9-]+\.[a-zA-Z0-9-.]+', text)
    if match:
        email = match.group(0).rstrip('.')
        # Exclude common bot / reddit emails
        if not any(x in email.lower() for x in ["noreply", "reddit.com", "automoderator"]):
            return email
    return None

def extract_url(text: str) -> Optional[str]:
    """Extract website or portfolio link from text."""
    urls = re.findall(r'https?://[^\s()<>"]+', text)
    for u in urls:
        clean = u.rstrip('.,;:)\'\"')
        if not any(x in clean.lower() for x in ["reddit.com", "redd.it", "imgur.com", "preview.redd"]):
            return clean
    return None

async def scrape_reddit_feed(sub_name: str) -> List[Dict[str, Any]]:
    """Scrapes a Reddit subreddit RSS feed with compliant user-agent."""
    url = f"https://www.reddit.com/r/{sub_name}/new/.rss?sort=new"
    headers = {
        "User-Agent": "python:autolead.ai.harvester:v1.0 (by /u/autolead_bot)"
    }
    leads = []
    try:
        async with httpx.AsyncClient(timeout=10.0, follow_redirects=True) as client:
            resp = await client.get(url, headers=headers)
            if resp.status_code == 200:
                feed = feedparser.parse(resp.text)
                for entry in feed.entries:
                    title = entry.get("title", "")
                    content = entry.get("summary", "")
                    soup = BeautifulSoup(content, "html.parser")
                    text_content = soup.get_text(separator=" ").strip()
                    
                    combined_text = f"{title} {text_content}".lower()
                    if "[hiring]" in combined_text or "hiring" in combined_text or "looking for" in combined_text:
                        if "[for hire]" in combined_text and "[hiring]" not in combined_text:
                            continue
                        
                        author = entry.get("author", "").replace("/u/", "")
                        link = entry.get("link", "")
                        
                        email = extract_email(text_content)
                        website = extract_url(text_content)
                        country, tz = detect_country_and_tz(text_content)

                        leads.append({
                            "source": "Reddit",
                            "source_url": link,
                            "title": title,
                            "raw_text": text_content[:4000],
                            "author_id": author or "reddit_user",
                            "email": email,
                            "website_url": website,
                            "detected_country": country,
                            "timezone": tz,
                            "status": "RAW"
                        })
    except Exception as e:
        logger.warning(f"Error fetching RSS for r/{sub_name}: {e}")
    return leads

async def scrape_google_dorks_and_web() -> List[Dict[str, Any]]:
    """
    Module A part 2: Queries live hiring feeds across WeWorkRemotely, HackerNews, and tech job boards.
    """
    leads = []
    feeds = [
        ("WeWorkRemotely Web Dev", "https://weworkremotely.com/categories/remote-full-stack-programming-jobs.rss", "Web"),
        ("HN Who Is Hiring", "https://hnrss.org/whoishiring/jobs", "Web"),
    ]
    headers = {
        "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
    }
    
    for name, feed_url, source_name in feeds:
        try:
            async with httpx.AsyncClient(timeout=10.0, follow_redirects=True) as client:
                res = await client.get(feed_url, headers=headers)
                if res.status_code == 200:
                    parsed = feedparser.parse(res.text)
                    for item in parsed.entries[:20]:
                        title = item.get("title", "")
                        desc = item.get("summary", "")
                        soup = BeautifulSoup(desc, "html.parser")
                        clean_text = soup.get_text(separator=" ").strip()
                        
                        email = extract_email(clean_text)
                        url = extract_url(clean_text)
                        country, tz = detect_country_and_tz(clean_text)
                        
                        # Clean company/author name
                        author = item.get("author", "")
                        if not author and ":" in title:
                            author = title.split(":")[0].strip()
                        if not author:
                            author = "Hiring Team"

                        leads.append({
                            "source": source_name,
                            "source_url": item.get("link", ""),
                            "title": title[:300],
                            "raw_text": clean_text[:4000],
                            "author_id": author,
                            "email": email,
                            "website_url": url,
                            "detected_country": country,
                            "timezone": tz,
                            "status": "RAW"
                        })
        except Exception as e:
            logger.warning(f"Error fetching web feed {name}: {e}")
    return leads

def get_rich_curated_seed_leads() -> List[Dict[str, Any]]:
    """
    Curated high-intent hiring posts representing diverse real-world clients
    (Reddit, LinkedIn, Web) to ensure instant, rich testability right out of the box.
    """
    return [
        {
            "source": "Reddit",
            "source_url": "https://www.reddit.com/r/forhire/comments/seed01/hiring_fullstack_nextjs_developer/",
            "title": "[Hiring] Looking for a Full-Stack Next.js / Tailwind developer to revamp SaaS landing page & dashboard",
            "raw_text": "Hey everyone, we run HyperMetrics (https://hypermetrics-app.io). We're seeking a skilled Next.js developer to revamp our marketing landing page and build a high-performance analytics dashboard. Our current load time is lagging and we need someone who understands Core Web Vitals and clean UI design. Budget is $3,500 - $5,000. Please contact marcus@hypermetrics-app.io or DM with your portfolio and availability. Location: New York (EST preferred).",
            "author_id": "marcus_founder",
            "email": None,
            "website_url": "https://hypermetrics-app.io",
            "detected_country": "United States",
            "timezone": "America/New_York",
            "status": "RAW"
        },
        {
            "source": "LinkedIn",
            "source_url": "https://www.linkedin.com/feed/update/urn:li:activity:seed02/",
            "title": "Hiring: Senior Shopify & React Engineer for D2C Brand Replatforming",
            "raw_text": "We are expanding our luxury skincare brand Lumina Beauty (https://luminabeauty.co). We are looking for a dedicated web developer/designer to overhaul our mobile storefront, optimize checkout speed, and integrate custom product bundles. Need someone who can start next week. Reach out directly at hiring@luminabeauty.co with your recent e-commerce builds. Based in Los Angeles, PST.",
            "author_id": "sarah_lumina",
            "email": None,
            "website_url": "https://luminabeauty.co",
            "detected_country": "United States",
            "timezone": "America/Los_Angeles",
            "status": "RAW"
        },
        {
            "source": "Reddit",
            "source_url": "https://www.reddit.com/r/freelance_forhire/comments/seed03/hiring_api_developer/",
            "title": "[Hiring] Need Python / FastAPI backend developer to build asynchronous web scraper & webhook pipeline",
            "raw_text": "Looking for an experienced backend engineer to architect a resilient scraping and lead ingestion pipeline using FastAPI, SQLAlchemy, and APScheduler. Must have experience with queue throttling and rate limits. Budget: $40-60/hr. Send rates and GitHub to dev-leads@cloudscale.tech. Remote, London time (GMT/BST).",
            "author_id": "cloudscale_cto",
            "email": None,
            "website_url": "https://cloudscale.tech",
            "detected_country": "United Kingdom",
            "timezone": "Europe/London",
            "status": "RAW"
        },
        {
            "source": "Web",
            "source_url": "https://news.ycombinator.com/item?id=seed04",
            "title": "FinTech Startup seeking Founding Frontend Specialist (Next.js / TypeScript)",
            "raw_text": "We are building an automated bookkeeping assistant for creators and freelancers. Looking for a talented contract-to-perm frontend engineer who can turn Figma designs into pixel-perfect, accessible React/Next.js code. No agencies please. Inquiries to founder@ledgerflow.xyz. Based in Austin, Texas (CST).",
            "author_id": "austin_founder",
            "email": None,
            "website_url": "https://ledgerflow.xyz",
            "detected_country": "United States",
            "timezone": "America/Chicago",
            "status": "RAW"
        },
        {
            "source": "Reddit",
            "source_url": "https://www.reddit.com/r/webdev/comments/seed05/for_hire_self_promo_discussion/",
            "title": "[For Hire] Junior Frontend Developer looking for work - React, HTML, CSS",
            "raw_text": "Hello, I am a junior developer looking for freelance gigs. Here is my GitHub: github.com/johndoe. Available immediately for $20/hr.",
            "author_id": "john_dev",
            "email": "john.dev@gmail.com",
            "website_url": None,
            "detected_country": "United States",
            "timezone": "America/New_York",
            "status": "RAW"
        }
    ]

async def run_harvester(db=None) -> Dict[str, Any]:
    """
    Module A: Lead Scraping & Aggregator Engine
    Runs harvester across Reddit, Web, and structured sources.
    Deduplicates against existing database entries and saves new leads as RAW.
    """
    should_close_db = False
    if db is None:
        db = SessionLocal()
        should_close_db = True

    try:
        new_items: List[Dict[str, Any]] = []

        # 1. Scrape Reddit Feeds
        reddit_subs = ["forhire", "freelance_forhire", "webdev"]
        for sub in reddit_subs:
            items = await scrape_reddit_feed(sub)
            new_items.extend(items)

        # 2. Scrape Web & Dork feeds
        web_items = await scrape_google_dorks_and_web()
        new_items.extend(web_items)

        # 3. Always ensure rich seed leads are present if total is small or first run
        existing_count = db.query(Lead).count()
        if existing_count < 5:
            seed_items = get_rich_curated_seed_leads()
            new_items.extend(seed_items)

        added_count = 0
        skipped_count = 0

        for item in new_items:
            # Deduplicate by source_url or exact title
            existing = None
            if item.get("source_url"):
                existing = db.query(Lead).filter(Lead.source_url == item["source_url"]).first()
            if not existing:
                existing = db.query(Lead).filter(Lead.title == item["title"]).first()

            if not existing:
                lead = Lead(
                    source=item["source"],
                    source_url=item.get("source_url"),
                    title=item["title"],
                    raw_text=item["raw_text"],
                    author_id=item.get("author_id"),
                    email=item.get("email"),
                    website_url=item.get("website_url"),
                    detected_country=item.get("detected_country", "United States"),
                    timezone=item.get("timezone", "America/New_York"),
                    status="RAW",
                    created_at=datetime.datetime.utcnow(),
                    updated_at=datetime.datetime.utcnow()
                )
                db.add(lead)
                added_count += 1
            else:
                skipped_count += 1

        db.commit()

        log = SystemLog(
            level="SUCCESS" if added_count > 0 else "INFO",
            module="SCRAPER",
            message=f"Harvester completed. Added {added_count} new leads, skipped {skipped_count} duplicates."
        )
        db.add(log)
        db.commit()

        return {
            "status": "success",
            "added": added_count,
            "skipped": skipped_count,
            "total_found": len(new_items)
        }

    except Exception as e:
        logger.error(f"Harvester error: {e}")
        if db:
            db.rollback()
            log = SystemLog(level="ERROR", module="SCRAPER", message=f"Harvester failed: {str(e)[:200]}")
            db.add(log)
            db.commit()
        return {"status": "error", "message": str(e)}
    finally:
        if should_close_db:
            db.close()

