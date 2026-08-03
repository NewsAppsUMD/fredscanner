# Frederick County Fire & Rescue Incidents Dashboard

A real-time incident tracking and analytics dashboard for Frederick County, Maryland fire and rescue calls. The project scrapes incident data from [frederickscanner.com](https://frederickscanner.com/) and publishes an interactive dashboard and RSS feed.

**Live dashboard:** [newsappsumd.github.io/fredscanner](https://newsappsumd.github.io/fredscanner/)

## About

This project is produced by the [Philip Merrill College of Journalism](https://merrill.umd.edu/) at the University of Maryland and funded by a grant from the [Scripps Howard Foundation](https://scripps.com/foundation/).

## How It Works

1. **Scraping** (`fredscanner.py`) — Fetches the latest incident data from frederickscanner.com every 30 minutes via GitHub Actions. New incidents are appended to `incidents.csv`.
2. **Threading** (`threads.py`) — The source re-posts an incident every time its dispatch changes (units added, event reclassified). This groups those re-posts into a single incident thread — chaining posts at the same location within a 60-minute window when their event types are compatible (e.g. a fire alarm escalating to a building fire), while never merging administrative posts (station transfers) or posts at station/training-facility addresses. `make_rss.py` and the dashboard both use it, so counts and feed entries reflect incidents, not individual dispatch posts.
3. **RSS Feeds** (`make_rss.py`) — Generates a feed of the 50 most recent individual posts (`site/latest.rss`) and a filtered feed of large responses, working fires, and rare incident types, one entry per incident thread (`site/priority.rss`). A growing incident updates its existing feed entry instead of appearing as a new one. Also writes the CSV into the `site/` directory with an added `ThreadID` column.
4. **Dashboard** (`site/index.html`) — A static HTML page deployed to GitHub Pages that loads and visualizes the incident data client-side, grouping posts into threads the same way.

## Dashboard Features

- Search by event type, location, or responding units
- Filter by event type and date range
- Key metrics: total incidents, average per day, most common event type — counted per incident thread, not per dispatch post
- 7-day and 30-day percentage change indicators
- Interactive line chart of incidents over time
- Frequent Locations leaderboard — top locations by incident count for the current filters, click-to-filter
- Incident records table with repeat dispatches grouped into one row; click a row with an updates badge to expand each individual post
- RSS feed for the latest individual posts, plus a filtered priority-alerts feed (one entry per incident thread) for large responses, working fires, and rare incident types

## Data

The incident data is stored in `incidents.csv` with the following columns:

| Column | Description |
|--------|-------------|
| Time | Time of the incident (e.g., "1:17 pm") |
| Event | Incident type (e.g., "HOUSE FIRE", "VEHICLE ACCIDENT - BLS") |
| Location | Address or block location |
| Units | Responding units and radio information |
| Date | Date in MM/DD/YYYY format |
| Datetime | ISO-formatted datetime (YYYY-MM-DD HH:MM:SS) |

The raw `incidents.csv` in the repo is never modified beyond appending new posts. The published copy at `site/incidents.csv` adds a `ThreadID` column so the dashboard can group posts into incidents; rows sharing the same `ThreadID` are re-posts of the same incident.

## Setup

### Requirements

- Python 3.x
- Dependencies: `pip install -r requirements.txt`

### Running Locally

```bash
# Run the test suite
python test_threads.py

# Scrape latest incidents
python fredscanner.py

# Generate RSS feeds and prepare site data
python make_rss.py
```

The dashboard can be served from the `site/` directory using any static file server.

### Automation

The GitHub Actions workflow (`.github/workflows/scrape.yaml`) runs the tests, scraper, and RSS generator every 30 minutes and deploys the updated site to GitHub Pages.

## License

MIT License. See [LICENSE](LICENSE) for details.
