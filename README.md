# Frederick County Fire & Rescue Incidents Dashboard

A real-time incident tracking and analytics dashboard for Frederick County, Maryland fire and rescue calls. The project scrapes incident data from [frederickscanner.com](https://frederickscanner.com/) and publishes an interactive dashboard and RSS feed.

**Live dashboard:** [newsappsumd.github.io/fredscanner](https://newsappsumd.github.io/fredscanner/)

## About

This project is produced by the [Philip Merrill College of Journalism](https://merrill.umd.edu/) at the University of Maryland and funded by a grant from the [Scripps Howard Foundation](https://scripps.com/foundation/).

## How It Works

1. **Scraping** (`fredscanner.py`) — Fetches the latest incident data from frederickscanner.com every 30 minutes via GitHub Actions. New incidents are appended to `incidents.csv`.
2. **RSS Feed** (`make_rss.py`) — Generates an RSS feed (`site/latest.rss`) with the 50 most recent incidents and copies the CSV into the `site/` directory.
3. **Dashboard** (`site/index.html`) — A static HTML page deployed to GitHub Pages that loads and visualizes the incident data client-side.

## Dashboard Features

- Search by event type, location, or responding units
- Filter by event type and date range
- Key metrics: total incidents, average per day, most common event type
- 7-day and 30-day percentage change indicators
- Interactive line chart of incidents over time
- Paginated incident records table
- RSS feed for the latest incidents

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

## Setup

### Requirements

- Python 3.x
- Dependencies: `pip install -r requirements.txt`

### Running Locally

```bash
# Scrape latest incidents
python fredscanner.py

# Generate RSS feed and prepare site data
python make_rss.py
```

The dashboard can be served from the `site/` directory using any static file server.

### Automation

The GitHub Actions workflow (`.github/workflows/scrape.yaml`) runs the scraper and RSS generator every 30 minutes and deploys the updated site to GitHub Pages.

## License

MIT License. See [LICENSE](LICENSE) for details.
