import os
import sys
import time
import certifi
import requests
import pandas as pd
from io import StringIO
from datetime import date, timedelta
from dotenv import load_dotenv
from google.cloud import storage
from google.cloud import bigquery

load_dotenv()

BUCKET_NAME   = os.environ.get("GCP_BUCKET_NAME", "earthquake-analytics-raw")
BQ_PROJECT_ID = os.environ.get("GCP_PROJECT_ID")
BQ_DATASET    = os.environ.get("GCP_DATASET", "earthquake_analytics")
BQ_TABLE      = "earthquakes_raw"

storage_client = storage.Client()
bq_client      = bigquery.Client(project=BQ_PROJECT_ID)

DTYPE = {  
    "latitude": "float64",
    "longitude": "float64",
    "depth": "float64",
    "mag": "float64",
    "magType": "string",
    "nst": "float64",
    "gap": "float64",
    "dmin": "float64",
    "rms": "float64",
    "net": "string",  
    "id": "string",   
    "place": "string",    
    "type": "string",
    "horizontalError": "float64",
    "depthError": "float64",
    "magError": "float64",
    "magNst": "float64",
    "status": "string",    
    "locationSource": "string",   
    "magSource": "string"
}

PARSE_DATES = [
    "time",
    "updated"
]

BASE_URL = 'https://earthquake.usgs.gov/fdsnws/event/1/query.csv'

def read_csv_url(url):
    # Fetch CSV from URL, handling macOS SSL issues.
    if sys.platform == "darwin":
        response = requests.get(url, verify=certifi.where())
        response.raise_for_status()
        return pd.read_csv(StringIO(response.text), dtype=DTYPE, parse_dates=PARSE_DATES)
    return pd.read_csv(url, dtype=DTYPE, parse_dates=PARSE_DATES)

def upload_to_gcs(local_path, gcs_path, skip_existing=False):
    bucket = storage_client.bucket(BUCKET_NAME)
    blob = bucket.blob(gcs_path)
    
    if skip_existing and blob.exists():
        print(f"  Already exists, skipping: {gcs_path}")
        os.remove(local_path)
        return
        
    blob.upload_from_filename(local_path)
    print(f"  Uploaded to gs://{BUCKET_NAME}/{gcs_path}")
    os.remove(local_path)

def fetch_month(current_year, current_month, next_year, next_month):
    """Fetch one month, splitting into halves or thirds if over the 20k row limit."""
    url = (
        f"{BASE_URL}"
        f"?starttime={current_year}-{current_month:02}-01"
        f"&endtime={next_year}-{next_month:02}-01"
    )
    
    try:
        df = read_csv_url(url)
        return [df]
    
    except Exception as e:
        if "400" in str(e) or "Bad Request" in str(e):
            print(f"  Too many rows, splitting into halves...")
            try:
                return fetch_month_in_halves(current_year, current_month)
            except Exception as e2:
                if "400" in str(e2) or "Bad Request" in str(e2):
                    print(f"  Still too many rows, splitting into thirds...")
                    return fetch_month_in_thirds(current_year, current_month)
                raise
        raise


def fetch_month_in_halves(year, month):
    """Split a month into first and second half."""
    import calendar
    mid_day = 15

    if month == 12:
        next_year, next_month = year + 1, 1
    else:
        next_year, next_month = year, month + 1

    url_first = (
        f"{BASE_URL}"
        f"?starttime={year}-{month:02}-01"
        f"&endtime={year}-{month:02}-{mid_day}"
    )
    url_second = (
        f"{BASE_URL}"
        f"?starttime={year}-{month:02}-{mid_day}"
        f"&endtime={next_year}-{next_month:02}-01"
    )

    dfs = []
    for url in [url_first, url_second]:
        df = read_csv_url(url)
        dfs.append(df)
        print(f"  Fetched {len(df)} rows from {url.split('starttime=')[1].split('&')[0]}")
    
    return dfs


def fetch_month_in_thirds(year, month):
    """Split a month into three parts."""
    import calendar
    last_day = calendar.monthrange(year, month)[1]
    day1 = 11  # days 1-10
    day2 = 21  # days 11-20
                # days 21-end

    if month == 12:
        next_year, next_month = year + 1, 1
    else:
        next_year, next_month = year, month + 1

    url_first  = f"{BASE_URL}?starttime={year}-{month:02}-01&endtime={year}-{month:02}-{day1}"
    url_second = f"{BASE_URL}?starttime={year}-{month:02}-{day1}&endtime={year}-{month:02}-{day2}"
    url_third  = f"{BASE_URL}?starttime={year}-{month:02}-{day2}&endtime={next_year}-{next_month:02}-01"

    dfs = []
    for url in [url_first, url_second, url_third]:
        df = read_csv_url(url)
        dfs.append(df)
        print(f"  Fetched {len(df)} rows from {url.split('starttime=')[1].split('&')[0]}")
    
    return dfs


def fetch_and_upload(current_year, current_month, next_year, next_month, prefix="historical"):
    print(f"Fetching {current_year}-{current_month:02}...")
    time.sleep(0.5)  # avoid hammering USGS API on sparse early centuries, comment out if you want to load the data from 1950+

    try:
        dfs = fetch_month(current_year, current_month, next_year, next_month)
        
        if not dfs or all(df.empty for df in dfs):
            print(f"  No data, skipping.")
            return

        # combine halves if split, or just use single df
        df = pd.concat(dfs, ignore_index=True) if len(dfs) > 1 else dfs[0]
        
        filename = f"earthquake-{current_year}-{current_month:02}.parquet"
        df.to_parquet(filename, index=False, coerce_timestamps='us')
        upload_to_gcs(filename, f"{prefix}/{filename}", skip_existing=True)

    except Exception as e:
        print(f"  Failed {current_year}-{current_month:02}: {e}")

def historical_load(start_year, start_month, end_year, end_month):
    current_year, current_month = start_year, start_month

    while (current_year, current_month) <= (end_year, end_month):
        if current_month == 12:
            next_year, next_month = current_year + 1, 1
        else:
            next_year, next_month = current_year, current_month + 1

        fetch_and_upload(current_year, current_month, next_year, next_month, prefix="historical")

        current_year, current_month = next_year, next_month

def incremental_load():
    """
    Two API calls:
    1. New earthquakes since MAX(time) in BigQuery
    2. Revised records updated since yesterday
    Both are appended to the raw table — dbt deduplicates on updated DESC.
    """
    today = date.today()
    yesterday = today - timedelta(days=1)

    # --- get last loaded time from BigQuery ---
    query = f"""
        SELECT MAX(time) as max_time
        FROM `{BQ_PROJECT_ID}.{BQ_DATASET}.{BQ_TABLE}`
    """
    result = bq_client.query(query).result()
    max_time = next(result).max_time

    if max_time is None:
        print("BigQuery table is empty, will upload the data for 1 day only")
        start_date = yesterday
    else:
        start_date = max_time.date().isoformat()
        print(f"Last loaded time in BigQuery: {start_date}")

    # --- call 1: new earthquakes ---
    print(f"Fetching new earthquakes from {start_date} to {today}...")
    url_new = (
        f"{BASE_URL}"
        f"?starttime={start_date}"
        f"&endtime={today}"
    )
    try:
        df_new = read_csv_url(url_new)
        print(f"  Fetched {len(df_new)} new records")
    except Exception as e:
        print(f"  Failed to fetch new earthquakes: {e}")
        df_new = pd.DataFrame()

    # --- call 2: revised records updated since yesterday ---
    print(f"Fetching revised records updated since {yesterday}...")
    url_revised = (
        f"{BASE_URL}"
        f"?updatedafter={yesterday}"
        f"&starttime=1568-01-01"
        f"&endtime={today}"
    )
    try:
        df_revised = read_csv_url(url_revised)
        print(f"  Fetched {len(df_revised)} revised records")
    except Exception as e:
        print(f"  Failed to fetch revised records: {e}")
        df_revised = pd.DataFrame()

    # --- combine and upload ---
    dfs = [df for df in [df_new, df_revised] if not df.empty]

    if not dfs:
        print("No new or revised records found, skipping.")
        return

    df = pd.concat(dfs, ignore_index=True).drop_duplicates(subset="id", keep="last")
    print(f"  Combined: {len(df)} records to upload")

    filename = f"earthquake-incremental-{yesterday}.parquet"
    df.to_parquet(filename, index=False, coerce_timestamps='us')
    upload_to_gcs(filename, f"incremental/{filename}", skip_existing=False)


if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument("--mode", choices=["historical", "incremental"], default=None)
    parser.add_argument("--start-year",  type=int, default=1973)
    parser.add_argument("--start-month", type=int, default=1)
    parser.add_argument("--end-year",    type=int, default=2026)
    parser.add_argument("--end-month",   type=int, default=3)
    args = parser.parse_args()

    if args.mode == "historical":
        historical_load(args.start_year, args.start_month, args.end_year, args.end_month)
    elif args.mode == "incremental":
        incremental_load()
    else:
        historical_load(
            int(input("Set what year you want to start from: ")),
            int(input("Set what month number you want to start from (1-12): ")),
            int(input("Set what year you want to end with: ")),
            int(input("Set what month number you want to end with (1-12): "))
        )