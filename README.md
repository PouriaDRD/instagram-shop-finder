# Instagram Shop Finder

A Python-based tool for discovering, validating, filtering, and managing public Instagram shop profiles.

The project finds potential Instagram shops from public web sources, validates their public Instagram profile information, classifies them by category, evaluates commercial/shop signals, and stores both discovered candidates and qualified profiles.

---

## Features

- Automatic discovery of Instagram shop candidates from public web sources
- Public Instagram profile validation using Playwright
- Category classification
- Shop/commercial signal scoring
- Follower-based filtering
- Minimum shop-score filtering
- Candidate retry and status tracking
- Persistent storage for candidates and qualified profiles
- Temporary snapshots for the latest discovery and validation runs
- Safe data deletion with automatic backups
- Persian RTL web dashboard
- Interactive dashboard search and filtering
- Dashboard launch directly from the CLI menu
- Conservative crawling and rate-limit handling
- Automated test suite

---

## Supported Categories

The current categories are:

- Beauty
- Fashion
- Clothing
- Home
- Accessories
- Toys
- Unknown

Classification is based on available public profile content and discovery evidence.

---

## How It Works

The automatic discovery workflow follows this pipeline:

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

Every discovered candidate is immediately stored in:

```text
data/candidates.json
```

This ensures that discovered usernames are preserved even if Instagram validation is interrupted later.

### 2. Instagram Validation

Candidates are checked against publicly accessible Instagram profile information.

Available profile data may include:

- Username
- Display name
- Bio
- Followers
- Following
- Post count
- External links
- Public/private availability

The application then evaluates:

- Detected category
- Category resolution
- Shop score
- Commercial signals
- Final qualification status

### 3. Final Filtering

Profiles can be filtered using criteria such as:

- Category
- Minimum followers
- Maximum followers
- Minimum shop score

Qualified profiles are permanently stored in:

```text
data/profiles.json
```

---

## Data Storage

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

Permanent storage for profiles that pass the requested qualification filters.

### `candidates.json`

Permanent storage for all discovered candidates and their processing history.

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

Stores only the latest discovery run.

It is overwritten when a new discovery starts.

### `latest_validation.json`

Stores the latest Instagram validation results and summary.

It is overwritten by the next run.

---

## Installation

Clone the repository:

```bash
git clone https://github.com/PouriaDRD/instagram-shop-finder.git
cd instagram-shop-finder
```

Create and activate a virtual environment.

### Windows

```bash
py -m venv .venv
.venv\Scripts\activate
```

Install the required Python dependencies:

```bash
pip install -r requirements.txt
```

Install the Chromium browser required by Playwright:

```bash
playwright install chromium
```

---

## Running the Application

Start the main CLI:

```bash
py main.py
```

The CLI provides access to the main project operations:

```text
1. Find shops automatically
2. Process profile manually
3. Filter saved profiles
4. Reprocess saved profiles
5. Setup Instagram session
6. Open web dashboard
7. Delete stored data
8. Exit
```

---

## Web Dashboard

The project includes a local Persian RTL dashboard for viewing discovered and validated profiles.

The dashboard provides:

- Overall candidate and profile statistics
- Latest discovery results
- Latest validation results
- Match and rejection statuses
- Follower counts
- Shop scores
- Category information
- Validation reasons
- Search and filtering
- Direct Instagram profile links

The dashboard is read-only and does not modify stored data.

Default address:

```text
http://127.0.0.1:8000
```

It can be opened directly from the CLI menu or started manually:

```bash
py -m app.web.server
```

When launched from the CLI, the web server runs in a separate process and the browser opens automatically.

---

## Safe Data Reset

Stored application data can be cleared from the CLI.

Before deletion, a timestamped backup is automatically created under:

```text
data/backups/
```

A backup may contain:

```text
profiles.json
candidates.json
latest_discovery.json
latest_validation.json
manifest.json
```

Deletion only proceeds after the user explicitly enters:

```text
yes
```

Existing backups and Instagram browser/session data are not removed.

---

## Follower Input Formats

Follower filters support multiple formats:

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

Instagram validation uses Playwright and works with publicly accessible profile information.

The crawler includes:

- Delays between profile requests
- Batch cooldown periods
- Rate-limit handling
- Controlled retries
- Session stopping after repeated rate limits

The project does not use CAPTCHA bypassing, proxy rotation, stealth techniques, or access-control circumvention.

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

The test suite covers areas including:

- Category classification
- Category resolution
- Shop scoring
- Follower input parsing
- Profile filtering
- Playwright profile extraction
- Crawl pacing
- Rate-limit handling
- Candidate processing
- Run snapshots
- Backup and data reset
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
├── LICENSE
├── README.md
├── requirements.txt
└── main.py
```

---

## Author

Developed by **Pouria Darandi**.

## License

This project is licensed under the **MIT License**.

See the `LICENSE` file in the project root for the full license text.

---

## Responsible Use

This project is intended for responsible processing of publicly available information.

Public-web discovery can run independently, while Instagram validation requires network access to public Instagram pages.