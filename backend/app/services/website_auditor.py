import time
import httpx
from bs4 import BeautifulSoup
from typing import Dict, Any, Optional

async def audit_website(url: str) -> Optional[Dict[str, Any]]:
    """
    Fetches basic metadata, checks response time, SSL, and mobile readiness.
    Generates 2 actionable improvement critiques.
    Returns None if URL is invalid or malformed (e.g. 'https:///').
    """
    if not url:
        return None

    clean_domain = url.replace("https://", "").replace("http://", "").strip("/")
    if "." not in clean_domain or len(clean_domain) < 4 or "/" in clean_domain.split(".")[0]:
        return None

    if not url.startswith("http://") and not url.startswith("https://"):
        url = "https://" + url

    start_time = time.time()
    result = {
        "url": url,
        "is_accessible": False,
        "response_time_ms": 0,
        "has_ssl": url.startswith("https://"),
        "title": "",
        "has_mobile_viewport": False,
        "critiques": []
    }

    headers = {
        "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36 AutoLeadAudit/1.0"
    }

    try:
        async with httpx.AsyncClient(timeout=8.0, follow_redirects=True, verify=False) as client:
            response = await client.get(url, headers=headers)
            latency = int((time.time() - start_time) * 1000)
            result["response_time_ms"] = latency
            result["status_code"] = response.status_code
            
            if response.status_code < 400:
                result["is_accessible"] = True
                soup = BeautifulSoup(response.text, "html.parser")
                
                title_tag = soup.find("title")
                if title_tag and title_tag.string:
                    result["title"] = title_tag.string.strip()[:100]
                
                viewport_tag = soup.find("meta", attrs={"name": "viewport"})
                result["has_mobile_viewport"] = viewport_tag is not None

                critiques = []
                # Check latency
                if latency > 1200:
                    critiques.append(f"Server response time is {latency}ms (TTFB), causing drop-offs; migrating to a modern edge SSR or static Next.js pipeline would cut this below 300ms.")
                else:
                    critiques.append("Homepage initial load time is reasonable, but asset payload can be streamlined with modern WebP/AVIF imagery and CDN caching.")

                # Check mobile viewport
                if not result["has_mobile_viewport"]:
                    critiques.append("Missing standard mobile viewport meta tag, causing content zooming issues on iOS/Android devices.")
                else:
                    # Check meta description
                    meta_desc = soup.find("meta", attrs={"name": "description"})
                    if not meta_desc or not meta_desc.get("content"):
                        critiques.append("Lacks an optimized meta description tag and OpenGraph preview cards for social & search shareability.")
                    else:
                        critiques.append("Hero section CTA hierarchy can be clarified with modern styling and frictionless micro-interactions to boost visitor conversion rates.")

                result["critiques"] = critiques[:2]
            else:
                result["critiques"] = [
                    f"Site returned HTTP {response.status_code} error during audit, hurting brand trust and user retention.",
                    "Needs an updated, resilient web presence with modern hosting infrastructure."
                ]
    except Exception as e:
        result["critiques"] = [
            f"Website responded slowly or timed out: {str(e)[:80]}. Reliable DNS and modern cloud hosting are needed.",
            "Conversion funnel would benefit from a refreshed, mobile-first Next.js architecture."
        ]

    return result

