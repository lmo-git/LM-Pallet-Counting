import streamlit as st
from PIL import Image
import pytesseract
import io
import datetime
import gspread
import requests
from google.oauth2.service_account import Credentials
from googleapiclient.discovery import build
from googleapiclient.http import MediaFileUpload

# Set the title of the application
st.title("📄 โปรแกรมการนับพาเลทด้วย AI")

# --- Step 1: Capture document photo ---
st.subheader("เลขที่เอกสารใบคุมพาเลท")
ocr_text = st.text_input("โปรดระบุเลขที่เอกสารโดยไม่ต้องระบุ PT เช่น 1234 เป็นต้น")

# --- Step 3: Capture pallet photo ---
st.subheader("Pallet Detection")
pallet_image_file = st.camera_input("Capture a pallet photo")
detected_count = 0  # Initialize detected count

if pallet_image_file:
    pallet_image = Image.open(pallet_image_file)

    # Save the image temporarily
    temp_image_path = "pallet_temp.jpg"
    pallet_image.save(temp_image_path)

    # --- Step 4: Pallet Detection using Roboflow API ---
    st.subheader("Pallet Detection Inference")
    try:
        with open(temp_image_path, "rb") as image_file:
            response = requests.post(
                "https://detect.roboflow.com/pallet-detection-measurement/1?api_key=WtsFf6wpMhlX16yRNb6e",
                files={"file": image_file}
            )

        result = response.json()
        predictions = result.get("predictions", [])
        detected_count = len(predictions)
        st.write(f"Detected Pallets: {detected_count}")

    except Exception as e:
        st.error(f"Error during inference: {e}")
        detected_count = 0  # Fallback if detection fails

# --- Step 5: User input for number of pallets ---
st.subheader("Confirm จำนวนพาเลท")
pallet_count_str = st.text_input("โปรดระบุจำนวนพาเลท", value=str(detected_count))
try:
    pallet_count = int(pallet_count_str)
except ValueError:
    pallet_count = 0
    st.warning("Pallet count was not a valid number. Defaulting to 0.")

# --- Step 6 & 7: Save to Google Drive & Google Sheets ---
if st.button("Confirm and Save Data"):
    try:
        scopes = [
            "https://www.googleapis.com/auth/spreadsheets",
            "https://www.googleapis.com/auth/drive"
        ]
        json_key = st.secrets["gcp"]
        creds = Credentials.from_service_account_info(json_key, scopes=scopes)

        gc = gspread.authorize(creds)
        sheet = gc.open_by_key("1ed2x0LCFSFhxewFRUZZiJO-h2tNnv11o8xbmrCazgMA").sheet1

        drive_service = build('drive', 'v3', credentials=creds)

        folder_name = "Pallet"
        query = f"mimeType='application/vnd.google-apps.folder' and name='{folder_name}' and trashed=false"
        results = drive_service.files().list(q=query, spaces='drive', fields='files(id, name)').execute()
        files = results.get('files', [])
        if files:
            folder_id = files[0]['id']
        else:
            file_metadata = {
                'name': folder_name,
                'mimeType': 'application/vnd.google-apps.folder'
            }
            folder = drive_service.files().create(body=file_metadata, fields='id').execute()
            folder_id = folder.get('id')

        file_name = ocr_text.strip().replace(" ", "_").replace("\n", "_") if ocr_text.strip() else "pallet_image"
        file_name += ".jpg"

        media = MediaFileUpload(temp_image_path, mimetype='image/jpeg')
        file_metadata = {
            'name': file_name,
            'parents': [folder_id]
        }
        uploaded_file = drive_service.files().create(body=file_metadata, media_body=media, fields='id').execute()
        uploaded_file_id = uploaded_file.get('id')
        file_link = f"https://drive.google.com/file/d/{uploaded_file_id}/view?usp=sharing"

        timestamp = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        row = [timestamp, ocr_text, pallet_count, file_link,detected_count]
        sheet.append_row(row)
        st.success("บันทึกข้อมูลสำเร็จ!")

    except Exception as e:
        st.error(f"Failed to save data: {e}")