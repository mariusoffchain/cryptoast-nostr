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
import ssl
import time
from pathlib import Path

from pynostr.key import PrivateKey
from pynostr.event import Event
from pynostr.relay_manager import RelayManager

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
#
# Chaque entrée : (label lisible, [mots-clés cherchés dans les tags RSS]).
# Correspondance insensible à la casse, partielle (substring).
# Un seul mot-clé qui matche → article publié.
#
# Pour voir les tags bruts reçus par le feed, ajoute DEBUG_TAGS=true
# dans les variables d'environnement du workflow GitHub Actions.

ALLOWED_CATEGORIES = [
    ("Bitcoin",            ["bitcoin"]),
    ("Blockchain",         ["blockchain"]),
    ("Minage",             ["minage", "mining", "mineur"]),
    ("Économie & Finance", ["économie", "finance", "macro", "marché", "bourse",
                            "economie", "etf", "institutionnel"]),
    ("Régulation",         ["régulation", "regulation", "réglementation",
                            "reglementation", "juridique", "loi", "sec", "mica",
                            "amf", "politique"]),
    ("Analyse prix",       ["analyse", "prix", "cours", "price", "bull", "bear",
                            "technique", "résistance", "support", "halving"]),
    ("Analyse on-chain",   ["on-chain", "onchain", "mempool", "hashrate",
                            "difficulté", "glassnode", "cryptoquant"]),
    ("Dossiers",           ["dossier"]),
    ("Tribunes",           ["tribune"]),
]


# ── Filtre ─────────────────────────────────────────────────────────────────

def get_entry_categories(entry) -> list:
    """Retourne les catégories/tags d'une entrée RSS en minuscules."""
    tags = entry.get("tags", [])
    categories = [t.get("term", "").lower() for t in tags]
    raw_cat = entry.get("category", "")
    if raw_cat:
        categories.append(raw_cat.lower())
    return categories


def is_allowed(entry):
    """
    Retourne (True, label) si l'article passe le filtre,
    (False, '') sinon.
    """
    entry_categories = get_entry_categories(entry)
    for label, keywords in ALLOWED_CATEGORIES:
        for kw in keywords:
            if any(kw in cat for cat in entry_categories):
                return True, label
    return False, ""


# ── Helpers ────────────────────────────────────────────────────────────────

def strip_html(text):
    text = re.sub(r"<[^>]+>", "", text)
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
    private_key = PrivateKey.from_nsec(nsec)
    relay_manager = RelayManager(error_threshold=4, timeout=10)
    for relay in RELAYS:
        relay_manager.add_relay(relay)
    relay_manager.open_connections({"cert_reqs": ssl.CERT_NONE})
    time.sleep(3)
    event = Event(content=content)
    private_key.sign_event(event)
    relay_manager.publish_event(event)
    time.sleep(3)
    relay_manager.close_connections()


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

    entries = list(reversed(feed.entries))[:1]  # TEST : 1 seul article
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
            posted.add(link)  # mémorise pour ne pas re-tester
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
