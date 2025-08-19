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

SCOPES = ['https://www.googleapis.com/auth/gmail.readonly']

class EmailState(TypedDict):
    emails:list[dict]
    current_chunk:List[dict]
    current_idx:int
    summaries:str
    service:Any
    final_summary:str

def get_service(state:EmailState)->EmailState:
    if 'service' not in st.session_state:
        flow = InstalledAppFlow.from_client_secrets_file("credentials.json", SCOPES)
        creds = flow.run_local_server(port=0)
        service = build('gmail', 'v1', credentials=creds)
        st.session_state['service'] = service
        state['service']=service
        return state

def fetch_emails(state:EmailState)->EmailState:
    yesterday = (datetime.utcnow() - timedelta(days=1)).strftime("%Y/%m/%d")
    query = f"after:{yesterday}"
    results = state['service'].users().messages().list(userId='me', q=query).execute()
    messages = results.get('messages', [])
    all_emails=[]

    for msg in messages:
        msg_data = state['service'].users().messages().get(userId='me', id=msg['id'],format='full').execute()
        payload=msg_data['payload']
        headers=payload.get('headers')
        subject = next((h['value'] for h in headers if h['name'] == 'Subject'), None)
        sender = next((h['value'] for h in headers if h['name'] == 'From'), '(Unknown Sender)')

        parts=payload.get('parts')
        if parts:
            for part in parts:
                mime_type = part.get('mimeType')
                body_data = part.get('body', {}).get('data')
                
                if mime_type == 'text/plain' and body_data:
                    import base64
                    email_body = base64.urlsafe_b64decode(body_data).decode('utf-8')
                    email_data={
                        'Subject':subject,
                        'Body':email_body,
                        'Sender':sender
                    }
                    all_emails.append(email_data)
                    break
        else:
            body_data = payload.get('body', {}).get('data')
            if body_data:
                import base64
                decoded_body = base64.urlsafe_b64decode(body_data).decode('utf-8')
                soup = BeautifulSoup(decoded_body, 'html.parser')
                email_body = soup.get_text() 
                email_data={
                        'Subject':subject,
                        'Body':email_body,
                        'Sender':sender
                    }
                all_emails.append(email_data)
                
    state['emails']=all_emails
    return state

def split_chunks(state:EmailState)->EmailState:
    chunk_size=2
    emails=state['emails']
    idx=state['current_idx']
    state['current_chunk']=emails[idx:idx+chunk_size]
    return state

def summarize_email(state:EmailState)->EmailState:
    template = """
You are a helpful AI assistant. Summarize all the emails according to their subject, body, and sender
emails:

{all_emails}
"""

    prompt=PromptTemplate(
        template=template,
        input_variables=["all_emails"]
    )
    formatted_prompt=prompt.format(
        all_emails=state['current_chunk']
    )
    response=llm.invoke(formatted_prompt)
    state['summaries']=state['summaries']+response.content
    return state

def should_continue(state: EmailState) -> Literal["increament","final_summary"]:
    if state['current_idx'] < len(state['emails']):
        return "increament"
    else:
        return "final_summary"

    

def increament(state:EmailState)->EmailState:
    state['current_idx']=state['current_idx']+10
    return state

def final_summary(state:EmailState)->EmailState:
    template = """
You are a helpful AI assistant. Summarize all the emails and list down all the important information if any on the basis of given 
summary:
{summary}
"""
    prompt=PromptTemplate(
        template=template,
        input_variables=["summary"]
    )
    formatted_prompt=prompt.format(
        summary=state['summaries']
    )
    response=llm.invoke(formatted_prompt)
    state['final_summary']=response.content
    return state

st.title("📨 Email Summary Agent")

if st.button("Connect to Gmail"):


    workflow=StateGraph(EmailState)
    workflow.add_node("get_service",get_service)
    workflow.add_node("fetch_emails",fetch_emails)
    workflow.add_node("split_chunks",split_chunks)
    workflow.add_node("summarize_email",summarize_email)
    workflow.add_node("should_continue",should_continue)
    workflow.add_node("increament",increament)
    workflow.add_node("final_summary",final_summary)

    workflow.add_edge(START,"get_service")
    workflow.add_edge("get_service","fetch_emails")
    workflow.add_edge("fetch_emails","split_chunks")
    workflow.add_edge("split_chunks","summarize_email")
    workflow.add_edge("summarize_email","increament")
    workflow.add_conditional_edges("increament", should_continue, {
        "increament": "split_chunks",
        "final_summary": "final_summary"
    })

    graph=workflow.compile()

    initial_state: EmailState = {
        "emails": [],
        "current_chunk": [],
        "current_idx": 0,
        "summaries": "",
        "service": None,
        "final_summary": ""
    }

    result=graph.invoke(initial_state)
    st.write(result['final_summary'])
