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
from langchain_core.prompts import PromptTemplate

os.environ['GROQ_API_KEY']=os.getenv('GROQ_API_KEY')
os.environ['TAVILY_API_KEY']=os.getenv('TAVILY_API_KEY')
llm=ChatGroq(model='llama3-70b-8192')
tavily=TavilySearchResults()

class State(TypedDict):
    userQuery:str
    city:str
    temp:str
    preference:str
    context:list[dict]
    next_days:str
    units:str
    condition:str
    ambiguous:bool
    content:str



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
 

def get_clarrify(state:dict):
    return "validate_location" if state['ambiguous'] else "generate_response"




def get_current_weather(state:dict)->dict:
    """Get weather info"""
    response = requests.get(f"http://api.weatherapi.com/v1/current.json?key=078f770d78c1428c8a891304240302&q={state['city']}")
    data = response.json()
    if "error" in data:
        state["ambiguous"] = True
    else:
        state["ambiguous"] = False
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


def subsequent_weather(state:dict)->dict:
    """Get weather info for subsequent days"""
    response=requests.get(f"http://api.weatherapi.com/v1/forecast.json?key=078f770d78c1428c8a891304240302&q={state['city']}&days=5")
    data=response.json()
    forecast_days = data["forecast"]["forecastday"]
    result=f"The weather condition for next 3 days for {state['city']}:"
    for day in forecast_days:
        date = day["date"]
        condition = day["day"]["condition"]["text"]
        max_temp = day["day"]["maxtemp_c"]
        min_temp = day["day"]["mintemp_c"]

        result += f"\n📅 {date}: {condition}, 🌡️ {min_temp}°C - {max_temp}°C"

    state['next_days']=result
    return state


def remove_ambiguity(state:dict)->dict:
    # """Remove Ambiguity From Query"""
    template="""Extract city and units required if any from {location}.
    Also extract preferences from {location}.
    Return output as a Python dictionary with keys and values. No preamble, no explanation — only the dictionary.
    Example:
    location:whats the weather in newyork for golf in degree celsius
    preferences:golf
    city:newyork
    units:celsius
    Output: {{'preference': 'golf', 'city': 'newyork', 'units': 'celsius'}}
    Example:
    location:whats the weather in london for running
    preferences:running
    city:london
    units:celsius
    Output: {{'preference': 'running', 'city': 'london', 'units': 'celsius'}}
    Example:
    location:whats the weather in melbourne
    preferences:None
    city:melbourne
    units:celsius
    Output: {{'preference': None, 'city': 'melbourne', 'units': 'celsius'}}
    """
    prompt=PromptTemplate(template=template,input_variables=['location'])
    formatted_prompt = prompt.format(location=state['userQuery'])
    response=llm.invoke(formatted_prompt)
    content = response.content.strip()


    try:
        parsed = ast.literal_eval(content)
    except Exception as e:
        print("⚠️ Failed to parse response:", response.content)
        raise e
    state['preference']=parsed['preference']
    state['city']=parsed['city']
    state['units']=parsed['units']
    return state


    
# Node definition
def generate_response(state:dict)->str:
    template="""you are given
    user preference:{preference}
    current temperature:{temp},
    current condition:{condition}
    current weather events:{context},
    next three days predicted weather:{next_days} 
    Generate appropriate response in less than 50 words for {query} according to given information"""
    context = state['context']
    if "ConnectTimeout" in str(context):
        context = "No recent weather events available."

    prompt=PromptTemplate(template=template,input_variables=['preference','temp','condition','context','next_days','query'])
    formatted_prompt = prompt.format(preference=state['preference'],temp=state['temp'],condition=state['condition'],context=context,next_days=state['next_days'],query=state['userQuery'])
    response=llm.invoke(formatted_prompt)
    state["content"] = response.content.strip()
    return state



# Build Graph
builder=StateGraph(State)
builder.add_node("parse_query",remove_ambiguity)
builder.add_node("get_context",fetch_context)
builder.add_node("next_days",subsequent_weather)
builder.add_node("weather_update",get_current_weather)
builder.add_node("generate_response",generate_response)
builder.add_node("validate_location",validate_location)
# Edges
builder.add_edge(START,"parse_query")
builder.add_edge(
    "parse_query","get_context"
)
builder.add_edge("get_context","next_days")
builder.add_edge("next_days","weather_update")
builder.add_conditional_edges("weather_update", get_clarrify, {
    "validate_location": "validate_location",
    "generate_response": "generate_response"
})
builder.add_edge("validate_location","weather_update")
builder.add_edge("generate_response",END)
graph=builder.compile()


def main():
    st.header("Weather Agent")
    location=st.text_input("Enter Your Query")
    if st.button('Search'):
        with st.spinner("Processing"):
            message=graph.invoke({"userQuery":location})
            st.write(message.get('content'))


if __name__=="__main__":
    main()