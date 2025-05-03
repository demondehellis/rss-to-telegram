import os
import hashlib
import requests
from datetime import datetime

import feedparser
from firebase_admin import initialize_app, firestore
from firebase_functions import scheduler_fn, https_fn, firestore_fn
from flask import Request, Response, jsonify

# Initialize Firebase app
initialize_app()


def add_to_firestore(entries):
    """Stores RSS entries in Firestore"""
    db = firestore.client()
    collection_ref = db.collection("feed")
    
    for entry in entries:
        # Get unique identifier
        guid = getattr(entry, 'id', None) or entry.link
        if not guid:
            continue
            
        # Prepare item data
        item_data = {
            "title": getattr(entry, 'title', ''),
            "link": getattr(entry, 'link', ''),
            "description": getattr(entry, 'description', ''),
            "pubDate": getattr(entry, 'published', ''),
            "guid": guid,
            "fetchedAt": datetime.utcnow().isoformat()
        }
        
        # Store in Firestore
        doc_id = hashlib.md5(guid.encode('utf-8')).hexdigest()
        collection_ref.document(doc_id).set(item_data, merge=True)


def rss_to_firestore():
    """Main function to fetch RSS and store in Firestore"""
    rss_feed_url = os.environ.get("RSS_FEED")
    if not rss_feed_url:
        raise Exception("RSS feed URL not set")

    # Fetch and process entries
    feed = feedparser.parse(rss_feed_url)
    if feed.entries:
        add_to_firestore(feed.entries)


def send_telegram_message(title, description, link):
    """Sends message to Telegram channel"""
    telegram_token = os.environ.get("TELEGRAM_TOKEN")
    telegram_channel = os.environ.get("TELEGRAM_CHANNEL")

    if not telegram_token or not telegram_channel:
        print("Telegram configuration not set")
        return

    message = f"*{title}*\n\n{description}\n\n[Read more]({link})"

    requests.post(
        f"https://api.telegram.org/bot{telegram_token}/sendMessage",
        json={
            "chat_id": telegram_channel,
            "text": message,
            "parse_mode": "Markdown",
            "disable_web_page_preview": False
        }
    )


@scheduler_fn.on_schedule(
    schedule="0 * * * *",  # Run once every hour
    timezone=scheduler_fn.Timezone("UTC")
)
def fetch_rss_on_schedule(event: scheduler_fn.ScheduledEvent) -> None:
    """Scheduled function to fetch RSS and store in Firestore"""
    rss_to_firestore()


@https_fn.on_request()
def fetch_rss_on_request(req: Request) -> Response:
    """HTTP endpoint to manually trigger RSS fetch"""
    try:
        rss_to_firestore()
    except Exception as e:
        return jsonify({"success": False, "error": str(e)})
    return jsonify({"success": True})


@firestore_fn.on_document_created(document="feed/{docId}")
def rss_item_on_created(event: firestore_fn.Event) -> None:
    """Sends new feed items to Telegram"""
    document_data = event.data.to_dict() if event.data else None
    if document_data:
        send_telegram_message(
            document_data.get("title", "No title"),
            document_data.get("description", "No description"),
            document_data.get("link", "")
        )
