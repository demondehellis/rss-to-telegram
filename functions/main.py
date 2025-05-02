# Welcome to Cloud Functions for Firebase for Python!
# Deploy with `firebase deploy`

import os
import xml.etree.ElementTree as ET
from datetime import datetime

import hashlib
import requests
from firebase_admin import initialize_app, firestore
from firebase_functions import scheduler_fn, https_fn
from flask import Request, Response, jsonify

# Initialize Firebase app
initialize_app()


def _fetch_rss_and_store_impl() -> dict:
    """
    Implementation of RSS fetching and storing logic.
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
        # Fetch RSS feed
        response = requests.get(rss_feed_url)
        response.raise_for_status()  # Raise exception for HTTP errors

        # Parse XML
        root = ET.fromstring(response.content)

        # Find the namespace if it exists
        namespace = ""
        if root.tag.startswith("{"):
            namespace = root.tag.split("}")[0] + "}"

        # Get channel element
        channel = root.find(f"{namespace}channel")
        if channel is None:
            error_msg = "Error: Could not find channel element in RSS feed"
            print(error_msg)
            results["success"] = False
            results["errors"].append(error_msg)
            return results

        # Get items
        items = channel.findall(f"{namespace}item")
        if not items:
            print("No items found in RSS feed")
            return results

        # Initialize Firestore client
        db = firestore.client()
        collection_ref = db.collection(collection_name)

        # Process each item
        for item in items:
            # Extract item data
            title_elem = item.find(f"{namespace}title")
            link_elem = item.find(f"{namespace}link")
            description_elem = item.find(f"{namespace}description")
            pub_date_elem = item.find(f"{namespace}pubDate")
            guid_elem = item.find(f"{namespace}guid")

            # Skip if required fields are missing
            if guid_elem is None or title_elem is None:
                continue

            guid = guid_elem.text

            # Create item data
            item_data = {
                "title": title_elem.text if title_elem is not None else "",
                "link": link_elem.text if link_elem is not None else "",
                "description": description_elem.text if description_elem is not None else "",
                "pubDate": pub_date_elem.text if pub_date_elem is not None else "",
                "guid": guid,
                "fetchedAt": datetime.utcnow().isoformat()
            }

            doc_id = hashlib.md5(guid.encode('utf-8')).hexdigest()
            doc_ref = collection_ref.document(str(doc_id))
            doc_ref.set(item_data, merge=True)

    except requests.RequestException as e:
        error_msg = f"Error fetching RSS feed: {e}"
        print(error_msg)
        results["success"] = False
        results["errors"].append(error_msg)
    except ET.ParseError as e:
        error_msg = f"Error parsing RSS feed: {e}"
        print(error_msg)
        results["success"] = False
        results["errors"].append(error_msg)
    except Exception as e:
        error_msg = f"Unexpected error: {e}"
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
