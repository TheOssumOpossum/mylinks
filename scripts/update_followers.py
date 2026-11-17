#!/usr/bin/env python3
"""Fetch TikTok / Instagram follower counts and update the pills in index.html.

Each platform is best-effort: if a count can't be retrieved, that platform is
skipped and its existing value in index.html is left untouched.
"""
import json
import re
import sys
import urllib.parse
import urllib.request
from pathlib import Path

INDEX = Path(__file__).resolve().parent.parent / "index.html"
UA = "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0 Safari/537.36"


def fetch(url):
    req = urllib.request.Request(url, headers={"User-Agent": UA, "Accept-Language": "en-US,en;q=0.9"})
    with urllib.request.urlopen(req, timeout=30) as r:
        return r.read().decode("utf-8", "replace")


def tiktok(username):
    page = fetch(f"https://www.tiktok.com/@{username}")
    m = re.search(r'"followerCount":(\d+)', page)
    return int(m.group(1)) if m else None


LINKTREE = "https://linktr.ee/vinnybonbon"


def _find_instagram_link(node):
    """Walk the Linktree page data for the INSTAGRAM_PROFILE link."""
    if isinstance(node, dict):
        if node.get("type") == "INSTAGRAM_PROFILE" and node.get("context", {}).get("integrationId"):
            return node
        node = list(node.values())
    if isinstance(node, list):
        for v in node:
            found = _find_instagram_link(v)
            if found:
                return found
    return None


def instagram(_username):
    """Read the count Linktree shows for the Instagram link on linktr.ee/vinnybonbon."""
    page = fetch(LINKTREE)
    m = re.search(r'<script id="__NEXT_DATA__"[^>]*>(.*?)</script>', page, re.S)
    if not m:
        print("Instagram: no page data found on Linktree page")
        return None
    data = json.loads(m.group(1))
    link = _find_instagram_link(data)
    uuid = data.get("props", {}).get("pageProps", {}).get("account", {}).get("uuid")
    if not link or not uuid:
        print("Instagram: Instagram link not found on Linktree page")
        return None
    qs = urllib.parse.urlencode({
        "instagramBusinessIntegrationId": link["context"]["integrationId"],
        "linkId": link["id"],
        "accountUuid": uuid,
    })
    resp = json.loads(fetch(f"https://linktr.ee/api/instagram-business/instagram-profile?{qs}"))
    count = resp.get("user", {}).get("followersCount")
    if not count:
        resp.pop("posts", None)
        print(f"Instagram: Linktree replied without a count: {json.dumps(resp)[:300]}")
        return None
    return int(count)


def abbreviate(n):
    if n >= 1_000_000:
        return f"{n / 1_000_000:.1f}M".replace(".0M", "M")
    if n >= 1_000:
        return f"{n / 1_000:.1f}K".replace(".0K", "K")
    return str(n)


def main():
    text = INDEX.read_text()
    new = text
    failed = []
    for name, fn, user, var in [
        ("TikTok", tiktok, "spreadsheetnerd", "tiktokFollowers"),
        ("Instagram", instagram, "vinnyvinnybonbon", "instagramFollowers"),
    ]:
        try:
            count = fn(user)
        except Exception as e:  # network error, block, etc.
            print(f"{name}: fetch failed ({e}); skipping")
            failed.append(name)
            continue
        if not count:
            print(f"{name}: count not found; skipping")
            failed.append(name)
            continue
        label = abbreviate(count)
        print(f"{name}: {count} -> {label}")
        new, n = re.subn(rf"(const {var} = ')[^']*(';)", rf"\g<1>{label}\g<2>", new)
        if n != 1:
            sys.exit(f"Could not find `const {var}` in index.html")
    if new != text:
        INDEX.write_text(new)
        print("index.html updated")
    else:
        print("No changes")
    if failed:
        # Counts that did load are already saved above; exit non-zero so the run shows as failed.
        sys.exit(f"Failed to read follower count for: {', '.join(failed)}")


if __name__ == "__main__":
    main()
