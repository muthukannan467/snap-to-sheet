import streamlit as st
import json
import gspread
from google import genai
from google.genai import types
from oauth2client.service_account import ServiceAccountCredentials

# --- UI CONFIG & CSS ---
st.set_page_config(page_title="Receipt OCR Scanner", page_icon="🧾")

# Custom CSS for the green scanning bar animation
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
def init_gemini():
    return genai.Client(api_key=st.secrets["GEMINI_API_KEY"])

def init_gspread():
    # Use oauth2client instead of google.oauth2.service_account
    scope = ["https://spreadsheets.google.com/feeds", "https://www.googleapis.com/auth/drive"]
    
    # Get the JSON from secrets and parse it
    gcp_json = st.secrets["gcp_service_account"]
    
    # If it's a string, parse it; if it's already a dict, use it directly
    if isinstance(gcp_json, str):
        creds_dict = json.loads(gcp_json)
    else:
        creds_dict = gcp_json
    
    # Create credentials using oauth2client
    creds = ServiceAccountCredentials.from_json_keyfile_dict(creds_dict, scope)
    return gspread.authorize(creds)

client = init_gemini()
gc = init_gspread()

# --- PROCESSING LOGIC ---
def process_receipt(image_bytes):
    prompt = """
    Extract the following information from this receipt in raw JSON format:
    - Merchant Name
    - Date
    - Total Amount (as a number)
    - Category (must be one of: Food, Transport, Supplies)
    
    Return ONLY the raw JSON object. No markdown formatting, no conversational text.
    Example: {"Merchant Name": "Starbucks", "Date": "2023-10-01", "Total Amount": 5.50, "Category": "Food"}
    """
    
    response = client.models.generate_content(
        model="models/gemini-1.5-flash",
        contents=[
            types.Part.from_bytes(data=image_bytes, mime_type="image/jpeg"),
            prompt
        ],
        config=types.GenerateContentConfig(
            response_mime_type="application/json"
        )
    )
    return json.loads(response.text)

def save_to_sheets(data):
    try:
        sh = gc.open('receipt_ocr')
        worksheet = sh.sheet1
        # Append row: Merchant Name, Date, Total Amount, Category
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

# --- APP UI ---
st.title("🧾 Receipt OCR Scanner")
st.write("Take a photo of your receipt to automatically log it.")

img_file = st.camera_input("Scan Receipt")

if img_file:
    # 1. Show Scanning Animation
    scan_placeholder = st.empty()
    scan_placeholder.markdown('<div class="scanner-container"><div class="scanning-bar"></div></div>', unsafe_allow_html=True)
    
    with st.spinner("Gemini is analyzing the receipt..."):
        try:
            # 2. Extract Data
            receipt_data = process_receipt(img_file.getvalue())
            
            # 3. Save to Google Sheets
            success = save_to_sheets(receipt_data)
            
            if success:
                # 4. Cleanup and Success
                scan_placeholder.empty()
                st.toast(f"Logged: {receipt_data.get('Merchant Name')} - ${receipt_data.get('Total Amount')}", icon='✅')
                
                # Show extracted data preview
                st.success("Data successfully saved to 'receipt_ocr'!")
                st.json(receipt_data)
                
        except Exception as e:
            scan_placeholder.empty()
            st.error(f"Processing failed: {str(e)}")
