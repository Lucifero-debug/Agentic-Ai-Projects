import streamlit as st
from weather import weather_agent
hotel_type=["Budget","Luxury","Home-Stays"]

def main():
    st.header("AI Travel Agent")
    col1, col2, col3 = st.columns(3)

    with col1:
        location = st.text_input("Enter Your Location")

    with col2:
        start_date = st.date_input("Please Select Start Date")

    with col3:
        no_of_days = st.number_input("Please Select No Of Days",step=1)

    col4, col5, col6 = st.columns(3)

    with col4:
        food_choice = st.selectbox("Food Options",["Veg","Non-Veg","Halal"])

    with col5:
        budget=st.number_input("Total Budget",step=1)

    with col6:
        hotel = st.selectbox("Preferred Stays",options=hotel_type)

    total_people=st.number_input("Total People",step=1)
    preferences=st.multiselect("Preferences For Tour", ["Food", "Adventure", "Shopping", "Religious"])
    travel_prefer=st.selectbox("Select Your Travel Preferences",["Fastest","Overnight","Scenic","cheapest"])
    if st.button('Generate'):
        weather_response=weather_agent.invoke({'city':location,'preference':preferences,'total_days':no_of_days,'start':start_date})
        print(weather_response)


if __name__=="__main__":
    main()