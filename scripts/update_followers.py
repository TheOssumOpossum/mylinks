#!/usr/bin/env python3
"""Fetch TikTok / Instagram follower counts and update the pills in index.html.

Each platform is best-effort: if a count can't be retrieved, that platform is
skipped and its existing value in index.html is left untouched.
"""
import http.cookiejar
import json
import re
import sys
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


def instagram(username):
    """Use blastup.com's public follower-count tool (same flow its web page uses)."""
    base = "https://blastup.com/instagram-follower-count"
    jar = http.cookiejar.CookieJar()
    opener = urllib.request.build_opener(urllib.request.HTTPCookieProcessor(jar))
    req = urllib.request.Request(base, headers={"User-Agent": UA})
    page = opener.open(req, timeout=30).read().decode("utf-8", "replace")
    tok = re.search(r'token:\s*"([^"]+)"', page)
    if not tok:
        print("Instagram: no token found on blastup page (page may have changed or been blocked)")
        return None
    body = json.dumps({"_token": tok.group(1), "username": username}).encode()
    req = urllib.request.Request(base, data=body, headers={
        "User-Agent": UA, "Content-Type": "application/json",
        "Accept": "application/json", "Referer": base,
    })
    data = json.loads(opener.open(req, timeout=60).read())
    if not data.get("success"):
        data.pop("profile_picture", None)
        print(f"Instagram: blastup replied without a count: {json.dumps(data)[:300]}")
        return None
    return int(data["followers"])


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
