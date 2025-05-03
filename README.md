# RSS to Telegram

A Firebase Functions application that automatically fetches RSS feeds and forwards new entries to a Telegram channel.

## Features

- Scheduled hourly RSS feed fetching
- Storage of feed entries in Firestore database
- Automatic forwarding of new entries to a Telegram channel

## Requirements

- Firebase project with Firestore database
- Python 3.x
- Telegram bot token and channel
- RSS feed URL

## Setup

1. Clone this repository
2. Install Firebase CLI: `npm install -g firebase-tools`
3. Login to Firebase: `firebase login`
4. Copy the environment variables file:
   ```bash
   cp .env.example .env
   ```
5. Edit `.env` with your configuration values:
   - `TELEGRAM_TOKEN`: Your Telegram bot token
   - `TELEGRAM_CHANNEL`: Your Telegram channel ID (e.g., @yourchannel)
   - `RSS_FEED`: URL of the RSS feed to monitor

## Deployment

1. Create a project in [Firebase console](https://console.firebase.google.com)
2. Create a firestore db for the project
3. Init project locally: `firebase init` (add repo to your created project)
4. Deploy to Firebase: `firebase deploy`

## Local Development

Set up Python environment:
   ```bash
   cd functions
   python -m venv venv
   source venv/bin/activate  # On Windows: venv\Scripts\activate
   pip install -r requirements.txt
   ```

Run the Firebase emulators:
```bash
firebase emulators:start
```

This will start the Firebase Functions emulator on port 5001 and the Firestore emulator on port 8080.