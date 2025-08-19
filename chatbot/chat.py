from typing_extensions import TypedDict
from typing import Annotated, List, Any, Literal
from langgraph.graph import StateGraph, START, END
from langchain_core.messages import BaseMessage, HumanMessage
from langgraph.checkpoint.sqlite import SqliteSaver,sqlite3
import os
from langchain_groq import ChatGroq
from dotenv import load_dotenv
from langgraph.graph.message import add_messages
import streamlit as st
import uuid

load_dotenv()
os.environ['GROQ_API_KEY'] = os.getenv('GROQ_API_KEY')
llm = ChatGroq(model='llama3-70b-8192')

conn=sqlite3.connect(database='chatbot.db',check_same_thread=False)

def retrieve_all_threads():
     all_threads=set()

     for checkpoint in checkpointer.list(None):
          all_threads.add(checkpoint.config['configurable']['thread_id'])

     return list(all_threads)

def generate_thread_id():
     thread_id=uuid.uuid4()
     return thread_id

def reset_chat():
     thread_id=generate_thread_id()
     st.session_state["thread_id"]=thread_id
     add_thread(st.session_state["thread_id"])
     st.session_state["message_history"] = []

def add_thread(thread_id):
     if thread_id not in st.session_state["chat_threads"]:
          st.session_state["chat_threads"].append(thread_id)

def load_convo(thread_id):
     return workflow.get_state(config={'configurable': {'thread_id': thread_id}}).values['message']


checkpointer = SqliteSaver(conn=conn)
@st.cache_resource
def create_workflow():
    
    class ChatState(TypedDict):
        message: Annotated[list[BaseMessage], add_messages]
    
    def chat_node(state: ChatState):
        message = state['message']
        response = llm.invoke(message)
        return {"message": [response]}  
    
    graph = StateGraph(ChatState)
    graph.add_node("chat_node", chat_node)
    graph.add_edge(START, "chat_node")
    graph.add_edge("chat_node", END)
    
    return graph.compile(checkpointer=checkpointer)


st.markdown("""
<style>
.chat-row {
    max-height: none !important;
    overflow: visible !important;
}

.chat-row div[data-testid="stText"] {
    white-space: pre-wrap !important;
    overflow-wrap: break-word !important;
}
</style>
""", unsafe_allow_html=True)


workflow = create_workflow()

st.header("ChatBot")


if "message_history" not in st.session_state:
    st.session_state["message_history"] = []

if "thread_id" not in st.session_state:
     st.session_state["thread_id"]=generate_thread_id()

if "chat_threads" not in st.session_state:
     st.session_state["chat_threads"]=retrieve_all_threads()

add_thread(st.session_state["thread_id"])

# SideBar UI
if st.sidebar.button('New Chat'):
     reset_chat()

st.sidebar.title("My COnversation")

for thread_id in st.session_state["chat_threads"][::-1]:
    if st.sidebar.button(str(thread_id)):
         st.session_state["thread_id"]=thread_id
         messages=load_convo(thread_id)

         temp_messages=[]

         for message in messages:
            if isinstance(message,HumanMessage):
                   role='user'
            else:
                   role='ai'
            temp_messages.append({'role':role,'content':message.content})
         st.session_state["message_history"]=temp_messages

CONFIG = {'configurable': {'thread_id': st.session_state["thread_id"]}}

for message in st.session_state["message_history"]:
    with st.chat_message(message['role']):
        st.text(message['content'])

user_input = st.chat_input("Type Here")

if user_input:
    with st.chat_message('user'):
        st.text(user_input)
    
    st.session_state["message_history"].append({'role': 'user', 'content': user_input})
    

            
    with st.chat_message('assistant'):
                ai_message=st.write_stream(
                    message_chunk.content for message_chunk,metadata in workflow.stream({"message": [HumanMessage(content=user_input)]}, config=CONFIG,stream_mode="messages")
                )
    st.session_state["message_history"].append({'role': 'assistant', 'content': ai_message})