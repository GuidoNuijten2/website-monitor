import hashlib
import requests
import csv
import json
import os
import subprocess
from bs4 import BeautifulSoup
from datetime import datetime
import gspread
from google.oauth2.service_account import Credentials

SNAPSHOT_FILE = "snapshots.json"
SHEET_ID = os.environ.get("SHEET_ID")
CREDS_JSON = os.environ.get("GOOGLE_CREDENTIALS")

def get_page_fingerprint(url):
    r = requests.get(url, timeout=15, headers={"User-Agent": "Mozilla/5.0"})
    soup = BeautifulSoup(r.text, "html.parser")
    for tag in soup(["script", "style", "nav", "footer"]):
        tag.decompose()
    text = soup.get_text(separator=" ", strip=True)
    return hashlib.md5(text.encode()).hexdigest()

def save_snapshots_to_repo(snapshots):
    with open(SNAPSHOT_FILE, "w") as f:
        json.dump(snapshots, f)
    subprocess.run(["git", "config", "user.email", "monitor@github-actions.com"])
    subprocess.run(["git", "config", "user.name", "GitHub Actions"])
    subprocess.run(["git", "add", SNAPSHOT_FILE])
    result = subprocess.run(["git", "diff", "--cached", "--quiet"])
    if result.returncode != 0:
        subprocess.run(["git", "commit", "-m", "Update snapshots"])
        subprocess.run(["git", "push"])

def main():
    creds_dict = json.loads(CREDS_JSON)
    creds = Credentials.from_service_account_info(
        creds_dict,
        scopes=["https://www.googleapis.com/auth/spreadsheets"]
    )
    client = gspread.authorize(creds)
    sheet = client.open_by_key(SHEET_ID).sheet1

    snapshots = {}
    if os.path.exists(SNAPSHOT_FILE):
        with open(SNAPSHOT_FILE) as f:
            snapshots = json.load(f)

    with open("companies.csv") as f:
        companies = list(csv.DictReader(f))

    for co in companies:
        name = co["name"]
        url = co["url"]
        print(f"Checking {name}...")
        try:
            new_hash = get_page_fingerprint(url)
            old_hash = snapshots.get(url, {}).get("hash")

            if old_hash and old_hash != new_hash:
                sheet.append_row([name, url, str(datetime.now().date()), "⚠️ Major change detected"])
                print(f"  → Change detected!")
            elif not old_hash:
                print(f"  → First snapshot saved")
            else:
                print(f"  → No change")

            snapshots[url] = {"hash": new_hash, "date": str(datetime.now())}
        except Exception as e:
            print(f"  → Error: {e}")
            sheet.append_row([name, url, str(datetime.now().date()), f"❌ Error: {e}"])

    save_snapshots_to_repo(snapshots)

if __name__ == "__main__":
    main()
