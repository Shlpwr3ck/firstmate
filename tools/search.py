"""Web search and fetch tools."""
import httpx
import re


def web_search(query: str) -> str:
    try:
        r = httpx.get(
            'https://api.duckduckgo.com/',
            params={'q': query, 'format': 'json', 'no_html': '1', 'skip_disambig': '1'},
            timeout=10
        )
        data = r.json()
        results = []
        if data.get('AbstractText'):
            results.append(f"Summary: {data['AbstractText']}")
        for topic in data.get('RelatedTopics', [])[:5]:
            if isinstance(topic, dict) and topic.get('Text'):
                results.append(f"• {topic['Text']}")
        if not results:
            return f"No instant results for '{query}'. Try fetch_webpage with a specific URL."
        return '\n'.join(results)
    except Exception as e:
        return f"Search error: {e}"


def fetch_webpage(url: str) -> str:
    try:
        r = httpx.get(url, timeout=15, follow_redirects=True,
                      headers={'User-Agent': 'Mozilla/5.0'})
        text = re.sub(r'<[^>]+>', ' ', r.text)
        text = re.sub(r'\s+', ' ', text).strip()
        if len(text) > 5000:
            text = text[:5000] + '\n[...truncated]'
        return text
    except Exception as e:
        return f"Fetch error: {e}"
