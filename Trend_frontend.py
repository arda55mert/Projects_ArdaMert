from fasthtml.common import *
from fastapi import Request
import requests
import logging
import uvicorn

# initializing FastHTML instance
app, rt = fast_app()
logging.basicConfig(level=logging.INFO)

# global variables to store url and name after the first submission
submitted_url = None
submitted_name = None

@rt("/")
def get():
    frm = Form(
        Input(name='url', placeholder='URL', type='text'),
        Input(name='name', placeholder='Name', type='text'),
        Button('Get Keyword Suggestions'),
        method="post",
        action="/suggest_keywords"  # update action to suggest_keywords
    )
    return Titled("Keyword Analysis Tool", frm, Div(id='summary'))

# routing for handling keyword suggestion form submission and storing the url and name
@rt('/suggest_keywords', methods=["POST"])
async def suggest_keywords(request: Request):
    global submitted_url, submitted_name

    # Extract form data from the request
    form_data = await request.form()
    submitted_url = form_data['url']
    submitted_name = form_data['name']

    keyword_request = {
        "url": submitted_url,
        "name": submitted_name
    }

    logging.info(f"Sending request for keyword suggestions: {keyword_request}")
    response = requests.post('http://api:8000/suggest_keywords/', json=keyword_request)
    logging.info(f"Response status code: {response.status_code}")

    if response.status_code == 200:
        result = response.json()

        # rendering keyword suggestions with checkboxes and an additional input box
        if 'suggestions' in result:
            additional_keywords_input = Input(name='additional_keywords', placeholder='add more keywords separated by commas', type='text')

            checkboxes = [
                CheckboxX(name="keyword", value=keyword, label=keyword)
                for keyword in result['suggestions']
            ]
            select_all_button = Button("Select All", onclick="selectAll()")
            analyze_button = Button("Analyze Selected Keywords", type="submit")

            frm = Form(
                *checkboxes,
		additional_keywords_input,
                select_all_button,
                analyze_button,
                method="post",
                action="/analyze_keywords"  # updating the action to point to the analyze_keywords route
            )
            summary_content = Div(frm)
        else:
            summary_content = Div("No keyword suggestions found", id='summary')
    else:
        summary_content = Div("Error occurred while processing the request", id='summary')

    return Titled(f"Keyword Suggestions for {submitted_name}", summary_content)

# routing for handling keyword analysis and processing
@rt('/analyze_keywords', methods=["POST"])
async def analyze_keywords(request: Request):
    global submitted_url, submitted_name

    form_data = await request.form()
    selected_keywords = form_data.getlist('keyword')

    additional_keywords = form_data.get('additional_keywords', '').split(',')
    additional_keywords = [kw.strip() for kw in additional_keywords if kw.strip()]  

    # combine both selected and additional keywords
    all_keywords = selected_keywords + additional_keywords

    keyword_analysis_request = {
        "url": submitted_url,  
        "name": submitted_name,
        "keywords": all_keywords
    }

    logging.info(f"Sending request for keyword analysis: {keyword_analysis_request}")
    response = requests.post('http://api:8000/analyze_keywords/', json=keyword_analysis_request)
    logging.info(f"Response status code: {response.status_code}")

    if response.status_code == 200:
        result = response.json()

        if 'name' in result and 'summaries' in result:
            summaries_html = [
                Div(
                    H2(f"Summary for {result['name']} - {summary['keyword']}"),
                    P(summary['summary'])
                )
                for summary in result['summaries']
            ]
            summary_content = Div(*summaries_html, id='summary')
        else:
            summary_content = Div("No summaries found", id='summary')
    else:
        summary_content = Div("Error occurred while processing the request", id='summary')

    return Titled(f"Keyword Analysis of {submitted_name}", summary_content)

if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=8080)