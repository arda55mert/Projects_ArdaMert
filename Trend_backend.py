import json
import time
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
from bs4 import BeautifulSoup
import pandas as pd
import cloudscraper
import requests
import logging

app = FastAPI()
logging.basicConfig(level=logging.INFO)

class KeywordRequest(BaseModel):
    url: str
    name: str
    keywords: list

class CompanyRequest(BaseModel):
    url: str
    name: str

def fetch_recent_entries_for_topic(url, pages=50):
    all_entries = []
    headers = {
        "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/126.0.0.0 Safari/537.36",
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8",
        "Accept-Encoding": "gzip, deflate",
        "Accept-Language": "en-US,en;q=0.9",
        "Connection": "keep-alive"
    }

    scraper = cloudscraper.create_scraper()

    for page in range(1, pages + 1):
        try:
            response = scraper.get(f"{url}?page={page}", headers=headers)

            if response.status_code != 200:
                continue

            soup = BeautifulSoup(response.text, 'html.parser')
            entry_elements = soup.find_all(class_='complaint-description')

            for entry_element in entry_elements:
                clean_text = entry_element.get_text(strip=True)
                all_entries.append(clean_text)

            time.sleep(1)  # Prevent being blocked by the server for too many requests in a short period

        except Exception:
            continue

    return all_entries

def analyze_keyword_themes(comments, name, keyword):
    if comments:
        themes_prompt = f"""
        Please review all comments that mention the keyword "{keyword}" and conduct a thorough analysis. Your goal is to highlight distinct and specific issues that customers have encountered with {name}'s performance related to this keyword. Focus on identifying unique points and avoid redundant observations.

	Important: Do not include generic issues such as "lack of transparency" or "poor customer service" in the summary. Instead, focus on detailed and concrete problems.

	Comments to Analyze:
	{' '.join(comments)}

	Your summary should include the following section, ensuring that each point is unique and insightful:

	Key Issues Identified:
	Highlight specific problems or challenges mentioned by customers.

	Please ensure that the analysis is concise, avoids repetition, and provides a clear overview of the most critical issues.
        """

        ollama_service_url = "http://ollama:11434/api/chat"
        headers = {'Content-Type': 'application/json'}
        themes_payload = json.dumps({
            "model": "llama3:8b",
            "messages": [{"role": "user", "content": themes_prompt}],
            "stream": False,
            "temperature": 0.3,
            "top_k": 50,
            "seed": 55
        })

        try:
            themes_response = requests.post(ollama_service_url, headers=headers, data=themes_payload)
            themes_response.raise_for_status()
            themes_content = themes_response.json()['message']['content'].strip()
            return themes_content
        except (requests.exceptions.RequestException, json.JSONDecodeError, KeyError) as e:
            logging.error(f"Error analyzing keyword themes: {e}")
            return "API call failed"
    else:
        return "No comments found."

def suggest_keywords_with_llama(name: str):
    llama_service_url = "http://ollama:11434/api/chat"
    prompt = f"""
    İnternette araştırarak '{name}' şirketi ne yapar? Bu bilgiye dayanarak, müşteri şikayetlerinde arayabileceğim bazı Türkçe anahtar tek (one-word) kelimeler önerir misiniz? Cevapta sadece numaralandırılmış anahtar kelimeleri görmek istiyorum, herhangi bir açıklama, cümle ya da yorum istemiyorum.
    """

    payload = {
        "model": "llama3:8b",
        "messages": [{"role": "user", "content": prompt}],
        "temperature": 0.3,
        "top_k": 50,
        "stream": False,
        "seed": 55
    }

    headers = {"Content-Type": "application/json"}

    try:
        response = requests.post(llama_service_url, json=payload, headers=headers)
        response.raise_for_status()
        result = response.json()
        keywords = result.get("message", {}).get("content", "").strip().split("\n")
        
        # Clean and format keywords
        keywords = [keyword.split(".", 1)[1].strip() for keyword in keywords if keyword]  # Remove double numbering and trim
    except (requests.exceptions.RequestException, json.JSONDecodeError, KeyError) as e:
        logging.error(f"Error generating keywords with LLaMA: {e}")
        keywords = []

    return keywords

@app.post("/suggest_keywords/")
async def suggest_keywords_endpoint(request: CompanyRequest):
    keywords = suggest_keywords_with_llama(request.name)

    if not keywords:
        raise HTTPException(status_code=404, detail="No keyword suggestions found.")

    return {"suggestions": keywords}

@app.post("/analyze_keywords/")
async def analyze_keywords(request: KeywordRequest):
    entries = fetch_recent_entries_for_topic(request.url, pages=50)
    
    if not entries:
        raise HTTPException(status_code=404, detail="No recent entries found.")

    summaries = []
    for keyword in request.keywords:
        keyword_comments = [comment for comment in entries if keyword.lower() in comment.lower()]
        
        if len(keyword_comments) >= 5:
            summary = analyze_keyword_themes(keyword_comments, request.name, keyword)
            summaries.append({"keyword": keyword, "summary": summary})
        else:
            logging.info(f"Keyword '{keyword}' was mentioned fewer than the required times: a summary will not be generated.")

    response = {"name": request.name, "summaries": summaries}
    logging.info(f"Response: {response}")
    return response

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)