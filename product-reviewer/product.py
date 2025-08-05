from langchain_community.tools.tavily_search import TavilySearchResults
from dotenv import load_dotenv
import streamlit as st
import os
import requests
from bs4 import BeautifulSoup
from langchain_groq import ChatGroq
from urllib.parse import urljoin
from typing_extensions import TypedDict
from langgraph.graph import StateGraph,START,END
from typing import Annotated,List,Any,Literal
from urllib.parse import urlparse
from pydantic import BaseModel, Field
from langchain.output_parsers import PydanticOutputParser
load_dotenv()


def get_site_name(url):
    domain = urlparse(url).netloc.lower()
    if "flipkart.com" in domain:
        return "Flipkart"
    elif "amazon." in domain:
        return "Amazon"
    else:
        return "Unknown"

os.environ['TAVILY_API_KEY']=os.getenv('TAVILY_API_KEY')
os.environ['GROQ_API_KEY']=os.getenv('GROQ_API_KEY')
llm=ChatGroq(model='llama3-70b-8192')
llm2=ChatGroq(model='qwen/qwen3-32b')

tavily=TavilySearchResults()



def get_flipkart_reviews(product_url: Annotated[str, "Flipkart product URL"]) -> list:
    """
    Scrape top reviews (title, body, rating) from a Flipkart product page.
    """
    headers = {"User-Agent": "Mozilla/5.0"}

    # Step 1: Get all reviews page URL
    response = requests.get(product_url, headers=headers)
    soup = BeautifulSoup(response.text, "html.parser")
    link_tag = soup.find("a", href=True, text=lambda t: t and "review" in t.lower())
    if not link_tag:
        return [{"error": "Could not find reviews link on the product page."}]
    all_reviews_url = urljoin(product_url, link_tag["href"])

    # Step 2: Scrape reviews
    response = requests.get(all_reviews_url, headers=headers)
    soup = BeautifulSoup(response.text, "html.parser")
    review_container = soup.find("div", class_=lambda x: x and "col-9-12" in x)
    if not review_container:
        return [{"error": "Review container not found."}]

    review_blocks = review_container.find_all("div", class_="cPHDOP col-12-12")
    all_reviews = []

    for block in review_blocks:
        title_tag = block.find("p", class_="z9E0IG")
        rating_tag = block.find("div", class_="XQDdHH")
        body_tag = block.find("div", class_="ZmyHeo")

        review = {
            "title": title_tag.get_text(strip=True) if title_tag else "No title",
            "rating": rating_tag.get_text(strip=True) if rating_tag else "No rating",
            "body": body_tag.get_text(strip=True) if body_tag else "No body"
        }
        all_reviews.append(review)

    return all_reviews

def fetch_amazon_reviews( product_url: Annotated[str, "Amazon product review page URL"],
    max_pages: Annotated[int, "Maximum number of pages to scrape"] = 1) -> list:
    """
    Scrape top reviews (title, body, rating) from a Amazon product page.
    """
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)",
        "Accept-Language": "en-US,en;q=0.9",
    }

    all_reviews = []

    for page in range(1, max_pages + 1):
        url = f"{product_url}?pageNumber={page}"
        res = requests.get(url, headers=headers)

        if res.status_code != 200:
            print(f"❌ Failed to fetch page {page}")
            break

        soup = BeautifulSoup(res.text, "html.parser")
        reviews = soup.select("li[data-hook='review']")

        if not reviews:
            print("⚠️ No reviews found.")
            break

        for review in reviews:
            title = review.select_one("a[data-hook='review-title']")
            body = review.select_one("span[data-hook='review-body']")
            rating = review.select_one("i[data-hook='review-star-rating']")

            all_reviews.append({
                "title": title.get_text(strip=True) if title else "",
                "body": body.get_text(strip=True) if body else "",
                "rating": rating.get_text(strip=True) if rating else "",
            })

    return all_reviews


class ProductState(TypedDict):
    reviews:List[dict]
    summary:str
    user_query:str
    review_url:str
    product_url:List[str]
    product_name:str
    final_reviews:str

class Product(BaseModel):
    product_name:str=Field(description='Name of the product given in the user query')

class Review(BaseModel):
    final_review:str=Field(description='Summary of all the product reviews given by llm')

parser1=PydanticOutputParser(pydantic_object=Product)
parser2=PydanticOutputParser(pydantic_object=Review)

def parse_query(state:ProductState):
    prompt=f"""
Get the Product Name From the Following user query
query:{state['user_query']}
{parser1.get_format_instructions()}
"""
    response=llm.invoke(prompt)
    product_name=parser1.parse(response.content)
    return {'product_name':product_name.product_name}

def get_product_link(state:ProductState):
    results=tavily.invoke(f"{state['product_name']} site:flipkart.com OR site:amazon.in")
    product_url=[]
    for result in results:
        product_url.append(result['url'])
    return {'product_url':product_url}


def fetch_reviews(state: ProductState):
    print("=== FETCH_REVIEWS DEBUG ===")
    print(f"Input state keys: {list(state.keys())}")
    print(f"Product URLs: {state.get('product_url', [])}")
    
    reviews = []
    for result in state['product_url']:
        site_name = get_site_name(result)
        if site_name == "Flipkart":
            reviews_array = get_flipkart_reviews(result)
            for review in reviews_array:
                if "error" not in review:  # Filter out errors
                    reviews.append(review)

        if site_name == "Amazon":
            amazon_reviews = fetch_amazon_reviews(result, max_pages=2)
            reviews.extend(amazon_reviews)

    return {'reviews': reviews}

def llm_summary(state:ProductState):
    if "reviews" not in state:
        print("[ERROR] 'reviews' key missing in state:", state.keys())
        return {"error": "Missing reviews"}
    prompt=f"""
You are a review summarization assistant.
Here is a list of individual user reviews for a product. Your task is to read all the reviews carefully and provide a **concise, balanced, and insightful summary**. Highlight the most common opinions, pros, cons, and the overall sentiment.
Reviews:
{state['reviews']}
Now give a final summarized review that:
- Reflects the majority opinion
- Mentions recurring praises or complaints
- Feels natural and human-written
- Does not repeat every point, but merges insights into a coherent paragraph
{parser2.get_format_instructions()}
"""
    response=llm.invoke(prompt)
    final_review=parser2.parse(response.content)
    return {'final_reviews':final_review.final_review}
    



def main():
    graph=StateGraph(ProductState)
    graph.add_node("parse_query",parse_query)
    graph.add_node("get_product_link",get_product_link)
    graph.add_node("fetch_reviews",fetch_reviews)
    graph.add_node("llm_summary",llm_summary)

    graph.add_edge(START,"parse_query")
    graph.add_edge("parse_query","get_product_link")
    graph.add_edge("get_product_link","fetch_reviews")
    graph.add_edge("fetch_reviews","llm_summary")
    graph.add_edge("llm_summary",END)

    product_agent=graph.compile()
    st.header("AI Product Reviewer")
    input=st.text_input("Enter Your Query")
    submit=st.button("Submit")

    if submit:
        initial_state = {
            'user_query': input,
            'product_name': '',
            'product_url': [],
            'reviews': [], 
            'summary': '',
            'review_url': '',
            'final_reviews': ''
        }

        print("=== STARTING GRAPH EXECUTION ===")
        try:
            response = product_agent.invoke(initial_state)
            print("=== FINAL RESPONSE ===")
            print(response)
            st.write(response['final_reviews'])
        except Exception as e:
            print(f"Graph execution error: {e}")

if __name__=="__main__":
    main()