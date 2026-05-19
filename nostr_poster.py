"""
Cryptoast → Nostr auto-poster
Lit le feed RSS Cryptoast et publie les nouveaux articles sur Nostr,
en filtrant uniquement les catégories éditoriales souhaitées.

Le nsec est lu depuis la variable d'environnement NOSTR_NSEC (GitHub Secret).
"""

import feedparser
import json
import os
import re
import time
from pathlib import Path

# ── Config ─────────────────────────────────────────────────────────────────

FEED_URL = "https://cryptoast.fr/feed"

RELAYS = [
    "wss://nos.lol",
    "wss://nostr.land",
    "wss://nostr.wine",
    "wss://relay.damus.io",
]

POSTED_FILE = "posted.json"
HASHTAGS = "#nostrfr"
MAX_SUMMARY_CHARS = 400

# ── Filtre catégories ───────────────────────────────────────────────────────
# Correspondance exacte sur les noms de catégories Cryptoast (insensible casse)

ALLOWED_CATEGORIES = {
    "actualité de la blockchain",
    "actu de la crypto",
    "actualité des exchanges",
    "actualité du bitcoin (btc)",
    "actualité du minage",
    "actualité du ripple (xrp)",
    "actualité économie et finance",
    "actualité régulation crypto",
    "analyse du prix du bitcoin et des crypto-monnaies",
    "analyse on-chain",
    "dossiers",
    "tribunes",
    "zone innovation",
    "analyses de cryptomonnaies",
    "crypto brunch",
    "cryptoast",
    "développement blockchain",
    "blockchain",
    "bourse",
    "defi : finance décentralisée",
    "droit et fiscalité",
    "exchanges crypto",
    "formation bitcoin",
    "guide sur le trading",
    "minage, masternodes et staking",
    "personnalités cryptos",
    "sécurité et stockage",
    "investissement",
    "le récap' crypto",
    "podcast crypto-monnaies",
    "tutos cryptos",
    "vidéos cryptos",
}

BLOCKED_TAGS = {"sponso", "no pub", "partenariat"}


# ── Filtre ─────────────────────────────────────────────────────────────────

def get_entry_categories(entry):
    tags = entry.get("tags", [])
    categories = [t.get("term", "").lower() for t in tags]
    raw_cat = entry.get("category", "")
    if raw_cat:
        categories.append(raw_cat.lower())
    return categories


def is_allowed(entry):
    entry_categories = get_entry_categories(entry)

    for blocked in BLOCKED_TAGS:
        if blocked in entry_categories:
            return False, ""

    for cat in entry_categories:
        if cat in ALLOWED_CATEGORIES:
            return True, cat.title()

    return False, ""


# ── Helpers ────────────────────────────────────────────────────────────────

def strip_html(text):
    import html
    text = re.sub(r"<[^>]+>", "", text)
    text = html.unescape(text)
    text = re.sub(r"L.article\s+.+?\s+est apparu en premier sur \w+\.", "", text, flags=re.DOTALL)
    text = re.sub(r"\s+", " ", text)
    return text.strip()


def load_posted():
    if Path(POSTED_FILE).exists():
        with open(POSTED_FILE, encoding="utf-8") as f:
            return set(json.load(f))
    return set()


def save_posted(posted):
    with open(POSTED_FILE, "w", encoding="utf-8") as f:
        json.dump(sorted(posted), f, indent=2)


def build_note(entry):
    title = strip_html(entry.get("title", "")).strip()
    summary_raw = entry.get("summary", "") or entry.get("description", "")
    summary = strip_html(summary_raw).strip()
    if len(summary) > MAX_SUMMARY_CHARS:
        summary = summary[:MAX_SUMMARY_CHARS].rsplit(" ", 1)[0] + "…"
    link = entry.get("link", "").strip()

    parts = [f"📰 {title}"]
    if summary:
        parts.append(summary)
    parts.append(f"👉 {link}")
    parts.append(HASHTAGS)
    return "\n\n".join(parts)


# ── Nostr ──────────────────────────────────────────────────────────────────

def publish_note(content, nsec):
    from nostr_sdk import Client, Keys, NostrSigner, EventBuilder
    import asyncio

    async def _publish():
        keys = Keys.parse(nsec)
        signer = NostrSigner.keys(keys)
        client = Client(signer)
        for relay in RELAYS:
            await client.add_relay(relay)
        await client.connect()
        await asyncio.sleep(2)
        builder = EventBuilder.text_note(content, [])
        await client.send_event_builder(builder)
        await asyncio.sleep(2)
        await client.disconnect()

    asyncio.run(_publish())


# ── Main ───────────────────────────────────────────────────────────────────

def main():
    nsec = os.environ.get("NOSTR_NSEC", "").strip()
    if not nsec:
        raise EnvironmentError("Variable NOSTR_NSEC manquante.")

    debug_tags = os.environ.get("DEBUG_TAGS", "").lower() == "true"
    posted = load_posted()

    print(f"Lecture du feed : {FEED_URL}")
    feed = feedparser.parse(
        FEED_URL,
        request_headers={"User-Agent": "Feedly/1.0 (compatible RSS reader)"},
    )

    if feed.bozo:
        print(f"Avertissement RSS : {feed.bozo_exception}")

    entries = list(reversed(feed.entries))
    published = skipped_cat = skipped_posted = 0

    for entry in entries:
        link = entry.get("link", "")
        title = entry.get("title", "(sans titre)")

        if link in posted:
            skipped_posted += 1
            continue

        allowed, matched_category = is_allowed(entry)

        if debug_tags:
            cats = get_entry_categories(entry)
            status = f"✓ {matched_category}" if allowed else "✗ ignoré"
            print(f"[DEBUG] {title}\n        tags: {cats} → {status}\n")

        if not allowed:
            skipped_cat += 1
            posted.add(link)
            continue

        note = build_note(entry)
        print(f"\n→ [{matched_category}] {title}")

        try:
            publish_note(note, nsec)
            posted.add(link)
            published += 1
            print("  ✓ Publié.")
        except Exception as e:
            print(f"  ✗ Erreur : {e}")

        time.sleep(3)

    save_posted(posted)
    print(f"\nTerminé — {published} publié(s) | {skipped_cat} hors catégorie | {skipped_posted} déjà postés.")


if __name__ == "__main__":
    main()
