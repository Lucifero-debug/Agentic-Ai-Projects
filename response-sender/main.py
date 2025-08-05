from typing_extensions import TypedDict
from typing import Annotated,List,Any,Literal
from langgraph.graph import StateGraph,START,END
import os
from langchain_groq import ChatGroq
from dotenv import load_dotenv
load_dotenv()
os.environ['GROQ_API_KEY']=os.getenv('GROQ_API_KEY')
llm=ChatGroq(model='llama3-70b-8192')
from pydantic import BaseModel, Field
from typing import Literal


class Sentiment(BaseModel):
    Sentiment:Literal["Positive","Negative"]=Field(description="Sentiment Of The Review")

class ReviewState(TypedDict):
    review:str
    sentiment:Literal["Postive","Negative"]
    issue:dict
    response:str

class Issue(BaseModel):
    issue_type:Literal["UX","Performance","Bug","Support","Other"]=Field(description="The category Of The Issue Mentioned In the Review")
    issue_tone:Literal["Angry","Frustrated","Dissapointed","Calm"]=Field(description="Emotional tone Expressed by the user")
    urgency:Literal["low","medium","high"]=Field(description="The urgency or how critical the issue appears to be")

llm_withstructured=llm.with_structured_output(Sentiment)
llm_withstructured2=llm.with_structured_output(Issue)

def find_sentiment(state:ReviewState):
    prompt=f'Analyse The Sentiment Of the following Review\n{state['review']}'
    response=llm_withstructured.invoke(prompt).Sentiment
    return {'sentiment':response}

def run_diagnosis(state:ReviewState):
    prompt=f'Analyse The Feedback Of The User and return issue_type,issue_tone and urgency\n{state['review']}'
    response=llm_withstructured2.invoke(prompt)
    return {'issue':response.model_dump()}

def positive_response(state:ReviewState):
    prompt=f'Write a warm thankyou message in response to the review\n{state['review']}\n also kindly ask the user to leave feedback'
    response=llm.invoke(prompt)
    return {'response':response.content}

def negative_response(state:ReviewState):
    diagnosis=state['issue']
    prompt=f'You are a Support assistant the user had a {diagnosis['issue_type']},sounded{diagnosis['issue_tone']} and marked urgency as {diagnosis['urgency']} write an empathic resolution message'
    response=llm.invoke(prompt)
    return {'response':response.content}

def check_condition(state:ReviewState)->Literal["positive_response","run_diagnosis"]:
    if state["sentiment"]=="Postive":
        return "positive_response"
    else:
        return "run_diagnosis"

graph=StateGraph(ReviewState)
graph.add_node("find_sentiment",find_sentiment)
graph.add_node("run_diagnosis",run_diagnosis)
graph.add_node("positive_response",positive_response)
graph.add_node("negative_response",negative_response)

graph.add_edge(START,"find_sentiment")
graph.add_conditional_edges("find_sentiment",check_condition)
graph.add_edge("positive_response",END)
graph.add_edge("run_diagnosis","negative_response")
graph.add_edge("negative_response",END)

workflow=graph.compile()

review="""I’ve never been this frustrated using a smartphone in 2025. Everything from the gesture navigation to simple settings is completely broken. Apps stutter, random touch inputs get ignored, and basic tasks take twice as long because of the clunky UI.

The worst part? I’ve had to restart the phone multiple times daily just to get the keyboard or camera working. Menus are buried under unnecessary layers, auto-brightness behaves erratically, and don’t get me started on the haptic feedback—it’s either too much or nothing at all.

This is not a learning curve — it’s a design failure.
For a device in this price range, this level of friction is unacceptable. I’m losing productivity, patience, and trust in this brand.

Please prioritize a major UX overhaul ASAP—this isn’t just annoying anymore, it’s disruptive."""
initial_state={
    'review':review
}
final_state=workflow.invoke(initial_state)
print(final_state)

