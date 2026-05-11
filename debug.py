import requests
import streamlit as st

st.title("🔍 Gemini Model Checker")

api_key = "AIzaSyAVuEMTWLXJCRld2E4lPYL7oy1wcLnX95Q"

url = f"https://generativelanguage.googleapis.com/v1/models?key={api_key}"

response = requests.get(url)

if response.status_code == 200:
    models = response.json()
    st.json(models)
else:
    st.error(f"Error: {response.status_code} - {response.text}")
