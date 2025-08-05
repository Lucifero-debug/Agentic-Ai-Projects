from urllib.parse import urlparse, parse_qs
from typing_extensions import TypedDict
from langgraph.graph import StateGraph,START,END
from youtube_transcript_api import YouTubeTranscriptApi
import os
import streamlit as st
from langchain_groq import ChatGroq
from dotenv import load_dotenv
from pydantic import BaseModel, Field
import streamlit as st
load_dotenv()
os.environ['GROQ_API_KEY']=os.getenv('GROQ_API_KEY')
llm=ChatGroq(model='llama3-70b-8192')

from langchain.output_parsers import PydanticOutputParser



class BlogState(TypedDict):
    transcript:str
    outline:str
    blog:str
    video_id:str
    language:str

from typing import Dict, List

class Section(BaseModel):
    title: str
    points: List[str]

class Outline(BaseModel):
    outline: Dict[str, Section]

parser = PydanticOutputParser(pydantic_object=Outline)

class Blog(BaseModel):
    blog:str=Field(description="Final Generated Blog")
parser2=PydanticOutputParser(pydantic_object=Blog)

language_mapping={
    "English":"en",
    "Hindi":"hi"
}

def fetch_transcript(state: BlogState):
    """Fetch transcript from YouTube video"""
    try:
        video_id = state['video_id']
        language = state['language']
        
        if not video_id:
            return {'transcript': 'Error: Invalid video ID'}
        
        api_fetcher=YouTubeTranscriptApi()
        transcript_list = api_fetcher.fetch(
            video_id, 
            languages=[language]
        )
        
        full_text = " ".join([item.text for item in transcript_list])
        
        return {'transcript': full_text}
    
    except Exception as e:
        return {'transcript': f'Error fetching transcript: {str(e)}'}

def generate_outline(state: BlogState):
    """Generate blog outline from transcript"""
    try:
        transcript = state['transcript']
        
        if transcript.startswith('Error'):
            return {'outline': 'Cannot generate outline due to transcript error'}
        
        prompt = f"""
        Create a detailed blog outline based on this YouTube video transcript.
        
        Transcript: {transcript[:3000]}...  
        
        Generate a clear, structured outline with main points and subpoints that would make for an engaging blog post.
        {parser.get_format_instructions()}
        """
        
        response = llm.invoke(prompt)
        structured = parser.parse(response.content)
        return {'outline': structured.outline}
    
    except Exception as e:
        return {'outline': f'Error generating outline: {str(e)}'}


def generate_blog(state:BlogState):
    """Generate final blog post"""
    try:
        
        outline_serialized =state['outline']
        transcript=state['transcript']

        prompt = f"""
        Write a comprehensive blog post based on the following:
        
        Video Transcript: {transcript[:2000]}...
        
        Blog Outline: {outline_serialized}
        
        Create an engaging, well-structured blog post that captures the key insights from the video.
        Include an introduction, main content sections based on the outline, and a conclusion.{parser2.get_format_instructions()}
        """
        
        response = llm.invoke(prompt)
        structured = parser2.parse(response.content)
        return {"blog":structured.blog}        
    except Exception as e:
        return {'blog': f'Error generating blog: {str(e)}'}

    

def main():
    graph=StateGraph(BlogState)

    graph.add_node("fetch_transcript",fetch_transcript)
    graph.add_node("generate_outline",generate_outline)
    graph.add_node("generate_blog",generate_blog)

    graph.add_edge(START,'fetch_transcript')
    graph.add_edge('fetch_transcript','generate_outline')
    graph.add_edge('generate_outline','generate_blog')
    graph.add_edge('generate_blog',END)

    workflow=graph.compile()
    st.header("Youtube Video to Blog Generator")
    
    video=st.text_input("Enter Video Id")
    select_language=st.selectbox("Select Language",options=["English","Hindi"])
    language = language_mapping[select_language]
    

    query = urlparse(video).query
    params = parse_qs(query)

    video_id = params.get("v", [None])[0]
    initial_state={'video_id':video_id,'language':language}
    submit=st.button("Submit")
    if submit:
        response=workflow.invoke(initial_state)
        blog_content=response['blog']
        st.markdown(blog_content, unsafe_allow_html=True)

if __name__=="__main__":
    main()