# Instagram Shop Finder

A Python-based tool for discovering, validating, filtering, and managing public Instagram shop profiles.

The project is designed to find potential Instagram shops from public web sources, validate their public Instagram profile information, classify them by category, score commercial/shop signals, and store both discovered candidates and qualified profiles.

Repository: https://github.com/PouriaDRD/instagram-shop-finder

---

## Features

- Automatic discovery of Instagram shop candidates from public web sources
- Public Instagram profile validation using Playwright
- Category classification
- Shop/commercial signal scoring
- Follower-based filtering
- Minimum shop-score filtering
- Candidate retry and status tracking
- Persistent storage of candidates and qualified profiles
- Temporary snapshots for the latest discovery and validation run
- Safe data reset with automatic backup
- Persian RTL web dashboard
- Interactive search and filtering in the dashboard
- Local web server launch directly from the CLI menu
- Conservative crawling and rate-limit handling
- Automated test suite

---

## Supported Categories

The current profile categories are:

- Beauty
- Fashion
- Clothing
- Home
- Accessories
- Toys
- Unknown

Category detection is based on profile content and available discovery evidence.

---

## How It Works

The automatic discovery workflow has three main stages:

```text
Search Filters
      ↓
Public Web Discovery
      ↓
Candidate Storage
      ↓
Instagram Validation
      ↓
Classification & Shop Scoring
      ↓
Filtering
      ↓
Qualified Profiles
```

### 1. Discovery

The application searches public web sources and directories for potential Instagram usernames.

Every discovered username is stored immediately in:

```text
data/candidates.json
```

This means candidate information is preserved even if Instagram validation is interrupted later.

### 2. Instagram Validation

Candidates are checked against publicly accessible Instagram profile information.

The crawler extracts available information such as:

- Username
- Display name
- Bio
- Followers
- Following
- Post count
- External links
- Public/private status

The application then determines:

- Detected category
- Shop score
- Shop signals
- Qualification status

### 3. Final Filtering

Profiles can be filtered by criteria such as:

- Category
- Minimum followers
- Maximum followers
- Minimum shop score

Qualified profiles are permanently stored in:

```text
data/profiles.json
```

---

## Data Files

The project separates permanent storage from temporary run snapshots.

```text
data/
├── profiles.json
├── candidates.json
├── latest_discovery.json
├── latest_validation.json
├── backups/
└── instagram-browser-profile/
```

### `profiles.json`

Stores profiles that passed the requested qualification filters.

### `candidates.json`

Stores all discovered candidates and their processing history.

Candidate statuses may include:

```text
new
matched
rejected
fetch_failed
rate_limited
incomplete
already_saved
```

### `latest_discovery.json`

Contains only the results of the latest discovery run.

It is overwritten when a new discovery starts.

### `latest_validation.json`

Contains the validation results and summary of the latest run.

It is also overwritten by the next run.

---

## Web Dashboard

The project includes a local Persian web dashboard.

The dashboard displays:

- Stored profile count
- Stored candidate count
- Latest discovery results
- Latest validation results
- Matched and rejected profiles
- Incomplete and failed profiles
- Categories
- Followers
- Shop scores
- Validation reasons

Tables support filtering and search, and rows are visually separated for easier reading.

The dashboard is read-only and does not modify stored data.

Default address:

```text
http://127.0.0.1:8000
```

---

## Installation

Clone the repository:

```bash
git clone https://github.com/PouriaDRD/instagram-shop-finder.git
cd instagram-shop-finder
```

Create a virtual environment:

### Windows

```bash
py -m venv .venv
.venv\Scripts\activate
```

Install dependencies:

```bash
pip install -e .
```

Install Playwright browser dependencies:

```bash
playwright install chromium
```

---

## Running the Application

Start the CLI:

```bash
py main.py
```

The menu provides access to the main project operations, including:

```text
Find shops automatically
Process profile manually
Filter saved profiles
Reprocess saved profiles
Setup Instagram session
Open web dashboard
Delete stored data
Exit
```

---

## Running the Dashboard Directly

The web dashboard can also be started manually:

```bash
py -m app.web.server
```

Then open:

```text
http://127.0.0.1:8000
```

When started through the CLI menu, the dashboard runs in a separate process and the browser is opened automatically.

---

## Safe Data Reset

Stored data can be cleared from the CLI.

Before any data is cleared, the application creates a backup inside:

```text
data/backups/
```

Example:

```text
data/backups/20260901_123945_123456/
├── profiles.json
├── candidates.json
├── latest_discovery.json
├── latest_validation.json
└── manifest.json
```

Deletion only proceeds when the user explicitly types:

```text
yes
```

Any other input cancels the operation.

Browser/session data and previous backups are not deleted.

---

## Follower Input Formats

Follower filters support multiple formats.

Examples:

```text
10000
10,000
10_000
۱۰٬۰۰۰
10k
10.5k
1m
1.5m
10 هزار
1 میلیون
10k+
```

---

## Crawling Behavior

The Instagram crawler uses Playwright and only works with publicly accessible profile information.

The crawler includes conservative pacing and cooldown behavior to reduce unnecessary request pressure.

It also handles rate-limit situations and can stop processing when repeated rate limiting occurs.

The project does not rely on anti-bot bypasses, proxy rotation, CAPTCHA bypassing, or other access-control circumvention techniques.

---

## Testing

Run the complete test suite:

```bash
pytest
```

Run a specific test module:

```bash
pytest tests/test_web_server.py -v
```

The project includes tests for areas such as:

- Category classification
- Category resolution
- Profile filtering
- Shop scoring
- Follower parsing
- Playwright profile parsing
- Rate limiting
- Crawl pacing
- Candidate processing
- Snapshot storage
- Data backup/reset
- Web dashboard
- Dashboard launcher

---

## Project Structure

```text
instagram-shop-finder/
├── app/
│   ├── classifiers/
│   ├── cli/
│   ├── crawler/
│   ├── discovery/
│   ├── filters/
│   ├── mappers/
│   ├── models/
│   ├── storage/
│   └── web/
├── data/
├── tests/
├── main.py
└── pyproject.toml
```

---

## Notes

Instagram availability depends on network access from the machine running the application.

The discovery stage uses public web sources and does not require Instagram access, while the Instagram validation stage requires access to public Instagram pages.

The application is intended for responsible analysis of publicly available information.