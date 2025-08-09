from typing_extensions import TypedDict
from typing import Annotated,List,Any,Literal
from langgraph.graph import StateGraph,START,END
import json
import os
import tempfile
import streamlit as st
import re
from pydantic import BaseModel, Field
from langchain_groq import ChatGroq
from reportlab.platypus import SimpleDocTemplate, Paragraph
from reportlab.lib.styles import getSampleStyleSheet
from langchain.output_parsers import PydanticOutputParser
import asyncio
from dotenv import load_dotenv
from scrapper import fetch_internshala_jobs,apply_internshala_jobs,convert_cookies_to_storage_state
load_dotenv()
os.environ['GROQ_API_KEY']=os.getenv('GROQ_API_KEY')
llm=ChatGroq(model='llama3-70b-8192')

class JobState(TypedDict):
    profile:List[dict]
    jobs:List[dict]
    selected_jobs:List[dict]
    resume:List[dict]


profile = {
    "name": "Prashant Kumar",
    "education": "Btech 3rd year",
    "experience": "No Experience",
    "projects": [
        "Ecommerce",
        "Social Media",
        "Blog Generator",
        "Text Summarriser",
        "Image Classification"
    ],
    "skills": [
        "Python",
        "Javascript",
        "Next Js",
        "GeneratiVe Ai",
        "Machine Learning",
        "Full Stack Mern"
    ],
    "preferences": [
        "Internship",
        "Remote",
        "Paid",
        "Freelance"
    ]
}

def get_top_5_jobs(scored_jobs: list[dict], all_jobs: list[dict]) -> list[dict]:
    sorted_jobs = sorted(scored_jobs, key=lambda job: job["score"], reverse=True)
    top_jobs = []
    for job in sorted_jobs[:5]:
        full_job = next((j for j in all_jobs if j.get("Title") == job["title"]), {})
        job["full_job_info"] = full_job
        top_jobs.append(job)
    return top_jobs

def save_pdf(resume_text: str, file_path: str):

    doc = SimpleDocTemplate(file_path)
    styles = getSampleStyleSheet()
    story = [Paragraph(resume_text, styles["Normal"])]
    doc.build(story)


def search_jobs(state:JobState):
    jobs=asyncio.run(fetch_internshala_jobs(query=state['profile']['skills'][0]))
    return {'jobs':jobs}



class Resume(BaseModel):
    resume:str=Field(description='Tailored Resume according to the job description by llm')

parser1=PydanticOutputParser(pydantic_object=Resume)

def score_jobs(state: JobState):
    jobs = state['jobs']
    job_score = []
    
    for job in jobs:
        prompt = f"""Given the candidate profile 
Education: {state['profile']['education']} 
Experience: {state['profile']['experience']} 
Projects: {state['profile']['projects']} 
Skills: {state['profile']['skills']} 
Preferences: {state['profile']['preferences']} 

And the job description: {json.dumps(job, indent=2)}

Score the suitability of the candidate for this job on a scale of 0 to 10. 
Also give a short justification. 

Return ONLY valid JSON, no extra text. 
Example:
{{
  "title": "{job.get('Title', 'Unknown')}",
  "score": 0,
  "reason": "..."
}}
"""
        response = llm.invoke(prompt)
        raw_text = response.content.strip()
        
        match = re.search(r"\{.*\}", raw_text, re.DOTALL)
        if match:
            try:
                result = json.loads(match.group(0))
                job_score.append(result)
            except json.JSONDecodeError as e:
                print(f"❌ JSON decode error for job {job.get('Title')}: {e}")
                print("⚠️ Raw model output:", raw_text)
        else:
            print(f"⚠️ No JSON object found for job {job.get('Title')}")
            print("⚠️ Raw model output:", raw_text)

    selected_jobs = get_top_5_jobs(job_score, jobs)
    return {'selected_jobs': selected_jobs}

def make_resume(state:JobState):
    jobs=state['selected_jobs']
    job_cv=[]

    for job in jobs:
        prompt = f"""
        You are a professional resume writer. Your task is to create a **tailored resume** for the candidate based on their profile and the given job description, ensuring the resume highlights the candidate’s most relevant skills, projects, and experiences for this job.

        ### Candidate Profile:
        Name: {state['profile']['name']}
        Education: {state['profile']['education']}
        Experience: {state['profile']['experience']}
        Projects: {", ".join(state['profile']['projects'])}
        Skills: {", ".join(state['profile']['skills'])}
        Preferences: {", ".join(state['profile']['preferences'])}
        email:{state['profile']['email']}
        phone:{state['profile']['phone_no']}

        ### Job Description:
        Title: {job['full_job_info'].get('Title', '')}
        Company: {job['full_job_info'].get('company_name', '')}
        Description: {job['full_job_info'].get('description', '')}
        Skills Required: {", ".join(job['full_job_info'].get('skills_required', []))}
        Certifications: {", ".join(job['full_job_info'].get('certifications', []))}
        Who Can Apply: {", ".join(job['full_job_info'].get('who_can_apply', []))}
        Perks: {", ".join(job['full_job_info'].get('perks', []))}
        About Company: {job['full_job_info'].get('about_company', '')}

        ### Instructions:
        1. Write the resume in a **professional, ATS-friendly** format.
        2. Highlight skills and projects that are most relevant to the job.
        3. Where possible, rephrase the candidate’s skills and experiences to match the job requirements and keywords.
        4. Emphasize transferable skills even if the candidate has no direct experience in this field.
        5. Include a **Summary** section tailored to the job.
        6. Keep the tone confident, concise, and relevant.
        7. Please output the resume in plain text format ONLY. Do NOT use markdown or any symbols like ** or *. Use simple dashes (-) for bullet points, and proper line breaks.
        8. Output ONLY the final resume text. Do NOT include any introductions, explanations, or closing remarks.
        9. Do NOT include any of these phrases anywhere in your output: 
"Here is the tailored resume", "As requested", "Below is the resume", "Summary:", or any other introduction.
Output ONLY the resume content, starting immediately with the candidate's name.

        """
        response=llm.invoke(prompt)
        print(response.content)
        resume_data={
            "Title":job['full_job_info'].get('Title', ''),
            "Resume":response.content
        }
        job_cv.append(resume_data)
    
    return {'resume':job_cv}

def apply_job(state:JobState):
    jobs=state['selected_jobs']
    for job in jobs:
        link = job['full_job_info'].get('link')
        title = job['full_job_info'].get('Title')
        print(f"Applying to {title} at {link}")
        resume_entry = next(
            (r for r in state['resume'] if r['Title'] == title),
            None
        )
        if not resume_entry:
            print(f"No tailored resume found for {title}")
            continue

        resume_text = resume_entry['Resume']
        with tempfile.NamedTemporaryFile(delete=False, suffix=".pdf") as tmp_file:
            pdf_path = tmp_file.name
        save_pdf(resume_text, pdf_path)

        asyncio.run(apply_internshala_jobs(job_url=link,resume_path=pdf_path))
        os.remove(pdf_path)
        print("Successfully Applied")


def initialize_graph():
    graph=StateGraph(JobState)
    graph.add_node("search_jobs",search_jobs)
    graph.add_node("score_jobs",score_jobs)
    graph.add_node("make_resume",make_resume)
    graph.add_node("apply_job",apply_job)

    graph.add_edge(START,"search_jobs")
    graph.add_edge("search_jobs","score_jobs")
    graph.add_edge("score_jobs","make_resume")
    graph.add_edge("make_resume","apply_job")
    graph.add_edge("apply_job",END)

    return graph.compile()


def load_data():
    with open("profile.json",'r') as f:
        data=json.load(f)
        return data

def main():

    # with open ("profile.json",'w') as f:
    #     json.dump(profile,f,indent=4)
    data=load_data()
    input_file = "cookie.json"  
    output_file = "auth.json"     

    convert_cookies_to_storage_state(input_file, output_file)    
    # asyncio.run(login_internshala())
    workflow=initialize_graph()
    result=workflow.invoke({
        "profile":data,
        "jobs": []  
    })
    print(result['resume'])

if __name__=="__main__":
    main()
