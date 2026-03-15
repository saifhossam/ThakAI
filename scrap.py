import asyncio
from crawl4ai import AsyncWebCrawler
from bs4 import BeautifulSoup
import os

URLS = [
    "https://uaelegislation.gov.ae/ar/legislations/1542/",
    "https://uaelegislation.gov.ae/ar/legislations/1552/",
    "https://uaelegislation.gov.ae/ar/legislations/1553/"
]

folder = "Clean_Text"
os.makedirs(folder, exist_ok=True)

async def fetch_and_save(crawler, url, idx):
    result = await crawler.arun(url=url)
    soup = BeautifulSoup(result.html, "html.parser")

    law_content = soup.select_one(".law_main_content")
    if not law_content:
        print(f"No content found for {url}")
        return

    # decompose unwanted tags
    for tag in law_content.find_all(["img", "svg", "a", "button", "script", "style"]):
        tag.decompose()

    # convert <br> to newlines
    for br in law_content.find_all("br"):
        br.replace_with("\n")

    text = law_content.get_text("\n", strip=True)

    # save the cleaned text to a file
    file_name = os.path.join(folder, f"uae_law_{idx+1}_cleaned.txt")
    with open(file_name, "w", encoding="utf-8") as f:
        f.write(text)

    print(f"Saved {file_name}")

async def main():
    async with AsyncWebCrawler() as crawler:
        tasks = [fetch_and_save(crawler, url, idx) for idx, url in enumerate(URLS)]
        await asyncio.gather(*tasks)

asyncio.run(main())
