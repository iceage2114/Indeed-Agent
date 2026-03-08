# config.py � Search parameters, location, and output path

import os

# --------------------------------------------------------------------------- #
# Location
# --------------------------------------------------------------------------- #
LOCATIONS = [
    "20878",                 # ZIP code (default/local)
    "Boston, MA",
    "Seattle, WA",
    "San Francisco, CA",
    "New York City, NY",
    "Chicago, IL",
]
RADIUS = 100                 # Miles

# --------------------------------------------------------------------------- #
# Search fields
# --------------------------------------------------------------------------- #
SEARCH_FIELDS = [
    {
        "label": "entry level software engineering",
        "query": "entry level software engineer",
    },
    {
        "label": "junior software engineering",
        "query": "junior software engineer",
    },
    {
        "label": "software engineering new grad",
        "query": "software engineering new grad",
    },
    {
        "label": "entry level cybersecurity",
        "query": "entry level cybersecurity",
    }
]

# --------------------------------------------------------------------------- #
# Pagination
# --------------------------------------------------------------------------- #
MAX_PAGES_PER_FIELD    = 3   # Hard page cap per search
MAX_NEW_JOBS_PER_FIELD = 10  # Stop early once this many new (unseen) jobs found

# --------------------------------------------------------------------------- #
# Rate limiting
# --------------------------------------------------------------------------- #
REQUEST_DELAY_MIN = 3.0      # Seconds — minimum delay between page loads
REQUEST_DELAY_MAX = 7.0      # Seconds — maximum delay between page loads
MAX_RETRIES = 3              # Retry failed pages up to this many times

# Pause between finishing one search query and starting the next.
# Gives Indeed time to "forget" the previous burst of requests.
INTER_SEARCH_DELAY_MIN = 10  # Seconds
INTER_SEARCH_DELAY_MAX = 20  # Seconds

# Extra pause when switching to a new location (on top of inter-search delay).
INTER_LOCATION_DELAY_MIN = 45  # Seconds
INTER_LOCATION_DELAY_MAX = 90  # Seconds

# --------------------------------------------------------------------------- #
# Company blocklist
# --------------------------------------------------------------------------- #
# Jobs from these companies will be silently skipped during scraping.
# Matching is case-insensitive and checks if the block string appears anywhere
# in the company name (e.g. "staffing" blocks "ABC Staffing Solutions").
BLOCKED_COMPANIES: list[str] = [
    # Add company names or keywords to block, e.g.:
    # "Staffing Solutions",
    # "Dice",
    "Antra",
    "Data Annotation"
]

# --------------------------------------------------------------------------- #
# Scheduler
# --------------------------------------------------------------------------- #
SCRAPE_INTERVAL_HOURS = 24   # How often the background scraper runs
SCRAPE_ON_STARTUP     = False  # Run the scraper immediately when the server starts

# --------------------------------------------------------------------------- #
# Paths
# --------------------------------------------------------------------------- #
BASE_DIR = os.path.dirname(os.path.abspath(__file__))

# Runtime data files live in data/
JOBS_DB_PATH      = os.path.join(BASE_DIR, "data", "jobs.db")
AUTH_STATE_PATH   = os.path.join(BASE_DIR, "data", "auth_state.json")
PROFILE_PATH      = os.path.join(BASE_DIR, "data", "profile.json")
