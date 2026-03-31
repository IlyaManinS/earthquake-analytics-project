# Earthquake Analytics

## Problem Statement

Earthquakes are one of the most destructive natural phenomena on Earth, yet the patterns behind where and when they occur are not always well understood outside the scientific community. This project asks: **where and when do earthquakes happen, and has global seismic activity changed over time?**

The USGS maintains a public earthquake catalog going back to 1568, but accessing it in bulk requires making hundreds of individual API requests, handling pagination limits, managing partial failures, and dealing with ongoing record revisions. Without an automated pipeline, downloading and keeping this data up to date would be a manual, error-prone process. This project solves that by building an end-to-end pipeline that handles ingestion, deduplication, transformation, and daily updates automatically.

To answer the core question, the project ingests the full USGS Earthquake Catalog spanning from 1568 to the present day, over 4.8 million records, via the USGS public API. Raw data is stored as Parquet files in Google Cloud Storage, then loaded into a partitioned and clustered BigQuery table. Because USGS continuously revises earthquake records after publication (updating magnitudes, depths, and locations), the pipeline handles both new events and revised records on every daily run, deduplicating them in the transformation layer.

The data is then transformed using dbt across three layers: staging cleans and deduplicates the raw records; the intermediate layer enriches them with derived fields such as region, magnitude category, depth category, and geographic quadrant; and mart models aggregate the data into dashboard-ready tables. The final output is a Looker Studio dashboard that allows users to explore seismic activity by region, magnitude, depth, and time period.

---

## Stack

| Layer | Tool | Reason |
|-------|------|--------|
| IaC | Terraform | Reproducibility, provisions all GCP resources |
| Data Lake | GCS | Raw Parquet storage |
| Data Warehouse | BigQuery | Partitioned and clustered tables |
| Orchestration | Kestra (local Docker) | DAG scheduling and flow management |
| Transformation | dbt Core | Staging, intermediate and mart models |
| Dashboard | Looker Studio | Free, native BigQuery connector |

---

<img width="598" height="439" alt="image" src="https://github.com/user-attachments/assets/9b650b06-3328-4384-ac03-03d34c860728" />


## Quick Start

1. **GCP**: create a project, two service accounts (Terraform + pipeline), download their JSON keys
2. **Terraform**: provision GCS bucket and BigQuery dataset (`terraform init && terraform apply`)
3. **Kestra**: encode your service account, start Docker (`docker-compose up -d`), run `01_gcp_kv` flow
4. **Historical load**: run `02_historical_load` flow in Kestra (ingests USGS data, creates BQ table, loads from GCS) (if you run the ingestion script manually via Python run `03_create_table_and_load` flow after if you want to work with the historical data only)
5. **Incremental load**: if you want to see how the increments work without dbt transformations, run `04_incremental_load.yml` with the commented out dbt section
6. **dbt**: configure `~/.dbt/profiles.yml`, then `dbt seed && dbt run && dbt test`
7. **Incremental with dbt transformation**: uncomment the dbt step in `04_incremental_load.yml`; daily runs are automatic while Docker is running
8. **Dashboard**: connect Looker Studio to the BigQuery mart tables

Each step is detailed in the sections below.

---

## Repo Structure

```
earthquake-analytics-project/
├── terraform/                        # GCS bucket + BQ dataset provisioning
│   ├── terraform.tfvars.example      # shows expected Terraform vars
├── ingestion/                        # Python ingestion script
│   ├── ingest_earthquake_data.py
│   ├── keys/                         # gitignored — place service account JSON here
├── orchestration/                    # Kestra YAML flows
│   └── flows/
│       ├── 01_gcp_kv.yml             # GCP connection config (placeholder values)
│       ├── 02_historical_load.yml    # runs historical ingestion + creates BQ table
│       ├── 03_create_table_and_load.yml  # creates BQ table from existing GCS files
│       └── 04_incremental_load.yml   # scheduled daily incremental load
├── dbt/                              # dbt project
│   ├── models/
│   │   ├── staging/
│   │   │   ├── sources.yml
│   │   │   ├── schema.yml
│   │   │   └── stg_earthquakes.sql
│   │   ├── intermediate/
│   │   │   ├── schema.yml
│   │   │   └── int_earthquakes.sql
│   │   └── marts/
│   │       ├── schema.yml
│   │       ├── mart_earthquakes_by_region.sql
│   │       ├── mart_earthquakes_over_time.sql
│   │       └── mart_significant_earthquakes.sql
│   ├── macros/
│   │   ├── filter_earthquakes.sql
│   │   └── earthquake_agg_metrics.sql
│   ├── seeds/
│   │   └── state_abbreviations.csv
│   └── dbt_project.yml
├── requirements.txt                  # Python dependencies
├── docker-compose.yml                # Kestra local setup
├── .env_encoded.example              # shows expected env var format
├── .env.example                      # shows expected env var format
├── .gitignore
└── README.md
```

---

## Prerequisites

- [Docker Desktop](https://www.docker.com/products/docker-desktop/)
- [Terraform](https://developer.hashicorp.com/terraform/install)
- [Python 3.11+](https://www.python.org/downloads/)
- [dbt Core](https://docs.getdbt.com/docs/core/installation) (`pip install dbt-bigquery`)
- A GCP account with billing enabled
- A GCP project created

---

## GCP Setup

### 1. Create Service Accounts

It is recommended to use separate service accounts per tool following least privilege:

| SA Name | Used By | Permissions |
|---------|---------|-------------|
| `terraform-account` | Terraform | Storage Admin, BigQuery Admin |
| `pipeline-account` | Kestra + Ingestion + dbt | Storage Object Admin, BigQuery Data Editor + Job User |

Download the JSON key file and place it in `ingestion/keys/` — this folder is gitignored.

### 2. Set Credentials Locally

```bash
# set once per session
export GOOGLE_APPLICATION_CREDENTIALS=~/path/to/your/service-account.json

# or add to ~/.zshrc or ~/.bashrc for permanent setup
export GOOGLE_APPLICATION_CREDENTIALS=~/path/to/your/service-account.json
```

---

## Terraform

Provisions the GCS bucket and BigQuery dataset.

### Setup

```bash
cd terraform
cp terraform.tfvars.example terraform.tfvars
# edit terraform.tfvars with your GCP project ID and bucket name
```

### Run

```bash
terraform init
terraform plan
terraform apply
```

### terraform.tfvars.example
```hcl
project         = "your-gcp-project-id"
gcs_bucket_name = "your-unique-bucket-name"
```

Note: `terraform destroy` will delete the bucket and all data, dev only due to `force_destroy = true`.

---

## Kestra

Kestra runs locally via Docker and orchestrates the full pipeline.

### 1. Encode Your Service Account

```bash
# macOS
echo SECRET_GCP_SERVICE_ACCOUNT=$(cat path/to/your-service-account.json | base64) > .env_encoded

# Linux
echo SECRET_GCP_SERVICE_ACCOUNT=$(cat path/to/your-service-account.json | base64 -w 0) > .env_encoded
```

Note: `-w 0` is Linux only, macOS base64 does not wrap by default.

This creates a `.env_encoded` file in the root of the repo. It is gitignored and should never be committed. See `.env_encoded.example` for the expected format.

### 2. Start Kestra

```bash
docker-compose up -d
```

Open the Kestra UI at `http://localhost:8080`

### 3. Configure GCP Connection

Open `orchestration/flows/01_gcp_kv.yml`, update the placeholder values with your GCP project details, and run the flow in the Kestra UI. This stores your config in Kestra's KV store.

```yaml
# values to update in 01_gcp_kv.yml
GCP_PROJECT_ID:   your-gcp-project-id
GCP_LOCATION:     US
GCP_BUCKET_NAME:  your-unique-bucket-name
GCP_DATASET:      earthquake_analytics
```

Note: `GCP_SERVICE_ACCOUNT` is loaded automatically from `.env_encoded` via Docker Compose — you do not set this in the UI.

### Flows

| Flow | Purpose | Trigger |
|------|---------|---------|
| `01_gcp_kv.yml` | Sets GCP config in KV store | Manual, once |
| `02_historical_load.yml` | Runs historical ingestion, creates partitioned BQ table, loads GCS data | Manual, once |
| `03_create_table_and_load.yml` | Creates BQ table and loads from GCS (if ingestion already ran manually) | Manual, as needed |
| `04_incremental_load.yml` | Fetches new and revised records from USGS, loads to BQ, runs dbt | Scheduled, daily 01:00 UTC |

Note: the daily scheduled run in `04_incremental_load.yml` only fires while Docker and Kestra are running. If Docker was stopped and runs were missed, the incremental script is self-healing, it queries `MAX(time)` from BigQuery on each run to determine where to resume from.

### Kestra Flow Setup Notes
- In flow files `02` and `04`, update `GOOGLE_APPLICATION_CREDENTIALS` to point to your service account file — keep `/app/project` as the prefix e.g. `/app/project/ingestion/keys/your-sa-file.json`
- Flows use `taskRunner: type: io.kestra.plugin.core.runner.Process` so the Python tasks can access the mounted project volume at `/app/project`
- The dbt run step in `04_incremental_load.yml` is commented out by default, uncomment it after completing the dbt setup section below, otherwise the flow will fail

---

## Ingestion

The ingestion script fetches earthquake data from the [USGS Earthquake Catalog API](https://earthquake.usgs.gov/fdsnws/event/1/) and uploads it to GCS as Parquet files.

### Install Dependencies

```bash
pip install -r requirements.txt
```

### Environment Variables

Copy `.env.example` to `.env` and fill in your values:

```bash
cp .env.example .env
```

```bash
GOOGLE_APPLICATION_CREDENTIALS=path/to/your-service-account.json
GCP_PROJECT_ID=your-gcp-project-id
GCP_DATASET=earthquake_analytics
GCP_BUCKET_NAME=your-unique-bucket-name
```

### GCS Path Structure

```
gs://your-bucket-name/
    historical/
        earthquake-1568-01.parquet
        earthquake-1568-02.parquet
        ...
    incremental/
        earthquake-incremental-2026-03-29.parquet
```

### Run Manually (Interactive)

```bash
python ingestion/ingest_earthquake_data.py
# you will be prompted for start year, start month (number 1-12), end year, end month
```

### Run via Argparse (Kestra / CI)

```bash
# historical backfill with explicit date range
# note: when running via Kestra, start and end dates are set as inputs in the flow YAML
python ingestion/ingest_earthquake_data.py --mode historical --start-year 1568 --start-month 1 --end-year 2026 --end-month 3

# incremental load (queries MAX(time) from BigQuery automatically)
python ingestion/ingest_earthquake_data.py --mode incremental
```

### Key Design Decisions

- CSV is converted to Parquet before uploading. Parquet is columnar, compressed, and preserves the schema.
- `coerce_timestamps='us'` is used in all `to_parquet()` calls because BigQuery rejects nanosecond precision timestamps.
- One Parquet file per month is written to GCS for historical data. Incremental runs write one file per day.
- `skip_existing=True` is set for the historical load so the script is safe to re-run without re-uploading existing files.
- Months with more than 20k rows hit the USGS API limit and are automatically split into halves, then thirds if halves are still too large.
- The incremental load queries `MAX(time)` from BigQuery on each run rather than relying on the schedule, making it self-healing if runs are missed.
- Each incremental run makes two API calls: one for new earthquakes since `MAX(time)`, and one for revised records via `?updatedafter={yesterday}`.
- A 0.5s sleep is added between requests to avoid hitting USGS API rate limits when looping through sparse early centuries.

### Known High-Volume Months
- 2018-06, 2018-07 — handled by halves split
- 2019-07 — Ridgecrest earthquake sequence (39,458 rows), needed thirds split
- 2020-05, 2020-06 — handled by halves split

---

## BigQuery Design

- Partition by: `DATE_TRUNC(time, MONTH)` — well within the 4,000 partition limit
- Cluster by: `type`, `place` — supports filtering by event type and region
- Raw table is created and loaded automatically by the Kestra pipeline

### Why These Cluster Columns

`mag` (FLOAT64) is not supported for clustering in BigQuery. Instead:
- `type` — 6 unique values (earthquake, quarry blast, explosion etc.) co-locates rows efficiently
- `place` — high cardinality, useful for regional queries

Magnitude-based filtering is handled in the dbt mart layer via a derived `magnitude_category` column.

### Non-Earthquake Events

The raw table contains multiple event types including quarry blasts, explosions and nuclear tests. All mart models filter to `event_type = 'earthquake'` and `magnitude IS NOT NULL` via the `filter_earthquakes()` dbt macro.

### Handling Updated Records

USGS revises earthquake records after the fact (magnitude updates, location refinements). The incremental load handles this via two API calls:

```python
# new earthquakes
?starttime={last_loaded_date}&endtime={today}

# revised records
?updatedafter={yesterday}&starttime=1568-01-01&endtime={today}
```

The dbt staging model deduplicates by `id`, keeping the most recently updated record using `ROW_NUMBER() OVER (PARTITION BY id ORDER BY updated DESC)`.

---

## dbt

Transforms raw data into dashboard-ready models across three layers.

### Setup

```bash
pip install dbt-bigquery
```

Create `~/.dbt/profiles.yml`:

```yaml
earthquake_analytics:
  target: dev
  outputs:
    dev:
      type: bigquery
      method: service-account
      project: your-gcp-project-id
      dataset: earthquake_analytics
      keyfile: path/to/your/service-account.json
      location: US
      threads: 4
```

Note: `profiles.yml` is never committed — it lives only on your local machine at `~/.dbt/`. A repo-level `dbt/profiles.yml` using environment variables is provided for Kestra runs.

### Run

```bash
cd dbt
dbt debug       # verify connection to BigQuery
dbt seed        # load state abbreviations lookup table
dbt run         # build all models
dbt test        # run all tests
```

### Model Layers

```
staging/
  stg_earthquakes          # deduplicate, rename columns, trim and lowercase strings

intermediate/
  int_earthquakes          # add region, magnitude_category, depth_category, quadrant
                           # drop quality measurement columns
                           # resolve state abbreviations via seed lookup

marts/
  mart_earthquakes_by_region      # aggregated by region, quadrant, magnitude and depth category
  mart_earthquakes_over_time      # aggregated by month, magnitude and depth category, quadrant
  mart_significant_earthquakes    # individual events with magnitude >= 6.0
```

### Materialization

| Layer | Materialization |
|-------|----------------|
| Staging | View |
| Intermediate | View |
| Marts | Table |

### Macros

| Macro | Used In | Purpose |
|-------|---------|---------|
| `filter_earthquakes()` | All marts | Filters to `event_type = 'earthquake' AND magnitude IS NOT NULL` |
| `earthquake_agg_metrics()` | by_region, over_time | Standard count and avg/max/min magnitude aggregations |

### Seeds

| Seed | Purpose |
|------|---------|
| `state_abbreviations.csv` | Maps US state abbreviations (CA, AK etc.) to full names for region normalisation |

### Derived Columns

**`region`** — extracted from USGS `place` field:
- Comma-separated — everything after last comma
- "X region" suffix — stripped
- State abbreviations — resolved to full name via seed

**`magnitude_category`**

| Category | Range |
|----------|-------|
| Minor | < 2.0 |
| Light | 2.0 – 3.9 |
| Moderate | 4.0 – 5.9 |
| Strong | >= 6.0 |

**`depth_category`** (per [USGS classification](https://www.usgs.gov/programs/earthquake-hazards/determining-depth-earthquake))

| Category | Range |
|----------|-------|
| Shallow | 0 – 70 km |
| Intermediate | 70 – 300 km |
| Deep | 300 – 700 km |

**`quadrant`** — derived from latitude and longitude:

| Quadrant | Condition |
|----------|-----------|
| NE | lat >= 0, lon >= 0 |
| NW | lat >= 0, lon < 0 |
| SE | lat < 0, lon >= 0 |
| SW | lat < 0, lon < 0 |

---

## Dashboard

Built in Looker Studio, connected directly to BigQuery mart models.

**Tiles:**
1. Bar Chart distribution of earthquakes by region with magnitude category breakdown (categorical)
   
   <img width="2252" height="1578" alt="image" src="https://github.com/user-attachments/assets/bbb7eeb5-a93d-43e4-95e3-5794180fca5e" />

   
3. Earthquake count with average magnitude over time since 1990 (temporal)
   
   <img width="1960" height="1204" alt="image" src="https://github.com/user-attachments/assets/24b9b97e-0d7f-46b0-b3d6-e5344f8f4b40" />
   

4. Significant earthquakes map (magnitude >= 6.0)
   
   <img width="2646" height="1338" alt="image" src="https://github.com/user-attachments/assets/66e3e310-a97a-4793-a5c6-385af79d249c" />

