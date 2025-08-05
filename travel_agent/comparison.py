from langchain_groq import ChatGroq
from langchain_core.prompts import PromptTemplate
from scrapper import railyatri_scrape,redbus_scrape,fetch_flight_offers
import os
from dotenv import load_dotenv
load_dotenv()

os.environ['GROQ_API_KEY']=os.getenv('GROQ_API_KEY')
llm=ChatGroq(model='meta-llama/llama-4-scout-17b-16e-instruct')

def get_best_transport(source,dest,date,preferences,budget):
    flights=fetch_flight_offers(source,dest,date)
    bus=redbus_scrape(source,dest,date)
    trains=railyatri_scrape(source,dest,date)

    prompt=f"""
You are a expert travel assistant Given the user preferences and budget help him pick the best mode of transport by comapring different options of flight,train and bus that perfectly suits his needs
source:{source}
destination:{dest}
flights:{flights}
trains:{trains}
bus:{bus}
preference:{preferences}
budget:{budget}
Return:
1. Best option (mode, provider, price, duration, timing,departure_station,arrival_station)
2. Reason for choosing it
3. Alternatives if applicable
"""
    response=llm.invoke(prompt)
    return response


response=get_best_transport("delhi","mumbai","2025-07-29","scenic","600")
import re

final_output = response.content

cleaned_output = re.sub(r"<think>.*?</think>", "", final_output, flags=re.DOTALL).strip()

print(cleaned_output)
