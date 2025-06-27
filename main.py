from fastapi import FastAPI, Query, HTTPException
from fastapi.responses import JSONResponse
from google.oauth2 import service_account
from googleapiclient.discovery import build
from googleapiclient.http import MediaIoBaseUpload
import yt_dlp
import os
import uuid
from io import BytesIO
import json
import base64
import tempfile

app = FastAPI()

SCOPES = ['https://www.googleapis.com/auth/drive.file']

# 🔐 Your Google Drive folder ID (keep hardcoded)
SHARED_FOLDER_ID = 'YOUR_SHARED_FOLDER_ID'  # 🔁 Replace with your folder ID


# 🔑 Load service account from env var
def get_drive_service():
    encoded_creds = os.getenv("GOOGLE_CREDENTIALS")
    if not encoded_creds:
        raise Exception("Missing GOOGLE_CREDENTIALS environment variable")
    
    creds_json = base64.b64decode(encoded_creds).decode('utf-8')
    creds_dict = json.loads(creds_json)
    creds = service_account.Credentials.from_service_account_info(
        creds_dict, scopes=SCOPES
    )
    return build('drive', 'v3', credentials=creds)


# 🎧 Download audio using cookies from env var
def download_audio_to_memory(video_url: str) -> (BytesIO, str):
    buffer = BytesIO()
    temp_id = str(uuid.uuid4())
    filename = f"{temp_id}.webm"

    # 🔓 Decode YouTube cookies
    encoded_cookies = os.getenv("YOUTUBE_COOKIES")
    if not encoded_cookies:
        raise Exception("Missing YOUTUBE_COOKIES environment variable")
    
    cookies_text = base64.b64decode(encoded_cookies).decode("utf-8")
    with tempfile.NamedTemporaryFile(delete=False, mode='w+', suffix=".txt") as cookie_file:
        cookie_file.write(cookies_text)
        cookie_file_path = cookie_file.name

    ydl_opts = {
        'format': 'bestaudio/best',
        'outtmpl': filename,
        'quiet': True,
        'no_warnings': True,
        'noplaylist': True,
        'cookiefile': cookie_file_path,
    }

    with yt_dlp.YoutubeDL(ydl_opts) as ydl:
        info = ydl.extract_info(video_url, download=True)
        full_path = ydl.prepare_filename(info)

    with open(full_path, 'rb') as f:
        buffer.write(f.read())
        buffer.seek(0)

    os.remove(full_path)
    os.remove(cookie_file_path)
    return buffer, filename


# ☁️ Upload to Google Drive
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


@app.get("/")
def home():
    return {"message": "YouTube Audio Upload API with Google Drive (ENV Mode)"}


@app.get("/upload")
def upload(link: str = Query(..., description="YouTube video link")):
    try:
        memory_file, filename = download_audio_to_memory(link)
        drive_url = upload_memory_to_drive(memory_file, filename)
        memory_file.close()
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

    return JSONResponse(content={"drive_link": drive_url})
