from typing_extensions import TypedDict
from typing import Annotated, List, Any, Literal
from langgraph.graph import StateGraph, START, END
from langchain_core.messages import BaseMessage, HumanMessage
from langgraph.checkpoint.memory import InMemorySaver
import os
from langchain_groq import ChatGroq
from dotenv import load_dotenv
from langgraph.graph.message import add_messages
import streamlit as st

load_dotenv()
os.environ['GROQ_API_KEY'] = os.getenv('GROQ_API_KEY')
llm = ChatGroq(model='llama3-70b-8192')

@st.cache_resource
def create_workflow():
    checkpointer = InMemorySaver()
    
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
/* Remove scroll inside chat_message containers */
.chat-row {
    max-height: none !important;
    overflow: visible !important;
}

/* Optional: also make content wrap properly */
.chat-row div[data-testid="stText"] {
    white-space: pre-wrap !important;
    overflow-wrap: break-word !important;
}
</style>
""", unsafe_allow_html=True)


# Get persistent workflow
workflow = create_workflow()
CONFIG = {'configurable': {'thread_id': 'thread1'}}

st.header("ChatBot")

if "message_history" not in st.session_state:
    st.session_state["message_history"] = []

# Display existing message history
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