"""
Court Case Search Application
- Search for cases using CourtListener's v4 API
- Return relevant top 20 results with Case Name, Court, Date, Citation, and URL

NOTE: Requires COURTLISTENER_API_TOKEN in environment or .streamlit/secrets.toml
In terminal: export COURTLISTENER_API_TOKEN="<PASTE_NEW_TOKEN_HERE>"
"""

#Import necessary libraries
import os
from datetime import datetime
import pandas as pd
import requests
import streamlit as st

#Setup streamlit page (required for all streamlit apps)
st.set_page_config(page_title="Court Case Search", page_icon="⚖️", layout="wide")


#***BACKEND LOGIC***
#- Helpers
#- API Call
#- Data Processing

#Create API url variable
API_BASE = "https://www.courtlistener.com/api/rest/v4"

# Return ISO formatted date or raw string
def iso_date_or_raw(s):
    if not s:
        return ""
    try:
        return datetime.fromisoformat(s.replace("Z", "")).date().isoformat()
    except Exception:
        return s
    
# Retrieve API token
def get_token():
    token = (os.getenv("COURTLISTENER_API_TOKEN", "") or st.secrets.get("COURTLISTENER_API_TOKEN", "")).strip()
    if not token:
        raise RuntimeError("Missing COURTLISTENER_API_TOKEN (env or .streamlit/secrets.toml).")
    return token

#Create and configure requests session
def make_session(): 
    s = requests.Session()
    s.headers.update({
        "Authorization": f"Token {get_token()}",
        "User-Agent": "CourtCaseSearchApp (victor.rosas.5000@gmail.com)",
        "Accept": "application/json",
    })
    return s

#Ensure application uses V4
def assert_v4_url(url: str):
    if "/api/rest/v4/" not in url:
        raise RuntimeError(f"Refusing to proceed: resolved URL is not v4.\nResolved URL: {url}")
    
#Universal string converter
def to_text(x):
    if x is None:
        return ""
    if isinstance(x, list):
        parts = []
        for e in x:
            if isinstance(e, dict):
                v = e.get("cite") or e.get("citation") or e.get("citation_string")
                if not v and {"volume", "reporter", "page"} <= set(e):
                    v = f'{e["volume"]} {e["reporter"]} {e["page"]}'
                parts.append(str(v) if v is not None else "")
            else:
                parts.append(str(e))
        return "; ".join(p for p in parts if p)
    if isinstance(x, dict):
        return x.get("cite") or x.get("citation") or x.get("citation_string") or str(x)
    return str(x)

#API call
def call_v4_search(keyword: str, page: int):
    #Setup API call
    sess = make_session() 
    url = f"{API_BASE}/search/" 
    params = {
        "q": keyword,
        "type": "o",
        "order_by": "score desc",
        "page": page,
        "page_size": 20,
        "stat_Published": "on",
    }
    
    #Conduct the API call
    r = sess.get(url, params=params, timeout=30, allow_redirects=False) 

    #Check for silent redirects
    if r.status_code in (301, 302, 303, 307, 308):
        loc = r.headers.get("Location", "")
        st.error(f"Server attempted to redirect ({r.status_code}) to: {loc}")
        assert_v4_url(loc)
        raise RuntimeError("Unexpected redirect.")

    #Catch-all for other errors
    if r.status_code != 200:
        body = (r.text or "")[:600]
        raise RuntimeError(f"HTTP {r.status_code}.\nBody (first 600 chars): {body}")

    #Confirm CourtListener v4 API
    assert_v4_url(r.request.url)

    #Parse results from call
    data = r.json()
    rows = []
    for item in data.get("results", []):
        case_name = to_text(
            item.get("caseName")
            or item.get("case_name")
            or item.get("caption")
            or item.get("caption_abbreviated")
        )
        court_slug = to_text(item.get("court"))
        raw_date = item.get("dateFiled") or item.get("date_filed") or item.get("date")
        citation_raw = item.get("citation") or item.get("citation_string") or item.get("citations")
        abs_url = item.get("absolute_url") or item.get("absoluteUrl")

        full_url = (
            f"https://www.courtlistener.com{abs_url}"
            if isinstance(abs_url, str) and isinstance(abs_url, str) and abs_url.startswith("/")
            else to_text(abs_url)
        )
        
        rows.append({
            "Case Name": case_name,
            "Court": court_slug,
            "Date": iso_date_or_raw(raw_date),
            "Citation": to_text(citation_raw),
            "URL": full_url,
        })

    return rows, r.request.url


#***FRONTEND LOGIC***
#- Title
#- Caption
#- Button and Input

#App title and caption
st.title("⚖️ Court Case Search — CourtListener ⚖️")
st.caption("Search by keyword, citation, or party name.")

#Create default search field text and page number
kw = st.text_input ('🔎 Search term', placeholder='e.g., "qualified immunity"')
page = st.number_input("Page", min_value=1, value=1, step=1)

#Create search button
if st.button("Search", type="primary"):
    q = kw.strip()
    if not q:
        st.warning("Please enter a search term.")
    else:
        with st.spinner("Searching v4..."):
            try:
                rows, final_url = call_v4_search(q, int(page))
                st.caption (f"Requested: {final_url}")
                df = pd.DataFrame(rows)
                if df.empty:
                    st.info("No results found.")
                else:
                    st.dataframe(df, use_container_width=True)
            except Exception as e:
                st.exception(e)    
