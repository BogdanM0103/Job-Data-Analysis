import requests
import json
import time
import pandas as pd
from typing import Any, cast
from bs4 import BeautifulSoup

# --- settings ---
SITEMAP_INDEX_URL = "https://www.ejobs.ro/sitemap-listings-index.xml"
SITEMAPS_CSV = "sitemaps.csv"
JOBS_CSV = "jobs.csv"
SITEMAP_DELAY = 1      # seconds between sitemap requests
JOB_DELAY = 0.5        # seconds between job page requests
SAVE_EVERY = 100       # save progress to CSV every N jobs


# --- helpers ---
def fetch_urls_from_sitemap(sitemap_url: str) -> list[str]:
    response = requests.get(sitemap_url, timeout=30)
    if response.status_code == 200:
        soup = BeautifulSoup(response.text, 'xml')
        return [loc.text for loc in soup.find_all('loc')]
    return []


def parse_job(job_data: dict[str, Any]) -> dict[str, Any]:
    # Step A: grab the nested parts first, each with a safe fallback
    company = job_data.get("hiringOrganization", {})
    salary = job_data.get("baseSalary", {})
    salary_value = salary.get("value", {})
    experience = job_data.get("experienceRequirements", {})
    education = job_data.get("educationRequirements", {})

    # jobLocation is a LIST of places -> take the first one (if the list isn't empty)
    locations = cast(list[dict[str, Any]], job_data.get("jobLocation", []))
    if len(locations) > 0:
        first_location = locations[0]
    else:
        first_location = {}
    address = cast(dict[str, Any], first_location.get("address", {}))

    # Step B: build one flat row (simple values only, no dicts inside)
    row: dict[str, Any] = {
        "title": job_data.get("title"),
        "company": company.get("name"),
        "city": address.get("addressLocality"),
        "salary_min": salary_value.get("minValue"),
        "salary_max": salary_value.get("maxValue"),
        "currency": salary.get("currency"),
        "date_posted": job_data.get("datePosted"),
        "url": job_data.get("url"),
        "employment_type": ", ".join(job_data.get("employmentType", [])),
        "experience_months": experience.get("monthsOfExperience"),
        "education": education.get("credentialCategory"),
        "industry": ", ".join(job_data.get("industry", [])),
        "occupations": ", ".join(job_data.get("relevantOccupation", [])),
        "valid_through": job_data.get("validThrough"),
        "description": job_data.get("description"),
    }
    return row


def scrape_job_posting(url: str) -> dict[str, Any] | None:
    response = requests.get(url, timeout=30)
    if response.status_code in (429, 403):
        print("WARNING: blocked by the site (status", response.status_code, ") - slow down")
    if response.status_code == 200:
        soup = BeautifulSoup(response.text, 'html.parser')
        script_tag = soup.find('script', type='application/ld+json')
        if script_tag and script_tag.string:
            data = json.loads(script_tag.string)
            for item in data.get("@graph", []):
                if item.get("@type") == "JobPosting":
                    return parse_job(item)
    return None


def save_csv(rows: list[dict[str, Any]], path: str) -> None:
    try:
        pd.DataFrame(rows).to_csv(path, index=False, encoding="utf-8-sig")
        print(f"Saved {len(rows)} rows to {path}")
    except PermissionError as e:
        print(f"Could not save {path} (is it open in Excel?):", e)


# --- stages ---
def collect_job_urls() -> list[str]:
    """Stage A: read every category sitemap and return the unique job URLs."""
    sitemap_urls = fetch_urls_from_sitemap(SITEMAP_INDEX_URL)
    print(f"Found {len(sitemap_urls)} category sitemaps")

    all_job_urls: list[str] = []
    sitemap_rows: list[dict[str, Any]] = []
    for i, sitemap_url in enumerate(sitemap_urls):
        category = sitemap_url.replace("https://www.ejobs.ro/sitemap-listings-", "").replace(".xml", "")
        jobs = fetch_urls_from_sitemap(sitemap_url)
        all_job_urls.extend(jobs)
        sitemap_rows.append({
            "category": category,
            "sitemap_url": sitemap_url,
            "job_count": len(jobs),
        })
        print(f"Sitemap {i + 1}/{len(sitemap_urls)}: {category} - {len(jobs)} jobs")
        time.sleep(SITEMAP_DELAY)

    save_csv(sitemap_rows, SITEMAPS_CSV)
    print(pd.DataFrame(sitemap_rows).sort_values("job_count", ascending=False).head(10))

    # the same job can appear in several categories -> drop duplicates, keep order
    unique_urls = list(dict.fromkeys(all_job_urls))
    print("Total job URLs: ", len(all_job_urls))
    print("Unique job URLs:", len(unique_urls))
    return unique_urls


def scrape_jobs(urls: list[str]) -> pd.DataFrame:
    """Stage B: visit every job page (slow, ~2 hours) and save the results."""
    rows: list[dict[str, Any]] = []
    for i, job_url in enumerate(urls):
        print(f"Scraping {i + 1}/{len(urls)}: {job_url}")
        try:
            row = scrape_job_posting(job_url)
            if row is not None:
                rows.append(row)
        except Exception as e:
            print("Failed:", job_url, e)

        if (i + 1) % SAVE_EVERY == 0:
            save_csv(rows, JOBS_CSV)
        time.sleep(JOB_DELAY)

    save_csv(rows, JOBS_CSV)
    return pd.DataFrame(rows)


def main() -> None:
    urls = collect_job_urls()

    # Uncomment to run the slow job scraping (~2 hours):
    # df = scrape_jobs(urls)
    # print(df.head())
    # df.info()


if __name__ == "__main__":
    main()
