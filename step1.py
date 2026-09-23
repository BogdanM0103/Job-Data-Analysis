import requests
import json
import time
import pandas as pd
from typing import Any, cast
from bs4 import BeautifulSoup

def parse_job(job_data: dict[str, Any]) -> dict[str, Any]:
    # Step A: grab the nested parts first, each with a safe fallback
    company = job_data.get("hiringOrganization", {})
    salary = job_data.get("baseSalary", {})
    salary_value = salary.get("value", {})

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
    }
    return row

def scrape_job_posting(url: str) -> dict[str, Any] | None:
    response = requests.get(url, timeout=30)
    if response.status_code == 200:
        soup = BeautifulSoup(response.text, 'html.parser')
        script_tag = soup.find('script', type='application/ld+json')
        if script_tag and script_tag.string:
            data = json.loads(script_tag.string)
            for item in data.get("@graph", []):
                if item.get("@type") == "JobPosting":
                    return parse_job(item)
    return None

def get_job_urls(sitemap_url: str) -> list[str]:
    response = requests.get(sitemap_url, timeout=30)
    if response.status_code == 200:
        soup = BeautifulSoup(response.text, 'xml')
        urls = [loc.text for loc in soup.find_all('loc')]
        return urls
    return []

url = "https://www.ejobs.ro/sitemap-listings-it-software.xml"

rows: list[dict[str, Any]] = []

first_5_jobs_urls = get_job_urls(url)[:5]
for i, job_url in enumerate(first_5_jobs_urls):
    print(f"Scraping {i + 1}/{len(first_5_jobs_urls)}: {job_url}")
    job_data = None
    try:
        job_data = scrape_job_posting(job_url)
        if job_data is not None:
            rows.append(job_data)
    except requests.RequestException as e:
        print("Failed:", job_url, e)
    time.sleep(1)

print(len(rows))

df = pd.DataFrame(rows)
df.head()
df.info()
df.to_csv("jobs.csv", index=False, encoding="utf-8-sig")