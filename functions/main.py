import os
import hashlib
from datetime import datetime

import feedparser
from firebase_admin import initialize_app, firestore
from firebase_functions import scheduler_fn, https_fn
from flask import Request, Response, jsonify

# Initialize Firebase app
initialize_app()


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

    try:
        # Parse RSS feed with feedparser
        feed = feedparser.parse(rss_feed_url)
        
        # Check if feed has entries
        if not feed.entries:
            print("No items found in RSS feed")
            return results
            
        # Initialize Firestore client
        db = firestore.client()
        collection_ref = db.collection(collection_name)
        
        # Process each item
        for entry in feed.entries:
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
            results["items_added"] += 1
            
    except Exception as e:
        error_msg = f"Error processing RSS feed: {e}"
        print(error_msg)
        results["success"] = False
        results["errors"].append(error_msg)
        
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