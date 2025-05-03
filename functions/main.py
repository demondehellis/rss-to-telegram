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


def fetch_rss(rss_feed_url: str) -> tuple:
    """
    Fetches RSS feed data from the provided URL.

    Args:
        rss_feed_url: URL of the RSS feed to fetch

    Returns:
        tuple: (success, feed_entries, error_message)
    """
    try:
        # Parse RSS feed with feedparser
        feed = feedparser.parse(rss_feed_url)

        # Check if feed has entries
        if not feed.entries:
            print("No items found in RSS feed")
            return True, [], None

        return True, feed.entries, None
    except Exception as e:
        error_msg = f"Error fetching RSS feed: {e}"
        print(error_msg)
        return False, [], error_msg


def store_items(entries: list, collection_name: str = "feed") -> tuple:
    """
    Stores RSS feed entries in Firestore.

    Args:
        entries: List of feed entries to store
        collection_name: Name of the Firestore collection

    Returns:
        tuple: (success, items_added, error_message)
    """
    items_added = 0

    try:
        # Initialize Firestore client
        db = firestore.client()
        collection_ref = db.collection(collection_name)

        # Process each item
        for entry in entries:
            # Use guid or link as unique identifier
            guid = getattr(entry, 'id', None) or entry.link

            # Skip if no unique identifier is available
            if not guid:
                continue

            # Create item data
            item_data = {
                "title": getattr(entry, 'title', ''),
                "link": getattr(entry, 'link', ''),
                "description": getattr(entry, 'description', ''),
                "pubDate": getattr(entry, 'published', ''),
                "guid": guid,
                "fetchedAt": datetime.utcnow().isoformat()
            }

            doc_id = hashlib.md5(guid.encode('utf-8')).hexdigest()
            doc_ref = collection_ref.document(str(doc_id))
            doc_ref.set(item_data, merge=True)
            items_added += 1

        return True, items_added, None
    except Exception as e:
        error_msg = f"Error storing items in Firestore: {e}"
        print(error_msg)
        return False, items_added, error_msg


def _fetch_rss_and_store_impl() -> dict:
    """
    Implementation of RSS fetching and storing logic using feedparser.
    Returns a dictionary with the results of the operation.
    """
    results = {
        "success": True,
        "items_added": 0,
        "items_existing": 0,
        "errors": []
    }

    # Get values from Firebase Functions config
    rss_feed_url = os.environ.get("RSS_FEED")
    collection_name = "feed"

    if not rss_feed_url:
        error_msg = "Error: RSS feed URL not set in Firebase Functions config"
        print(error_msg)
        results["success"] = False
        results["errors"].append(error_msg)
        return results

    # Fetch RSS feed
    success, entries, error = fetch_rss(rss_feed_url)
    if not success:
        results["success"] = False
        results["errors"].append(error)
        return results

    if not entries:
        return results

    # Store items in Firestore
    success, items_added, error = store_items(entries, collection_name)
    if not success:
        results["success"] = False
        results["errors"].append(error)

    results["items_added"] = items_added

    return results


@scheduler_fn.on_schedule(
    schedule="0 * * * *",  # Run once every hour
    timezone=scheduler_fn.Timezone("UTC")
)
def fetch_rss_and_store(event: scheduler_fn.ScheduledEvent) -> None:
    """
    Fetches RSS feed and stores items in Firestore.
    Runs on a schedule (every hour).
    """
    _fetch_rss_and_store_impl()


@https_fn.on_request()
def fetch_rss_http(req: Request) -> Response:
    """
    HTTP endpoint to fetch RSS feed and store items in Firestore.
    Can be called manually for testing.
    """
    results = _fetch_rss_and_store_impl()
    return jsonify(results)


@firestore_fn.on_document_created(document="feed/{docId}")
def send_to_channel(event: firestore_fn.Event) -> None:
    """
    Cloud Function triggered when a new document is created in the 'feed' collection.
    Sends the new item to a Telegram channel using the Telegram Bot API.
    """
    # Get the document data
    document_snapshot = event.data
    if not document_snapshot:
        print("No document data available")
        return

    # Get document data
    document_data = document_snapshot.to_dict()
    if not document_data:
        print("Document data is empty")
        return

    # Extract relevant information
    title = document_data.get("title", "No title")
    link = document_data.get("link", "")
    description = document_data.get("description", "No description")

    # Get Telegram configuration from environment variables
    telegram_token = os.environ.get("TELEGRAM_TOKEN")
    telegram_channel = os.environ.get("TELEGRAM_CHANNEL")

    if not telegram_token or not telegram_channel:
        print("Telegram configuration not set in environment variables")
        return

    # Format message for Telegram
    message = f"*{title}*\n\n{description}\n\n[Read more]({link})"

    # Send message to Telegram
    telegram_api_url = f"https://api.telegram.org/bot{telegram_token}/sendMessage"
    payload = {
        "chat_id": telegram_channel,
        "text": message,
        "parse_mode": "Markdown",
        "disable_web_page_preview": False
    }

    try:
        response = requests.post(telegram_api_url, json=payload)
        response_data = response.json()

        if response.status_code == 200 and response_data.get("ok"):
            print(f"Message sent to Telegram channel {telegram_channel}")
        else:
            print(f"Failed to send message to Telegram: {response_data}")
    except Exception as e:
        print(f"Error sending message to Telegram: {e}")
