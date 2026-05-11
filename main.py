import streamlit as st
import json
import gspread
import requests
import base64
from oauth2client.service_account import ServiceAccountCredentials

# --- PAGE CONFIG ---
st.set_page_config(page_title="Receipt OCR Scanner", page_icon="🧾")

# --- CUSTOM CSS FOR SCANNING ANIMATION ---
st.markdown("""
    <style>
    @keyframes scan {
        0% { top: 0%; }
        50% { top: 100%; }
        100% { top: 0%; }
    }
    .scanner-container {
        position: relative;
        width: 100%;
        height: 10px;
        overflow: visible;
    }
    .scanning-bar {
        position: absolute;
        width: 100%;
        height: 4px;
        background-color: #00ff00;
        box-shadow: 0 0 15px #00ff00;
        animation: scan 2s infinite linear;
        z-index: 10;
    }
    </style>
""", unsafe_allow_html=True)

# --- INITIALIZATION ---
def init_gspread():
    """Initialize Google Sheets with Service Account from secrets"""
    scope = ["https://spreadsheets.google.com/feeds", "https://www.googleapis.com/auth/drive"]
    
    gcp_json = st.secrets["gcp_service_account"]
    
    if isinstance(gcp_json, str):
        creds_dict = json.loads(gcp_json)
    else:
        creds_dict = gcp_json
    
    creds = ServiceAccountCredentials.from_json_keyfile_dict(creds_dict, scope)
    return gspread.authorize(creds)

def process_receipt(image_bytes):
    """Send image to Gemini API using available model"""
    
    api_key = st.secrets["GEMINI_API_KEY"]
    
    # Use one of the available models from your list
    # Options: "models/gemini-2.0-flash", "models/gemini-2.5-flash", "models/gemini-2.0-flash-lite"
    model_name = "models/gemini-2.5-flash"
    
    url = f"https://generativelanguage.googleapis.com/v1/{model_name}:generateContent?key={api_key}"
    
    # Encode image to base64
    image_base64 = base64.b64encode(image_bytes).decode('utf-8')
    
    prompt = """
    Extract the following information from this receipt image.
    Return ONLY valid JSON, no other text, no markdown formatting.
    
    JSON format:
    {
        "Merchant Name": "name of the merchant",
        "Date": "YYYY-MM-DD",
        "Total Amount": 0.00,
        "Category": "Food" or "Transport" or "Supplies"
    }
    """
    
    payload = {
        "contents": [{
            "parts": [
                {"text": prompt},
                {
                    "inline_data": {
                        "mime_type": "image/jpeg",
                        "data": image_base64
                    }
                }
            ]
        }]
    }
    
    headers = {"Content-Type": "application/json"}
    
    response = requests.post(url, headers=headers, json=payload)
    
    if response.status_code != 200:
        raise Exception(f"API Error: {response.status_code} - {response.text}")
    
    result = response.json()
    
    try:
        text_response = result["candidates"][0]["content"]["parts"][0]["text"]
    except (KeyError, IndexError):
        raise Exception(f"Unexpected API response: {result}")
    
    # Clean the response
    clean_json = text_response.strip()
    if clean_json.startswith("```json"):
        clean_json = clean_json[7:]
    if clean_json.startswith("```"):
        clean_json = clean_json[3:]
    if clean_json.endswith("```"):
        clean_json = clean_json[:-3]
    clean_json = clean_json.strip()
    
    return json.loads(clean_json)

def save_to_sheets(data):
    """Save extracted data to Google Sheet"""
    try:
        sh = gc.open('receipt_ocr')
        worksheet = sh.sheet1
        
        row = [
            data.get("Merchant Name", ""),
            data.get("Date", ""),
            data.get("Total Amount", 0),
            data.get("Category", "")
        ]
        worksheet.append_row(row)
        return True
    except Exception as e:
        st.error(f"Error saving to Google Sheets: {e}")
        return False

# Initialize
gc = init_gspread()

# --- APP UI ---
st.title("🧾 Receipt OCR Scanner")
st.write("Take a photo of your receipt to automatically log it to Google Sheets.")

img_file = st.camera_input("📸 Scan Receipt")

if img_file:
    # Show scanning animation
    scan_placeholder = st.empty()
    scan_placeholder.markdown('<div class="scanner-container"><div class="scanning-bar"></div></div>', unsafe_allow_html=True)
    
    with st.spinner("Gemini is analyzing the receipt..."):
        try:
            # Extract data from receipt
            receipt_data = process_receipt(img_file.getvalue())
            
            # Save to Google Sheets
            success = save_to_sheets(receipt_data)
            
            if success:
                # Remove animation
                scan_placeholder.empty()
                
                # Show success message
                st.toast(f"✅ Logged: {receipt_data.get('Merchant Name')} - ${receipt_data.get('Total Amount')}", icon='✅')
                st.success("Data successfully saved to 'receipt_ocr' Google Sheet!")
                
                # Show extracted data
                st.subheader("📊 Extracted Data:")
                st.json(receipt_data)
                
        except Exception as e:
            scan_placeholder.empty()
            st.error(f"Processing failed: {str(e)}")
