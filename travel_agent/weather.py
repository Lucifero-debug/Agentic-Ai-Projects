import ast
import re
from langchain_core.prompts import PromptTemplate
import streamlit as st
from dotenv import load_dotenv
load_dotenv()
import requests 
import os
from langchain_groq import ChatGroq
from typing_extensions import TypedDict
from langchain_core.messages import AnyMessage
from typing import Annotated
from langgraph.graph import StateGraph,START,END
from langgraph.prebuilt import ToolNode
from langgraph.graph.message import add_messages
from langgraph.prebuilt import tools_condition
from langchain_community.tools.tavily_search import TavilySearchResults
from datetime import date,timedelta

os.environ['GROQ_API_KEY']=os.getenv('GROQ_API_KEY')
os.environ['TAVILY_API_KEY']=os.getenv('TAVILY_API_KEY')
llm=ChatGroq(model='llama3-70b-8192')
tavily=TavilySearchResults()

class State(TypedDict):
    city:str
    temp:str
    start:date
    preference:list[str]
    context:list[dict]
    next_days:str
    condition:str
    content:str
    total_days:int



def validate_location(state: dict) -> dict:
    """
    Use Nominatim API to correct or validate a location.
    Returns a dictionary with city, state, and country.
    """
    url = "https://nominatim.openstreetmap.org/search"
    params = {
        'q': state['city'],
        'format': 'json',
        'addressdetails': 1,
        'limit': 1
    }

    response = requests.get(url, params=params, headers={'User-Agent': 'weather-app'})
    data = response.json()

    if not data:
        return {"error": f"Location '{state['location']}' not found"}

    address = data[0]["address"]
    city = address.get("city") or address.get("town") or address.get("village") or address.get("hamlet")
    states = address.get("state")
    country = address.get("country")
    state['city']=city
    return state
 


def get_current_weather(state:dict)->dict:
    """Get weather info"""
    response = requests.get(f"http://api.weatherapi.com/v1/current.json?key=078f770d78c1428c8a891304240302&q={state['city']}")
    data = response.json()
    if "error" in data:
        state["ambiguous"] = True
        print("Error fetching weather data")
    else:
        state["temp"] = data["current"]["temp_c"]
        state["condition"] = data["current"]["condition"]["text"]
    return state  # ✅ 

def fetch_context(state: dict) -> dict:
    """Get extra weather related Information"""
    try:
        response = tavily.invoke(f"recent weather events in {state['city']}")
        state['context'] = response
    except Exception as e:
        print("⚠️ Tavily context fetch failed:", e)
        state['context'] = "No recent weather news available."
    return state


def subsequent_weather(state:dict):
    key = os.getenv("WEATHER_API_KEY")
    result=f"The weather condition for next {state['total_days']} days for {state['city']}:"
    days=state['total_days']
    start_date=state['start']
    for i in range(days):
        date = (start_date + timedelta(days=i))
        date_str = date.strftime("%Y-%m-%d")
        url = f"http://api.weatherapi.com/v1/forecast.json"
        params = {
            "key": key,
            "q": state['city'],
            "dt": date_str
        }
        response = requests.get(url, params=params)
        data = response.json()
        if "error" in data:
            # ✅ Return the error message inside the state dict
            state["next_days"] = f"❌ Error: {data['error']['message']}"
            return state

        day = data["forecast"]["forecastday"][0]["day"]
        condition = day["condition"]["text"]
        max_temp = day["maxtemp_c"]
        min_temp = day["mintemp_c"]

        result+= f"📅 {date} (Past) - {condition}, 🌡️ {min_temp}°C to {max_temp}°C"
    state['next_days']=result
    return state



    
# Node definition
def generate_response(state:dict)->str:
    template = """You are given:
    - user preference: {preference}
    - current temperature: {temp}
    - current condition: {condition}
    - current weather events: {context}
    - next three days predicted weather: {next_days}
    Generate a short, helpful weather summary for a traveler who wants to do {preference}."""
    context = state['context']
    if "ConnectTimeout" in str(context):
        context = "No recent weather events available."

    prompt = PromptTemplate(
    template=template,
    input_variables=["preference", "temp", "condition", "context", "next_days"]
    )
    formatted_prompt = prompt.format(
        preference=state["preference"],
        temp=state["temp"],
        condition=state["condition"],
        context=context,
        next_days=state["next_days"]
    )
    response=llm.invoke(formatted_prompt)
    state["content"] = response.content.strip()
    print("content",state['content'])
    return state

# Build Graph
builder=StateGraph(State)
builder.add_node("get_context",fetch_context)
builder.add_node("next_days",subsequent_weather)
builder.add_node("weather_update",get_current_weather)
builder.add_node("generate_response",generate_response)
builder.add_node("validate_location",validate_location)
# Edges
builder.add_edge(START,"validate_location")
builder.add_edge(
    "validate_location","get_context"
)
builder.add_edge("get_context","next_days")
builder.add_edge("next_days","weather_update")
builder.add_edge("weather_update", "generate_response")
builder.add_edge("generate_response",END)
weather_agent=builder.compile()