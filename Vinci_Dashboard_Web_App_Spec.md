# Vinci Daily BSR Dashboard — Web Application Specification

**Version:** 1.0  
**Date:** May 2026  
**Prepared for:** Vinci Books Ltd  
**Classification:** Confidential — Internal Use Only

---

## Table of Contents

1. [Context & Project Overview](#1-context--project-overview)
2. [Architecture & Technology Stack](#2-architecture--technology-stack)
3. [Environment Variables & Secrets](#3-environment-variables--secrets)
4. [Data Sources & API Integration](#4-data-sources--api-integration)
5. [Supabase Database Schema](#5-supabase-database-schema)
6. [Data Refresh & Cron Architecture](#6-data-refresh--cron-architecture)
7. [Authentication & Security](#7-authentication--security)
8. [Business Logic & Calculation Rules](#8-business-logic--calculation-rules)
9. [Dashboard Sections — Full Specification](#9-dashboard-sections--full-specification)
10. [Budget / Reforecast Feature](#10-budget--reforecast-feature)
11. [Design System & CSS Tokens](#11-design-system--css-tokens)
12. [File & Project Structure](#12-file--project-structure)
13. [Deployment Runbook (Ubuntu VM)](#13-deployment-runbook-ubuntu-vm)
14. [Claude Build Prompt](#14-claude-build-prompt)

---

## 1. Context & Project Overview

Vinci Books Ltd is a digital-first publishing house managing a portfolio of several hundred authors and thousands of titles across Amazon KDP, Kindle Unlimited (KU), and other marketplaces. The business runs daily publishing analytics from two primary sources: **Publisher Champ** (revenue, KENP reads, ad spend, units sold, series metadata) and **Supabase** (daily Amazon BSR snapshots tracked since May 15, 2026).

The current system is a Python script (`generate_daily_bsr_report_v19.py`) that fetches data from these sources, applies complex business logic, and renders a static single-page HTML file. This static file is manually opened in a browser and is not accessible to the team without running the script.

The objective of this project is to replace the static report with a **live, login-protected Next.js web application** that:

- Authenticates individual users via Supabase Auth.
- Automatically refreshes data daily at 5:00 AM UK time.
- Replicates all existing business logic and dashboard sections faithfully.
- Adds a new **Budget/Reforecast** feature for tracking actual performance against monthly targets.
- Is deployed on the existing cloud computer (Ubuntu VM, IP: `34.26.132.30`) with HTTPS.

The GitHub repository for the existing Python script is: `https://github.com/marksmith-jpg/vinci-dashboard`

---

## 2. Architecture & Technology Stack

| Layer | Technology | Notes |
|---|---|---|
| Frontend | Next.js 14+ (App Router) | Consistent with existing Vinci-Rights app |
| Styling | Tailwind CSS | Dark theme, custom design tokens |
| Auth | Supabase Auth | Email/password, individual accounts |
| Database | Supabase (PostgreSQL) | BSR data, budget targets, cached API data |
| Backend | Next.js API Routes | Data fetching, cron trigger endpoints |
| Cron | Node-cron or Vercel Cron / system cron | Daily 5 AM UK refresh |
| Deployment | Ubuntu VM (34.26.132.30) | PM2 process manager, Nginx reverse proxy |
| SSL | Let's Encrypt / Certbot | HTTPS on custom domain or IP |
| Charts | Recharts or pure CSS | Bar charts for readthrough funnels |

---

## 3. Environment Variables & Secrets

All secrets must be stored in a `.env.local` file (never committed to Git) and loaded via `process.env`. The following variables are required:

```
# Publisher Champ API
PUBLISHER_CHAMP_EMAIL=<email used to log in to publisherchamp.com>
PUBLISHER_CHAMP_PASSWORD=<password>
PUBLISHER_CHAMP_API_KEY=<api key>
PUBLISHER_CHAMP_ACCOUNT_ID=<account id>
PUBLISHER_CHAMP_BASE_URL=https://www.publisherchamp.com/api/v1

# Supabase
SUPABASE_URL=https://<project-id>.supabase.co
SUPABASE_KEY=<service role key>
NEXT_PUBLIC_SUPABASE_URL=https://<project-id>.supabase.co
NEXT_PUBLIC_SUPABASE_ANON_KEY=<anon key>

# App
NEXTAUTH_SECRET=<random 32-char string>
CRON_SECRET=<random secret for securing cron endpoint>
```

---

## 4. Data Sources & API Integration

### 4.1 Publisher Champ API

The Publisher Champ API is a REST API authenticated via an `api_key` query parameter. All endpoints follow the pattern:

```
GET https://www.publisherchamp.com/api/v1/{endpoint}/
  ?api_key=<PUBLISHER_CHAMP_API_KEY>
  &account_id=<PUBLISHER_CHAMP_ACCOUNT_ID>
  &start_date=YYYY-MM-DD
  &end_date=YYYY-MM-DD
```

The API has a long response time (up to 5 minutes for large date ranges); always use a `timeout` of at least 300 seconds. Implement retry logic with 3 attempts and a 5-second delay between retries.

#### Endpoints Used

| Endpoint | Purpose | Response Key |
|---|---|---|
| `bookStatsAPI` | Per-book revenue, spend, KENP, units, series | `table_data` (array) |
| `countryStatsAPI` | Revenue and spend by country | `countries` (object) |
| `authorStatsAPI` | Per-author book breakdown | `table_data` (object keyed by author name) |
| `adsMonitoringAPI` | Ad monitoring data | varies |

#### Book Stats Record Shape (`bookStatsAPI`)

Each item in `table_data` is an object with the following fields used by the dashboard:

| Field | Type | Description |
|---|---|---|
| `asin` | string | Amazon ASIN |
| `title` | string | Book title |
| `gross_royalty` | float | Gross revenue in converted currency (GBP) |
| `net_royalty` | float | Net royalty after Amazon fees |
| `spending` | float | Total ad spend (Facebook + Amazon combined) |
| `fb_ad_spend` | float | Facebook-only ad spend |
| `amz_ad_spend` | float | Amazon-only ad spend |
| `total_reads` | int | KENP pages read |
| `full_reads` | int | Complete KU reads (KENP / KENPC) |
| `ebooks_paid_sold` | int | Paid ebook units sold |
| `ebooks_free_sold` | int | Free ebook units (permafree) |
| `paperbacks_sold` | int | Paperback units sold |
| `image` | string | URL of book cover image |
| `all_series` | array | List of series strings, e.g. `["#1 in Ryan Kaine", "#1 in Die Ryan Kaine Reihe"]` |

#### Country Stats Record Shape (`countryStatsAPI`)

The response object has a `countries` key whose value is an object keyed by country name:

```json
{
  "converted_currency": "GBP",
  "countries": {
    "United States": {
      "converted": 129600.0,
      "converted_spend": 75200.0,
      "original_currency": "USD",
      "original": 165000.0,
      "original_spend": 96000.0
    }
  }
}
```

Use `converted` for gross revenue and `converted_spend` (or `spend_converted` or `spend` as fallback) for total ad spend.

#### Author Stats Record Shape (`authorStatsAPI`)

The `table_data` value is an object keyed by author name, where each value is itself an object keyed by book title:

```json
{
  "Joe Talon": {
    "Griffin Woodbury Supernatural Detective Book 1": {
      "asin": "B0XXXXXXXX",
      "book_royalty": 500.0,
      "read_royalty": 300.0,
      "reads": 150000
    }
  }
}
```

#### Data Periods Fetched

The following periods must be fetched and cached on each daily refresh:

| Cache Key | Start Date | End Date | Notes |
|---|---|---|---|
| `mtd` | 1st of current month | Today | Month-to-date |
| `mtd_ly` | 1st of same month last year | Same day last year | For YoY comparison |
| `30day` | Today − 30 days | Today | Rolling 30-day |
| `90day` | Today − 90 days | Today | Rolling 90-day |
| `ytd` | Jan 1 of current year | Today | Year-to-date |
| `ytd_ly` | Jan 1 of last year | Same day last year | For YoY comparison |
| `fy_prev` | Jan 1 of last year | Dec 31 of last year | Full previous FY (cache permanently once fetched) |
| `fy_prev2` | Jan 1 two years ago | Dec 31 two years ago | Full FY before that (cache permanently) |
| `lifetime` | Earliest available | Today | All-time (fetch once, update daily) |
| `country_30day` | Today − 30 days | Today | Country breakdown |
| `author_30day` | Today − 30 days | Today | Author breakdown |

### 4.2 Supabase BSR Data

The BSR tracking table stores daily snapshots of Amazon Best Sellers Rank for each tracked title. The table has been populated since May 15, 2026.

#### BSR Record Shape

Records may appear in two formats (both must be handled):

**Old format:**
```json
{
  "record_date": "2026-05-20",
  "asin": "B0XXXXXXXX",
  "title": "Book Title",
  "bsr_us": 5432,
  "bsr_uk": 1200,
  "bsr_de": 8900
}
```

**New format:**
```json
{
  "recorded_at": "2026-05-20T00:00:00Z",
  "title_id": "uuid-string",
  "title": "Book Title",
  "bsr_us": 5432,
  "bsr_uk": 1200,
  "bsr_de": 8900
}
```

When `asin` is absent, resolve the ASIN by matching `title` (normalised to lowercase, trimmed) against the book stats data.

Only load BSR records where `record_date >= 2026-05-15` (or `recorded_at >= 2026-05-15`).

---

## 5. Supabase Database Schema

The following tables must be created in the Supabase project. The BSR tracking table already exists; the budget and cached data tables are new.

### 5.1 `bsr_snapshots` (existing)

```sql
CREATE TABLE bsr_snapshots (
  id           BIGSERIAL PRIMARY KEY,
  record_date  DATE,
  recorded_at  TIMESTAMPTZ,
  asin         TEXT,
  title_id     UUID,
  title        TEXT,
  bsr_us       INTEGER,
  bsr_uk       INTEGER,
  bsr_de       INTEGER
);
```

### 5.2 `dashboard_cache` (new)

Stores the pre-computed JSON blobs for each data period so the dashboard loads instantly without re-fetching from Publisher Champ on every page view.

```sql
CREATE TABLE dashboard_cache (
  id           BIGSERIAL PRIMARY KEY,
  cache_key    TEXT UNIQUE NOT NULL,   -- e.g. 'books_30day', 'country_30day'
  data         JSONB NOT NULL,
  refreshed_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);
```

### 5.3 `budget_targets` (new)

Stores monthly revenue and ad spend targets, plus mid-month reforecasts.

```sql
CREATE TABLE budget_targets (
  id              BIGSERIAL PRIMARY KEY,
  year            INTEGER NOT NULL,
  month           INTEGER NOT NULL,          -- 1–12
  target_gross    NUMERIC(12,2) NOT NULL,    -- Revenue target in GBP
  target_spend    NUMERIC(12,2) NOT NULL,    -- Ad spend budget in GBP
  reforecast_gross NUMERIC(12,2),            -- Mid-month revised target (nullable)
  reforecast_spend NUMERIC(12,2),            -- Mid-month revised budget (nullable)
  created_by      UUID REFERENCES auth.users(id),
  updated_at      TIMESTAMPTZ NOT NULL DEFAULT NOW(),
  UNIQUE (year, month)
);
```

### 5.4 `daily_snapshots` (new)

Stores a daily summary snapshot for trend tracking (mirrors the Python `save_daily_snapshot` function).

```sql
CREATE TABLE daily_snapshots (
  id              BIGSERIAL PRIMARY KEY,
  snapshot_date   DATE UNIQUE NOT NULL,
  portfolio       JSONB NOT NULL,   -- {gross, spend, net, kenp, roi, books}
  top_series      JSONB NOT NULL,   -- [{name, gross, net, roi}]
  top_readthrough JSONB NOT NULL,   -- [{series, book1_to_2}]
  top_authors_rt  JSONB NOT NULL,   -- [{author, avg_rt}]
  created_at      TIMESTAMPTZ NOT NULL DEFAULT NOW()
);
```

### 5.5 Row-Level Security

All tables must have RLS enabled. Only authenticated users may read data. Only users with the `admin` role (stored in `auth.users.user_metadata.role`) may write to `budget_targets`.

```sql
ALTER TABLE dashboard_cache ENABLE ROW LEVEL SECURITY;
CREATE POLICY "Authenticated read" ON dashboard_cache FOR SELECT USING (auth.role() = 'authenticated');

ALTER TABLE budget_targets ENABLE ROW LEVEL SECURITY;
CREATE POLICY "Authenticated read" ON budget_targets FOR SELECT USING (auth.role() = 'authenticated');
CREATE POLICY "Admin write" ON budget_targets FOR ALL USING (
  (auth.jwt() -> 'user_metadata' ->> 'role') = 'admin'
);
```

---

## 6. Data Refresh & Cron Architecture

### 6.1 Refresh Flow

The daily refresh runs at **5:00 AM UK time** (UTC+0 in winter, UTC+1 in summer — use `Europe/London` timezone). The refresh sequence is:

1. Fetch all required periods from Publisher Champ API (see §4.1 table).
2. Fetch latest BSR data from Supabase `bsr_snapshots`.
3. Run all business logic computations (see §8).
4. Write computed results to `dashboard_cache` table.
5. Write a `daily_snapshots` record.
6. Return HTTP 200.

### 6.2 API Route

Create a protected API route at `/api/refresh`:

```typescript
// app/api/refresh/route.ts
export async function POST(request: Request) {
  const secret = request.headers.get('x-cron-secret');
  if (secret !== process.env.CRON_SECRET) {
    return new Response('Unauthorized', { status: 401 });
  }
  // ... run refresh logic
}
```

### 6.3 System Cron (Ubuntu VM)

On the Ubuntu VM, add a crontab entry to trigger the refresh endpoint:

```bash
# Run at 5 AM UK time (adjust for BST/GMT as needed; use TZ= prefix)
TZ=Europe/London
0 5 * * * curl -s -X POST http://localhost:3000/api/refresh \
  -H "x-cron-secret: $CRON_SECRET" >> /var/log/vinci-refresh.log 2>&1
```

### 6.4 Manual Refresh

The dashboard header must include a **"Refresh Data"** button (visible to all authenticated users) that calls `POST /api/refresh` with the cron secret stored in a server action. The button should show a loading spinner and display the last refresh timestamp.

---

## 7. Authentication & Security

### 7.1 User Accounts

Five initial user accounts must be created in Supabase Auth:

| Name | Role |
|---|---|
| Mark Smith | admin |
| Charlie Redmayne | viewer |
| Peter Roche | viewer |
| Julian Shaw | viewer |
| Wayne | viewer |

Admin users can access the Budget/Reforecast admin page. All users can view the dashboard.

### 7.2 Auth Flow

- **Login page** (`/login`): Email and password form. No public registration. On success, redirect to `/`.
- **Middleware**: All routes except `/login` must require an active Supabase session. Use Next.js middleware to check the session cookie and redirect unauthenticated requests to `/login`.
- **Session**: Use Supabase's built-in session management with secure HttpOnly cookies via `@supabase/ssr`.
- **Password reset**: Implement the Supabase password reset email flow. Add a "Forgot password?" link on the login page.
- **Logout**: A logout button in the header that calls `supabase.auth.signOut()` and redirects to `/login`.

### 7.3 Security Requirements

- The app must not be publicly accessible without authentication. No data endpoints may return data to unauthenticated requests.
- All API routes must validate the session server-side using the Supabase service role key.
- The `.env.local` file must never be committed to Git. Add it to `.gitignore`.
- The Supabase service role key must only be used server-side (API routes, server components). The anon key is used client-side.

---

## 8. Business Logic & Calculation Rules

This section documents every calculation rule exactly as implemented in the Python script. The web app must replicate these rules precisely.

### 8.1 Currency Formatting

```
fmt_currency(value):
  sign = "-" if value < 0 else ""
  abs_val = abs(value)
  if abs_val >= 1,000,000: return f"{sign}£{abs_val/1M:.1f}M"
  if abs_val >= 1,000:     return f"{sign}£{abs_val/1K:.1f}K"
  else:                    return f"{sign}£{abs_val:.0f}"
```

**Key rule:** The minus sign appears BEFORE the pound sign: `-£1,500` not `£-1,500`.

### 8.2 Percentage Formatting

```
fmt_pct(value):
  sign = "+" if value >= 0 else ""
  return f"{sign}{value:,.1f}%"   # comma-separated for large values
```

Example: `+26,311.8%` (not `+26311.8%`).

### 8.3 Portfolio Overview KPIs

For each period tab, compute the following from the period's book stats array:

```
gross  = sum(book.gross_royalty for book in books)
spend  = sum(book.spending for book in books)
net    = gross - spend
kenp   = sum(book.total_reads for book in books)
units  = sum(book.ebooks_paid_sold for book in books)
roi    = (gross / spend * 100) if spend > 0 else Infinity
active_titles = len(books)
```

**YoY comparison row** (shown beneath the KPI cards where applicable):

```
gross_change = (gross_curr - gross_prev) / gross_prev * 100
net_change   = (net_curr  - net_prev)  / net_prev  * 100
kenp_change  = (kenp_curr - kenp_prev) / kenp_prev * 100
```

If `prev == 0` and `curr > 0`, display "N/A" in green. Use comma formatting for large percentages.

**Period comparison logic:** Same-period-last-year, not full-month average. MTD compares to the same days of the same month last year. YTD compares to the same calendar date range last year.

### 8.4 Portfolio Pulse

**BSR Top 10K counts** (from latest BSR snapshot date):

```
us_top10k = count(records where bsr_us > 0 AND bsr_us <= 10,000)
uk_top10k = count(records where bsr_uk > 0 AND bsr_uk <= 10,000)
de_top10k = count(records where bsr_de > 0 AND bsr_de <= 10,000)
```

**Avg B1→B2 Readthrough %** (from 90-day readthrough results):

```
b1_to_b2_rates = [r.book1_to_2 for r in readthrough_90 if r.book1_to_2 > 0]
avg_b1_to_b2 = mean(b1_to_b2_rates)
```

Color coding: Green if ≥ 50%, Amber if ≥ 40%, Red if < 40%.

**Organic Revenue %** (from 30-day books):

```
total_gross   = sum(book.gross_royalty for book in books_30)
organic_gross = sum(book.gross_royalty for book in books_30 if book.spending == 0)
organic_pct   = organic_gross / total_gross * 100
```

**Top Mover** (from BSR data, comparing latest vs previous snapshot date):

```
For each book with BSR data on both latest_date and prev_date:
  prev_bsr = bsr_us on prev_date
  curr_bsr = bsr_us on latest_date
  
  ONLY consider books where:
    0 < prev_bsr <= 100,000 AND 0 < curr_bsr <= 100,000
  
  improvement = prev_bsr - curr_bsr  (positive = moved up the chart)
  
  ONLY include if improvement > 0 AND improvement/prev_bsr >= 0.10 (10% minimum)
  
  weighted_score = improvement * (1 / log10(max(2, curr_bsr)))

Top Mover = book with highest weighted_score
```

Display: Book cover image, title (truncated to 35 chars), author name, BSR change (e.g., `15,000 → 5,000`), improvement string (e.g., `+10K`). Subtitle: "Among titles ranked in top 100K".

### 8.5 Series Classification

**Box set detection** — a title is a box set if it contains any of these keywords (case-insensitive):

```
box set, boxed set, boxset, box-set, omnibus, collection, complete series,
complete collection, the complete, trilogy, duology, quadrilogy, pentalogy
```

Also matches the regex pattern: `books?\s+\d+\s*[-–to]+\s*\d+` (e.g., "Books 1-3").

**Prequel/novella detection** — a title is a prequel/novella if it contains any of these keywords (case-insensitive):

```
prequel, novella, short story, short stories, origin story, origins story,
prelude, prologue, bonus story, companion novella, companion story,
starter, sampler, free story, free read
```

**German/translated series detection** — a series name is a DE translation if it starts with `Der `, `Die `, or `Das `.

### 8.6 Series Economics Computation

The `all_series` field on each book record contains strings like `"#1 in Ryan Kaine"` or `"#1 in Die Ryan Kaine Reihe"`. Parse these as follows:

```
parts = series_string.split(" in ", 1)
position_str = parts[0]   # e.g. "#1"
series_name  = parts[1]   # e.g. "Ryan Kaine"
position_num = int(position_str[1:])
```

**P&L aggregation rules:**

- **Regular EN book:** Add revenue/spend/KENP/units to the EN series P&L. Include in readthrough books list.
- **Box set:** Add revenue/spend/KENP/units to the EN series P&L. Do NOT include in readthrough books list.
- **DE/translated book:** Add revenue/spend/KENP/units to both the DE series P&L and the EN parent series P&L (if the EN parent can be identified by word overlap). Do NOT include in EN readthrough books list (but include in DE readthrough list).

**Deduplication:** Within a series, if multiple books share the same position number, keep the one with the highest KENP.

**Outlier filter:** If a series has 3+ books, remove any book whose KENP is more than 2.5× the median KENP of the series. This prevents a single heavily-advertised book from distorting readthrough.

**Composition annotation:** For each EN series, build a string like `"8 EN titles · 2 DE translations · 1 box set"`.

**Minimum sample size:** Only include a series in readthrough analysis if Book 1 KENP ≥ 5,000.

### 8.7 Readthrough Funnel Computation

For each series with 2+ books after deduplication and outlier filtering:

```
1. Find Book 1: the book with position == 1 that is NOT a prequel/novella.
   If Book 1 KENP == 0 or Book 1 KENP < 5,000: skip this series.

2. For each book in sorted position order (skipping position 0 and prequels/novellas):
   pct_of_book1 = (book.total_reads / book1_kenp) * 100

3. Compute step-by-step retention:
   For i in range(1, len(books)):
     step_retention[i] = (books[i].total_reads / books[i-1].total_reads) * 100

4. book1_to_2 = step_retention[0]

5. EXCLUDE series where book1_to_2 > 100% (inverted funnels).

6. avg_subsequent = mean(step_retention[1:]) if len > 1 else 0
```

**Bar chart rendering:**
- Book 1 bar: always 100% height, Gold colour (`#F5C518`).
- Book 2+ bars: height = step retention from preceding book (not cumulative % of Book 1).
- Bar colours by step retention:
  - B1→B2: Green ≥ 50%, Amber ≥ 40%, Red < 40%.
  - B2→B3 and beyond: Green ≥ 70%, Amber ≥ 60%, Red < 60%.
- Bars are anchored to the bottom of the card using CSS flexbox (`align-items: flex-end`).
- Tooltip on hover: shows both step retention AND cumulative % of Book 1.

**Readthrough Early Warnings:** Flag any series where the 30-day B1→B2 has dropped more than 10 percentage points below the 90-day B1→B2. Display in an amber warning box below the funnel cards.

### 8.8 Author Readthrough Ranking

```
For each author:
  series_list = all series where Book 1 is attributed to this author
  avg_readthrough = mean(series.book1_to_2 for series in series_list)
  best_readthrough = max(series.book1_to_2 for series in series_list)
  best_series = series with highest book1_to_2

Sort by avg_readthrough descending.
```

Author attribution: Resolve from the `authorStatsAPI` data by matching ASIN. Use title-based fallback if ASIN is not found.

### 8.9 Ad Efficiency

**Qualification threshold:** Series must have `total_series_gross >= £1,000` to appear in any tier.

**ROI tiers:**

| Tier | Label | Condition | Sort Order |
|---|---|---|---|
| 1 | ⭐ Star Performers | ROI ≥ 300% | ROI descending |
| 2 | ✓ Solid Performers | 200% ≤ ROI < 300% | ROI descending |
| — | *(excluded)* | 100% ≤ ROI < 200% | Not shown |
| 3 | ✗ Burning Money | ROI < 100% | Absolute £ loss descending |

**ROI calculation:**

```
roi = (total_series_gross / total_series_spend) * 100
```

**Cost/Reader calculation:**

```
book1_readers = book1.full_reads + book1.ebooks_paid_sold + book1.paperbacks_sold
cost_per_reader = total_series_spend / book1_readers
```

`full_reads` = number of people who read the complete KU book (KENP ÷ KENPC). This field is provided directly by Publisher Champ.

**Burning Money loss column:**

```
abs_loss = total_series_spend - total_series_gross
display as: -£{abs_loss}  (negative, bold, red)
```

Show top 10 per tier. Burning Money column header changes from "Cost/Reader" to "£ Loss".

### 8.10 Market Breakdown

**Non-country exclusion list** (exact string match):

```
Facebook, Meta, Amazon, Google, Apple, BookBub,
Draft2Digital, Kobo, Smashwords, IngramSpark
```

**Local currency badges** — show `(INR)`, `(JPY)`, `(BRL)`, `(MXN)` badge for these countries when `original_currency != "GBP"`:

```
India → (INR)
Japan → (JPY)
Brazil → (BRL)
Mexico → (MXN)
```

Badge tooltip: `"Amounts converted from {currency}. Original: {currency} {gross:,.0f} gross / {currency} {spend:,.0f} spend"`.

**% of Total column:**

```
pct_of_total = (country.gross / total_all_countries_gross) * 100
```

Display as a gold percentage value plus a 60px inline mini bar chart.

**Sort:** By gross revenue descending.

### 8.11 BSR-Revenue Correlation

```
For each ASIN with BSR readings:
  avg_bsr = mean(all bsr_us readings across all tracked dates)
  
  EXCLUDE if: book.ebooks_free_sold > 10 AND book.gross_royalty < 10
              (perma-free books rank on the FREE chart, not paid chart)
  
  FLAG as Free+KU if: book.ebooks_free_sold > 0 AND book.total_reads > 0

Sort by avg_bsr ascending (best rank first).
Show top 25.
```

**Series column values:**
- If book is a box set: `"Box Set"` (optionally appended with series name)
- If book has a valid series entry: the full series string, e.g. `"#1 in Ryan Kaine"`
- Otherwise: `"Standalone"`

**Column header note:** "Avg BSR based on N day(s) of tracking data (BSR tracking started May 15, 2026 — average will improve as history grows)"

---

## 9. Dashboard Sections — Full Specification

The dashboard is a single-page application at `/`. Sections appear in the following order. All data is loaded server-side on initial render and hydrated client-side for tab switching.

### Section 1: Portfolio Overview

**Section badge:** `PORTFOLIO`

**Description:** Tabbed view of aggregate portfolio metrics across multiple time periods.

**Tabs (in order):** MTD | 30-Day | 90-Day | YTD 2026 | FY 2025 | FY 2024 | Lifetime

Default active tab: **MTD**.

Each tab panel shows a 6-card KPI grid:

| KPI | Label | Sub-label |
|---|---|---|
| Gross Revenue | `GROSS REVENUE` | — |
| Ad Spend | `AD SPEND` | `FB + AMZ combined` |
| Net Profit | `NET PROFIT` | — |
| KENP Reads | `KENP READS` | — |
| Portfolio ROI | `PORTFOLIO ROI` | `Gross / Spend` |
| Units Sold | `UNITS SOLD` | `{N} active titles` |

Where applicable, show a YoY comparison row beneath the KPI grid:

```
vs {label}: Gross {+X%}  Net {+X%}  KENP {+X%}
```

Comparison rows appear on: MTD (vs same period last year), YTD 2026 (vs YTD 2025), FY 2025 (vs FY 2024).

### Section 2: Portfolio Pulse

**Section badge:** `LIVE SIGNALS`

**Description:** "Real-time portfolio health signals. BSR Top 10K counts from the latest daily Supabase snapshot. Readthrough and organic metrics from the 90-day Publisher Champ window."

A 6-card KPI grid:

| # | KPI | Label | Sub-label |
|---|---|---|---|
| 1 | US Top 10K count | `US TOP 10K` | `Titles ranked ≤10,000 (as of {date})` |
| 2 | UK Top 10K count | `UK TOP 10K` | `Titles ranked ≤10,000 (as of {date})` |
| 3 | DE Top 10K count | `DE TOP 10K` | `Titles ranked ≤10,000 (as of {date})` |
| 4 | Avg B1→B2 RT% | `AVG B1→B2 READTHROUGH` | `Portfolio avg across all series · Benchmark: 50%+` |
| 5 | Organic Revenue % | `ORGANIC REVENUE %` | `Gross from titles with zero ad spend (30-day)` |
| 6 | Top Mover | `TOP MOVER (US BSR)` | `Among titles ranked in top 100K` |

The Top Mover card has a special layout: book cover thumbnail (52×72px) on the left, text on the right showing the improvement value in green, title, author in italic, and BSR change (e.g., `15,000 → 5,000`).

### Section 3: Budget vs Actual *(new)*

See §10 for full specification.

### Section 4: Ad Efficiency

**Section badge:** `FUNNEL ECONOMICS`

**Description:** "Evaluating Book 1 funnels at SERIES level. A profitable funnel means total series revenue exceeds total ad spend. Minimum £1K gross revenue to qualify."

**Period label badge:** "📅 Based on 30-day rolling data"

Three sub-sections rendered sequentially:

**Tier 1 — ⭐ Star Performers (ROI ≥ 300%)** (gold heading)

Table columns: `Series / Author | Books | Spend | Gross | ROI | Cost/Reader (?)`

The Cost/Reader column header has a tooltip: "Ad spend ÷ total readers acquired. Total readers = KU complete reads (full_reads) + paid ebook units + paperback units. A lower value means you are acquiring readers more efficiently."

**Tier 2 — ✓ Solid Performers (ROI 200–300%)** (green heading)

Same columns as Tier 1.

**Tier 3 — ✗ Burning Money (ROI < 100%)** (red heading)

Table columns: `Series / Author | Books | Spend | Gross | ROI | £ Loss`

The £ Loss value is displayed in bold red as `-£{abs_loss}`.

### Section 5: Market Breakdown

**Section badge:** `BY COUNTRY`

**Description:** "Revenue and spend by marketplace. All values converted to GBP."

Table columns: `Country | Revenue | Ad Spend | Net | % of Total`

The `% of Total` column shows a gold percentage value and a 60px inline mini bar chart (4px tall, gold fill, proportional width).

Local currency badges appear inline in the Country column (see §8.10).

### Section 6: Series Readthrough Funnels

**Section badge:** `90-DAY KENP`

**Description:** "Step-by-step reader retention through each series. Book 1 is the 100% baseline. Each subsequent bar shows what % of the preceding book's readers continued. Excludes prequels, novellas, and inverted funnels."

**Benchmark legend** (shown above the funnel grid):

| Colour | Meaning |
|---|---|
| 🟢 Green | B1→B2: ≥ 50% · B2+: ≥ 70% |
| 🟡 Amber | B1→B2: ≥ 40% · B2+: ≥ 60% |
| 🔴 Red | B1→B2: < 40% · B2+: < 60% |

**Funnel card layout:** 2-column responsive grid (`minmax(400px, 1fr)`). Show top 12 series by gross revenue (minimum 3 books required).

Each card contains:
- Series name (h4)
- Meta line: `{author} · {N} EN books · Book 1 KENP: {kenp:,}`
- Composition annotation in gold monospace: e.g., `8 EN titles · 2 DE translations · 1 box set`
- Step retention badges (e.g., `B1→B2: 78%` in green/amber/red)
- Bottom-anchored CSS bar chart (height 160px, 200px if > 10 books)

Bar chart tooltip on hover shows: `B{N}→B{N+1}: {step}% of preceding book | {cumulative}% of B1`

**Readthrough Early Warnings box** (amber, shown if any warnings exist):

"⚠️ Readthrough Early Warnings — Flags series where the last 30-day Book 1→Book 2 readthrough has dropped more than 10 percentage points below the 90-day average. A sudden drop may indicate: wrong readers being attracted by new ads or covers, pricing changes affecting conversion, or algorithm visibility loss. Investigate the cause and adjust marketing."

List each flagged series as: `{Series Name}: 90-day RT {X}% → 30-day RT {Y}% (↓{Z}pp)`

### Section 7: Author Readthrough Retention Ranking

**Section badge:** `LEADERBOARD`

**Description:** "Authors ranked by their best Book 1→Book 2 readthrough rate across all series. This is the critical ad funnel conversion point — it measures how many Book 1 readers are sticky enough to buy Book 2. Industry benchmark: 50%+ is good, 60%+ is excellent."

Table columns: `# | Author | B1→B2 RT% ⓘ | Series | Best Series`

The B1→B2 RT% column header has a tooltip: "Best Book 1→Book 2 readthrough across all their series. This is the ad funnel conversion point — the % of Book 1 readers who buy Book 2."

Colour-code the RT% value: Green ≥ 50%, Amber ≥ 40%, Red < 40%.

Show top 20 authors.

### Section 8: BSR-Revenue Correlation

**Section badge:** `US MARKET`

**Description:** "Average US BSR rank cross-referenced with 30-day Publisher Champ revenue. BSR is averaged across all available daily snapshots — the average stabilises as tracking accumulates. Sorted by best (lowest) average rank."

**Info note** (amber): "ℹ Avg BSR based on {N} day(s) of tracking data (BSR tracking started May 15, 2026 — average will improve as history grows)"

Table columns: `Avg BSR (US) | Title / Author | Series | 30-Day Gross | KENP | Units`

- Avg BSR column: right-aligned, monospace, padded right.
- Title/Author: two-line cell — title in bold (with Free+KU amber badge if applicable), author in smaller secondary colour.
- Series: left-aligned, secondary colour, truncated to 45 chars.

Show top 25 books.

---

## 10. Budget / Reforecast Feature

### 10.1 Admin Page (`/admin/budget`)

Accessible only to users with `role: admin` in their Supabase user metadata. Non-admin users attempting to access this URL should be redirected to `/`.

The page shows a form for the current month with the following fields:

| Field | Label | Type |
|---|---|---|
| `target_gross` | Monthly Revenue Target (£) | Number input |
| `target_spend` | Monthly Ad Spend Budget (£) | Number input |
| `reforecast_gross` | Reforecast Revenue Target (£) | Number input (optional) |
| `reforecast_spend` | Reforecast Ad Spend Budget (£) | Number input (optional) |

On submit, upsert the record into `budget_targets` for the current `year` and `month`. Show a success/error toast notification.

Also show a read-only table of all historical budget records (past 12 months).

### 10.2 Dashboard Budget Widget (Section 3)

Shown on the main dashboard between Portfolio Pulse and Ad Efficiency. If no budget has been set for the current month, show a subtle "No budget set for this month — [Set Budget]" link (admin only).

When a budget exists, show a 2-column card:

**Left column — Revenue:**
- Actual MTD gross vs target (or reforecast if set)
- Pacing indicator: project end-of-month gross based on current daily run rate
- Progress bar (gold fill, dark background)
- Status text: e.g., `"On track to hit 112% of target"` or `"8% behind budget"`

**Right column — Ad Spend:**
- Actual MTD spend vs budget (or reforecast if set)
- Pacing indicator: project end-of-month spend
- Progress bar
- Status text

**Pacing calculation:**

```
days_in_month = calendar.monthrange(year, month)[1]
days_elapsed  = today.day
daily_run_rate = actual_mtd / days_elapsed
projected_eom  = daily_run_rate * days_in_month
pacing_pct     = (projected_eom / target) * 100
```

If `pacing_pct >= 100`: show green "On track to hit {pacing_pct:.0f}% of target".
If `pacing_pct >= 90`: show amber "On track for {pacing_pct:.0f}% of target".
If `pacing_pct < 90`: show red "{100 - pacing_pct:.0f}% behind budget".

If a reforecast exists, show both the original target and the reforecast, with the reforecast used for the pacing calculation.

---

## 11. Design System & CSS Tokens

The following CSS custom properties must be defined globally and used consistently throughout the application. In Tailwind, these should be added to `tailwind.config.js` as custom colours.

### 11.1 Colour Palette

| Token | Value | Usage |
|---|---|---|
| `--black` | `#000000` | Header background |
| `--gold` | `#F5C518` | Primary accent, KPI values, section badges |
| `--white` | `#FFFFFF` | Primary text |
| `--dark-bg` | `#0a0a0a` | Page background |
| `--card-bg` | `#141414` | Card backgrounds, table wrappers |
| `--card-border` | `#222222` | Card borders, table row dividers |
| `--text-primary` | `#f0f0f0` | Body text |
| `--text-secondary` | `#999999` | Sub-labels, secondary text |
| `--text-muted` | `#666666` | Muted text, rank numbers |
| `--green` | `#00c853` | Positive values, good readthrough |
| `--red` | `#ff1744` | Negative values, burning money |
| `--amber` | `#ffab00` | Warning states, amber readthrough |

### 11.2 Typography

- **Body font:** `-apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif`
- **Monospace font:** `'JetBrains Mono', 'SF Mono', monospace` — used for KPI values, numeric table cells, readthrough badges, composition annotations
- **KPI value size:** `1.8rem`, weight `700`
- **KPI label size:** `0.7rem`, uppercase, letter-spacing `1.5px`
- **Section header h2:** `1.3rem`, weight `700`
- **Table header:** `0.7rem`, uppercase, letter-spacing `1px`, gold colour
- **Table body:** `0.85rem`
- **Numeric cells:** `0.8rem`, monospace

### 11.3 Header

```
Background: #000000
Bottom border: 2px solid #F5C518
Layout: flex, space-between, align-items center
Padding: 1.5rem 2rem

Left side:
  - Vinci Books logo (white version), 40px wide
  - Title: "Vinci Books — Executive Performance Dashboard"
  - Subtitle: "DAILY PUBLISHING ANALYTICS" in gold, uppercase, letter-spacing 2px

Right side:
  - "Data as of {date}" in secondary text
  - "Last refreshed: {timestamp}" in muted text
  - "Refresh Data" button (gold outline)
  - User name + Logout link
```

### 11.4 Section Headers

```
Layout: flex, align-items center, gap 0.75rem
Bottom border: 1px solid #222
Margin bottom: 1.5rem, padding bottom: 0.75rem

h2: 1.3rem, weight 700, white
Section badge: gold background, black text, 0.65rem, uppercase, letter-spacing 1px, border-radius 3px
Section desc: 0.85rem, secondary colour, margin bottom 1rem
```

### 11.5 KPI Cards

```
Background: #141414
Border: 1px solid #222
Border-radius: 8px
Padding: 1.5rem
Text-align: center

.kpi-value: 1.8rem, weight 700, gold, monospace
.kpi-label: 0.7rem, secondary, uppercase, letter-spacing 1.5px, margin-top 0.5rem
.kpi-sublabel: 0.75rem, muted, margin-top 0.3rem
```

### 11.6 Period Tabs

```
.period-tab (inactive):
  Background: #141414, border: 1px solid #222
  Color: secondary, padding: 0.4rem 1.2rem
  Border-radius: 4px, font-size: 0.8rem, uppercase, letter-spacing 1px

.period-tab:hover:
  Border-color: gold, color: gold

.period-tab.active:
  Background: gold, border-color: gold, color: black
```

### 11.7 Data Tables

```
.table-wrapper:
  overflow-x: auto, background: #141414
  border: 1px solid #222, border-radius: 8px

.data-table th:
  background: #141414, color: gold
  font-size: 0.7rem, uppercase, letter-spacing 1px
  padding: 0.75rem 1rem, border-bottom: 1px solid #222
  position: sticky, top: 0

.data-table td:
  padding: 0.6rem 1rem, border-bottom: 1px solid #1a1a1a
  vertical-align: middle, text-align: center

.data-table tr:hover:
  background: rgba(245, 197, 24, 0.03)

.num: monospace, 0.8rem, center-aligned
.author-name, .series-name, .book-title: left-aligned, weight 500, max-width 250px, ellipsis
.positive: green (#00c853)
.negative: red (#ff1744)
```

### 11.8 Readthrough Bar Chart (CSS-only)

```
.rt-card:
  background: #141414, border: 1px solid #222
  border-radius: 8px, padding: 1.5rem
  display: flex, flex-direction: column

.rt-bar-chart:
  margin-top: auto  /* anchors to bottom of flex column */

.rt-bars-container:
  display: flex, align-items: flex-end, gap: 4px
  height: 160px (200px if > 10 books), padding-bottom: 28px

.rt-bar-wrap:
  display: flex, flex-direction: column, align-items: center
  flex: 1, min-width: 28px, height: 100%
  justify-content: flex-end, position: relative

.rt-bar:
  width: 100%, border-radius: 3px 3px 0 0, min-height: 2px

.rt-bar-label: position absolute, bottom -24px, font-size 9px, muted
.rt-bar-value: position absolute, top -18px, font-size 9px, #aaa, weight 600
.rt-bar-tooltip: hidden by default, shown on .rt-bar-wrap:hover
```

### 11.9 Readthrough Badges

```
.rt-badge: 0.7rem, padding 0.2rem 0.5rem, border-radius 3px, weight 600, monospace

.rt-green: background rgba(0,200,83,0.15), color #00c853, border rgba(0,200,83,0.3)
.rt-amber: background rgba(255,171,0,0.15), color #ffab00, border rgba(255,171,0,0.3)
.rt-red:   background rgba(255,23,68,0.15),  color #ff1744, border rgba(255,23,68,0.3)
```

### 11.10 KPI Comparison Row

```
.kpi-comparison:
  display: flex, gap: 1.5rem, flex-wrap: wrap
  padding: 0.75rem 1rem
  background: rgba(245,197,24,0.05)
  border: 1px solid rgba(245,197,24,0.15)
  border-radius: 6px, margin-top: 0.75rem
  font-size: 0.8rem, color: secondary
```

### 11.11 Warning Box

```
.warning-box:
  background: rgba(255,171,0,0.08)
  border: 1px solid rgba(255,171,0,0.3)
  border-radius: 8px, padding: 1.5rem, margin-top: 1.5rem

h4: amber colour
p: secondary colour, 0.85rem
li: 0.85rem, primary colour
```

### 11.12 Responsive Breakpoints

```
@media (max-width: 768px):
  .container: padding 1rem
  .kpi-grid: 2 columns
  .two-col: 1 column
  .rt-grid: 1 column
  .header: flex-direction column, gap 1rem, text-align center
```

---

## 12. File & Project Structure

```
vinci-dashboard-app/
├── app/
│   ├── (auth)/
│   │   ├── login/
│   │   │   └── page.tsx          # Login form
│   │   └── reset-password/
│   │       └── page.tsx          # Password reset
│   ├── (dashboard)/
│   │   ├── layout.tsx            # Auth-protected layout with header
│   │   ├── page.tsx              # Main dashboard page
│   │   └── admin/
│   │       └── budget/
│   │           └── page.tsx      # Budget admin page
│   └── api/
│       ├── refresh/
│       │   └── route.ts          # Cron-triggered data refresh
│       └── budget/
│           └── route.ts          # Budget CRUD API
├── components/
│   ├── layout/
│   │   ├── Header.tsx
│   │   └── Footer.tsx
│   ├── dashboard/
│   │   ├── PortfolioOverview.tsx  # Tabbed KPI section
│   │   ├── PortfolioPulse.tsx     # 6 live KPI cards
│   │   ├── BudgetWidget.tsx       # Budget vs actual
│   │   ├── AdEfficiency.tsx       # 3-tier ad table
│   │   ├── MarketBreakdown.tsx    # Country table
│   │   ├── ReadthroughFunnels.tsx # Bar chart cards
│   │   ├── AuthorRanking.tsx      # Author RT table
│   │   └── BsrCorrelation.tsx     # BSR revenue table
│   └── ui/
│       ├── KpiCard.tsx
│       ├── PeriodTabs.tsx
│       ├── DataTable.tsx
│       ├── RtBarChart.tsx
│       ├── RtBadge.tsx
│       └── BudgetProgressBar.tsx
├── lib/
│   ├── publisherchamp.ts          # PC API client
│   ├── supabase.ts                # Supabase client (server)
│   ├── supabase-browser.ts        # Supabase client (browser)
│   ├── analytics/
│   │   ├── series.ts              # Series economics computation
│   │   ├── readthrough.ts         # Readthrough funnel computation
│   │   ├── adEfficiency.ts        # Ad efficiency tiers
│   │   ├── marketBreakdown.ts     # Country breakdown
│   │   ├── bsrCorrelation.ts      # BSR-revenue correlation
│   │   ├── portfolioPulse.ts      # Pulse KPIs + top mover
│   │   └── budget.ts              # Budget pacing calculation
│   └── formatters.ts              # fmt_currency, fmt_pct, fmt_number
├── middleware.ts                  # Auth protection middleware
├── tailwind.config.js             # Custom colour tokens
├── .env.local                     # Secrets (not committed)
└── package.json
```

---

## 13. Deployment Runbook (Ubuntu VM)

The application is deployed on the Ubuntu VM at IP `34.26.132.30`. Follow these steps:

### 13.1 Prerequisites

```bash
# Install Node.js 20 LTS
curl -fsSL https://deb.nodesource.com/setup_20.x | sudo -E bash -
sudo apt-get install -y nodejs

# Install PM2 process manager
sudo npm install -g pm2

# Install Nginx
sudo apt-get install -y nginx

# Install Certbot for SSL
sudo apt-get install -y certbot python3-certbot-nginx
```

### 13.2 Application Setup

```bash
# Clone the repository
git clone https://github.com/marksmith-jpg/vinci-dashboard.git /opt/vinci-dashboard-app
cd /opt/vinci-dashboard-app

# Install dependencies
npm install

# Create .env.local with all required environment variables
nano .env.local

# Build the Next.js application
npm run build

# Start with PM2
pm2 start npm --name "vinci-dashboard" -- start
pm2 save
pm2 startup  # follow the printed command to enable auto-start on reboot
```

### 13.3 Nginx Configuration

```nginx
# /etc/nginx/sites-available/vinci-dashboard
server {
    listen 80;
    server_name 34.26.132.30;  # Replace with domain name if available

    location / {
        proxy_pass http://localhost:3000;
        proxy_http_version 1.1;
        proxy_set_header Upgrade $http_upgrade;
        proxy_set_header Connection 'upgrade';
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_cache_bypass $http_upgrade;
    }
}
```

```bash
sudo ln -s /etc/nginx/sites-available/vinci-dashboard /etc/nginx/sites-enabled/
sudo nginx -t
sudo systemctl reload nginx
```

### 13.4 SSL Certificate

If a domain name is pointed at the VM:

```bash
sudo certbot --nginx -d yourdomain.com
```

For IP-only access (no domain), use a self-signed certificate:

```bash
sudo openssl req -x509 -nodes -days 365 -newkey rsa:2048 \
  -keyout /etc/ssl/private/vinci.key \
  -out /etc/ssl/certs/vinci.crt \
  -subj "/CN=34.26.132.30"
```

Then update the Nginx config to use `listen 443 ssl` with the certificate paths.

### 13.5 Cron Setup

```bash
# Edit crontab
crontab -e

# Add this line (5 AM UK time, using TZ prefix)
TZ=Europe/London
0 5 * * * curl -s -X POST http://localhost:3000/api/refresh \
  -H "x-cron-secret: YOUR_CRON_SECRET" >> /var/log/vinci-refresh.log 2>&1
```

### 13.6 Updating the Application

```bash
cd /opt/vinci-dashboard-app
git pull origin main
npm install
npm run build
pm2 restart vinci-dashboard
```

---

## 14. Claude Build Prompt

The following prompt is ready to paste into a fresh Claude session. It is self-contained and references this specification document.

---

```
You are an expert Next.js 14 and Supabase developer. I need you to build the "Vinci Daily BSR Dashboard" — a live, login-protected web application for Vinci Books Ltd that replaces an existing Python-generated static HTML report.

I have attached the full specification document (Vinci_Dashboard_Web_App_Spec.md). Please read it carefully before writing any code. It contains every business logic rule, calculation, API field name, design token, and deployment instruction you need.

Here is a summary of what you are building:

**What it is:**
A daily publishing analytics dashboard for a digital-first book publisher. It shows revenue, KENP reads, ad spend, series readthrough funnels, ad efficiency tiers, market breakdown, and BSR-revenue correlation. Data comes from Publisher Champ API and Supabase BSR tracking.

**Tech stack:**
- Next.js 14 (App Router) + TypeScript + Tailwind CSS
- Supabase for auth, database, and BSR data storage
- Deployed on Ubuntu VM (34.26.132.30) with PM2 + Nginx + HTTPS

**Key requirements:**
1. Supabase Auth with individual user accounts (5 users initially). Login page, middleware protection on all routes, password reset, logout. No public registration.
2. Daily data refresh at 5 AM UK time via a protected POST /api/refresh endpoint triggered by system cron.
3. All business logic from the Python script must be replicated exactly — particularly:
   - Step-by-step series readthrough (NOT cumulative vs Book 1). Exclude prequels/novellas by keyword. Exclude inverted funnels (B1→B2 > 100%). Minimum 5,000 KENP for Book 1.
   - Top Mover: both previous AND current BSR must be ≤ 100,000. Weighted score = improvement × (1 / log10(curr_bsr)).
   - Ad Efficiency: 3 tiers (ROI ≥300%, 200-300%, <100%). The 100-200% range is intentionally excluded. Minimum £1K gross. Burning Money sorted by absolute £ loss.
   - BSR-Revenue Correlation: average BSR across all tracked days. Exclude perma-free (free_units > 10 AND gross < £10).
   - Currency formatting: minus sign BEFORE pound sign (-£1,500 not £-1,500).
   - Large percentages: comma-formatted (+26,311.8%).
4. Dashboard sections in order: Portfolio Overview (tabs: MTD/30-Day/90-Day/YTD/FY2025/FY2024/Lifetime) → Portfolio Pulse (6 KPIs) → Budget vs Actual → Ad Efficiency → Market Breakdown → Series Readthrough Funnels → Author RT Ranking → BSR-Revenue Correlation.
5. NEW Budget/Reforecast feature: Admin page to set monthly revenue targets and ad spend budgets. Dashboard widget showing actual vs target with pacing indicator ("on track to hit 112% of target").
6. Dark theme exactly matching the design tokens in the spec: background #0a0a0a, cards #141414, gold accent #F5C518, green #00c853, red #ff1744, amber #ffab00.
7. Readthrough bar charts must be pure CSS (no Chart.js), bottom-anchored, with bars coloured by step retention benchmarks.

**Supabase tables to create:**
- `bsr_snapshots` (already exists — BSR tracking data)
- `dashboard_cache` (new — stores pre-computed JSON per period)
- `budget_targets` (new — monthly revenue/spend targets)
- `daily_snapshots` (new — daily portfolio summary for trend tracking)

**Environment variables (use these names exactly):**
PUBLISHER_CHAMP_EMAIL, PUBLISHER_CHAMP_PASSWORD, PUBLISHER_CHAMP_API_KEY, PUBLISHER_CHAMP_ACCOUNT_ID, PUBLISHER_CHAMP_BASE_URL, SUPABASE_URL, SUPABASE_KEY, NEXT_PUBLIC_SUPABASE_URL, NEXT_PUBLIC_SUPABASE_ANON_KEY, NEXTAUTH_SECRET, CRON_SECRET

**Reference files:**
- GitHub repo: https://github.com/marksmith-jpg/vinci-dashboard
- The Python script generate_daily_bsr_report_v19.py contains all business logic
- The HTML file Vinci_Daily_BSR_Report_v19.html shows the exact UI to replicate

**Please build in this order:**
1. Scaffold the Next.js project with Tailwind and the custom colour tokens.
2. Set up Supabase auth (login page, middleware, password reset, logout).
3. Create the Supabase database schema (SQL migrations for the 3 new tables with RLS policies).
4. Build the Publisher Champ API client with retry logic and the data refresh endpoint.
5. Implement all business logic functions (series economics, readthrough, ad efficiency, market breakdown, BSR correlation, portfolio pulse).
6. Build each dashboard section component in order, matching the design system exactly.
7. Build the Budget/Reforecast admin page and dashboard widget.
8. Provide the complete deployment runbook for the Ubuntu VM (PM2 + Nginx + SSL + cron).

Start with step 1 and work through each step completely before moving to the next. Show me the full file contents for each file you create.
```

---

*End of Specification Document*
