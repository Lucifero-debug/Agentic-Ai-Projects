from google_auth_oauthlib.flow import InstalledAppFlow
from google.oauth2.credentials import Credentials
from googleapiclient.discovery import build
from langchain_core.prompts import PromptTemplate
from typing_extensions import TypedDict
from typing import Annotated,List,Any,Literal
from langgraph.graph import StateGraph,START,END
from datetime import datetime, timedelta
from bs4 import BeautifulSoup
import os
import streamlit as st
from langchain_groq import ChatGroq
from dotenv import load_dotenv
load_dotenv()
os.environ['GROQ_API_KEY']=os.getenv('GROQ_API_KEY')
llm=ChatGroq(model='llama3-70b-8192')