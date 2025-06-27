from fastapi import FastAPI, Query, HTTPException
from fastapi.responses import JSONResponse
from google.oauth2 import service_account
from googleapiclient.discovery import build
from googleapiclient.http import MediaIoBaseUpload
import yt_dlp
import os
import uuid
from io import BytesIO

app = FastAPI()

# Service account setup
SERVICE_ACCOUNT_FILE = 'service_account.json'
SCOPES = ['https://www.googleapis.com/auth/drive.file']

# 👉 Replace this with your shared folder ID
SHARED_FOLDER_ID = '15qjD_koVrx_aecL9feTOrXAB7GDyjp7H'


def get_drive_service():
    creds = service_account.Credentials.from_service_account_file(
        SERVICE_ACCOUNT_FILE, scopes=SCOPES
    )
    return build('drive', 'v3', credentials=creds)


def download_audio_to_memory(video_url: str) -> (BytesIO, str):
    """Download YouTube audio to memory as BytesIO."""
    buffer = BytesIO()
    temp_id = str(uuid.uuid4())
    filename = f"{temp_id}.webm"

    ydl_opts = {
        'format': 'bestaudio/best',
        'outtmpl': filename,
        'quiet': True,
        'no_warnings': True,
        'noplaylist': True,
        'postprocessors': [],
        'logger': None,
    }

    class MyLogger:
        def debug(self, msg): pass
        def warning(self, msg): pass
        def error(self, msg): print("YTDLP ERROR:", msg)

    ydl_opts['logger'] = MyLogger()

    with yt_dlp.YoutubeDL(ydl_opts) as ydl:
        info = ydl.extract_info(video_url, download=True)
        full_path = ydl.prepare_filename(info)

    # Read into memory
    with open(full_path, 'rb') as f:
        buffer.write(f.read())
        buffer.seek(0)

    os.remove(full_path)  # Remove temp file
    return buffer, filename


def upload_memory_to_drive(memory_file: BytesIO, filename: str) -> str:
    """Upload memory file to Google Drive shared folder."""
    service = get_drive_service()

    file_metadata = {
        'name': filename,
        'parents': [SHARED_FOLDER_ID],  # Upload to the shared folder
    }

    media = MediaIoBaseUpload(memory_file, mimetype='audio/webm', resumable=True)

    uploaded_file = service.files().create(
        body=file_metadata,
        media_body=media,
        fields='id'
    ).execute()

    file_id = uploaded_file['id']

    # Make it public
    service.permissions().create(
        fileId=file_id,
        body={'type': 'anyone', 'role': 'reader'}
    ).execute()

    return f"https://drive.google.com/file/d/{file_id}/view"


@app.get("/")
def home():
    return {"message": "YouTube Audio Upload API with Google Drive (Service Account)"}


@app.get("/upload")
def upload(link: str = Query(..., description="YouTube video link")):
    try:
        memory_file, filename = download_audio_to_memory(link)
        drive_url = upload_memory_to_drive(memory_file, filename)
        memory_file.close()
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
    return JSONResponse(content={"drive_link": drive_url})
