"""Run the AXON market scanner interactively from Python IDLE or a terminal."""

from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parent / "src"))

from axon.market_scanner import MarketDataError, RemotiveScanner


def main() -> None:
    keyword = input("Enter a job keyword (for example, Python): ").strip()
    if not keyword:
        print("Please enter a keyword and run the script again.")
        return

    try:
        jobs = RemotiveScanner().search(keyword, limit=5)
    except MarketDataError as exc:
        print(f"Could not retrieve Remotive listings: {exc}")
        return

    print(f"\n{len(jobs)} matching result(s) from Remotive for {keyword!r}\n")
    if not jobs:
        print("No matching listings were found in the current feed.")
        return

    for number, job in enumerate(jobs, start=1):
        print(f"{number}. {job.title}")
        print(f"   Company: {job.company}")
        print(f"   Location: {job.eligible_location or 'Not provided'}")
        print(f"   Category: {job.category or 'Not provided'}")
        print(f"   Salary: {job.salary or 'Not provided'}")
        print(f"   Published: {job.publication_date or 'Not provided'}")
        print(f"   Source: {job.source}")
        print(f"   Job link: {job.url}\n")


if __name__ == "__main__":
    main()
