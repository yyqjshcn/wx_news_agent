import feedparser
import logging
from datetime import datetime, timezone
from typing import Optional

logger = logging.getLogger(__name__)


def parse_feed(feed_url: str) -> dict:
    """Parse an RSS/Atom feed and return structured data."""
    try:
        feed = feedparser.parse(feed_url)
        
        if feed.bozo and not feed.entries:
            return {
                "success": False,
                "error": f"Feed parse error: {feed.bozo_exception}",
                "title": None,
                "entries": [],
            }
        
        entries = []
        for entry in feed.entries[:50]:
            published = None
            if hasattr(entry, "published_parsed") and entry.published_parsed:
                published = datetime(*entry.published_parsed[:6], tzinfo=timezone.utc)
            elif hasattr(entry, "updated_parsed") and entry.updated_parsed:
                published = datetime(*entry.updated_parsed[:6], tzinfo=timezone.utc)
            
            link = entry.get("link", "")
            if not link and hasattr(entry, "links") and entry.links:
                link = entry.links[0].get("href", "")
            
            content = ""
            if hasattr(entry, "summary"):
                content = entry.summary
            elif hasattr(entry, "content") and entry.content:
                content = entry.content[0].get("value", "")
            
            entries.append({
                "title": entry.get("title", "Untitled"),
                "link": link,
                "author": entry.get("author", ""),
                "published": published,
                "content": content[:500] if content else "",
            })
        
        return {
            "success": True,
            "title": feed.feed.get("title", ""),
            "entries": entries,
        }
    except Exception as e:
        return {
            "success": False,
            "error": str(e),
            "title": None,
            "entries": [],
        }


async def test_feed(feed_url: str) -> dict:
    """Test if an RSS feed is accessible and parseable."""
    result = parse_feed(feed_url)
    return {
        "success": result["success"],
        "title": result.get("title"),
        "article_count": len(result.get("entries", [])),
        "error": result.get("error"),
    }
