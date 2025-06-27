from fastapi import FastAPI, Query, HTTPException
from fastapi.responses import JSONResponse
from googleapiclient.discovery import build
from googleapiclient.http import MediaIoBaseUpload
from google.oauth2 import service_account
import yt_dlp
import os
import json
import uuid
import base64
from io import BytesIO

app = FastAPI()

SCOPES = ['https://www.googleapis.com/auth/drive.file']
SHARED_FOLDER_ID = '15qjD_koVrx_aecL9feTOrXAB7GDyjp7H'  # Replace with your real Google Drive folder ID

# Load service account credentials from environment variable
def get_drive_service():
    encoded = os.getenv("GOOGLE_CREDENTIALS")
    if not encoded:
        raise Exception("Missing GOOGLE_CREDENTIALS environment variable.")

    decoded = base64.b64decode(encoded).decode("utf-8")
    service_account_info = json.loads(decoded)

    creds = service_account.Credentials.from_service_account_info(
        service_account_info, scopes=SCOPES
    )
    return build('drive', 'v3', credentials=creds)

# Download audio from YouTube to memory
def download_audio_to_memory(video_url: str) -> (BytesIO, str):
    buffer = BytesIO()
    temp_id = str(uuid.uuid4())
    filename = f"{temp_id}.webm"

    ydl_opts = {
        'format': 'bestaudio/best',
        'outtmpl': filename,
        'quiet': True,
        'no_warnings': True,
        'noplaylist': True,
    }

    with yt_dlp.YoutubeDL(ydl_opts) as ydl:
        info = ydl.extract_info(video_url, download=True)
        full_path = ydl.prepare_filename(info)

    with open(full_path, 'rb') as f:
        buffer.write(f.read())
        buffer.seek(0)

    os.remove(full_path)
    return buffer, filename

# Upload file to Google Drive
def upload_memory_to_drive(memory_file: BytesIO, filename: str) -> str:
    service = get_drive_service()

    media = MediaIoBaseUpload(memory_file, mimetype='audio/webm', resumable=True)
    file_metadata = {
        'name': filename,
        'parents': [SHARED_FOLDER_ID]
    }

    uploaded_file = service.files().create(
        body=file_metadata,
        media_body=media,
        fields='id'
    ).execute()

    file_id = uploaded_file['id']

    service.permissions().create(
        fileId=file_id,
        body={'type': 'anyone', 'role': 'reader'}
    ).execute()

    return f"https://drive.google.com/file/d/{file_id}/view"

# API Home
@app.get("/")
def home():
    return {"message": "YouTube Audio Upload API with Google Drive (Service Account)"}

# Upload Endpoint
@app.get("/upload")
def upload(link: str = Query(..., description="YouTube video link")):
    try:
        memory_file, filename = download_audio_to_memory(link)
        drive_url = upload_memory_to_drive(memory_file, filename)
        memory_file.close()
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

    return JSONResponse(content={"drive_link": drive_url})
