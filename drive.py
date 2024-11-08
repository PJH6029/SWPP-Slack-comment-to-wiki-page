import os, json, uuid
import requests
import mimetypes
from googleapiclient.discovery import build
from googleapiclient.http import MediaFileUpload
from google.oauth2 import service_account

from dotenv import load_dotenv
from utils import *

load_dotenv(override=True)
sprint_no = os.getenv("TEAM_SPRINT_NO")

SCOPES = [os.getenv("GOOGLE_DRIVE_SCOPE")]
SERVICE_ACCOUNT_FILE = os.getenv("GOOGLE_SERVICE_ACCOUNT_FILE")
GOOGLE_DRIVE_FOLDER_ID = os.getenv("GOOGLE_DRIVE_FOLDER_ID")

def build_drive_service():
    creds = None
    
    creds = service_account.Credentials.from_service_account_file(
        SERVICE_ACCOUNT_FILE, scopes=SCOPES
    )
    return build("drive", "v3", credentials=creds)

def get_or_create_subfolder(drive_service, parent_id, folder_name):
    # get or create the subfolder
    response = drive_service.files().list(
        q=f"name='{folder_name}' and trashed=false and '{parent_id}' in parents",
        fields="files(id, name)"
    ).execute()
    
    folder_id = None
    if not response["files"]:
        # create the folder
        file_metadata = {
            "name": folder_name,
            "mimeType": "application/vnd.google-apps.folder",
            "parents": [parent_id],
        }
        folder = drive_service.files().create(
            body=file_metadata,
            fields="id",
            supportsAllDrives=True
        ).execute()
        folder_id = folder.get("id")
    else:
        folder_id = response["files"][0].get("id")
    return folder_id

def get_nested_folder_id(drive_service, team_drive_id, folder_name):
    folder_names = str(folder_name).replace("\\" , "/").split("/")
    parent_id = team_drive_id
    for folder_name in folder_names:
        parent_id = get_or_create_subfolder(drive_service, parent_id, folder_name)
    return parent_id

def download_image(image_url):
    response = requests.get(
        image_url,
        headers={"Authorization": f"Bearer {os.getenv('SLACK_BOT_TOKEN')}"} # slack bot token
    )
    if response.status_code == 200:
        return response.content
    else:
        print(f"Failed to download image: {image_url}")
        return None

def donwload_image_to_local(image_url, image_path, tmp_dir="tmp"):
    response = requests.get(
        image_url,
        headers={"Authorization": f"Bearer {os.getenv('SLACK_BOT_TOKEN')}"} # slack bot token
    )
    if response.status_code == 200:
        if not os.path.exists(tmp_dir):
            os.makedirs(tmp_dir)
        
        with open(os.path.join(tmp_dir, image_path), "wb") as f:
            f.write(response.content)
        return os.path.join(tmp_dir, image_path)
    else:
        print(f"Failed to download image: {image_url}")
        return None

def upload_from_comment(comment, tmp_dir="tmp"):
    drive_service = build_drive_service()
    if not drive_service:
        print("Failed to build drive service")
        return
    tmp_files = []
    
    date_str = get_date_from_comment(comment)
    initials = get_team_initials(comment['user_id'])
    
    full_path = os.path.join(
        f"Sprint{sprint_no}", "DevLogs", f"{date_str}_{initials}"
    )
    
    folder_id = get_nested_folder_id(drive_service, GOOGLE_DRIVE_FOLDER_ID, str(full_path).replace("\\" , "/"))
    
    # upload json
    if json_data := comment.get("json_data"):
        json_file_name = f"{date_str}_{initials}_data.json"
        tmp_json_path = os.path.join(tmp_dir, json_file_name)
        tmp_files.append(tmp_json_path)
        
        # temporary save the json data
        with open(tmp_json_path, "w", encoding="utf-8") as f:
            json.dump(json_data, f, indent=4, ensure_ascii=False)
            
        # upload the json file
        file_metadata = {
            "name": json_file_name,
            "parents": [folder_id]
        }
        media = MediaFileUpload(tmp_json_path, resumable=True, mimetype="application/json")
        
        file = drive_service.files().create(
            body=file_metadata,
            media_body=media,
            fields="id",
            supportsAllDrives=True
        ).execute()
        
        print(f"Uploaded {json_file_name} to {full_path}. File ID: {file.get('id')}")
    
    
    # upload image
    image_urls = comment.get('image_urls', [])
    for image_url in image_urls:
        # download the image
        image_filename = os.path.basename(image_url)
        imag_filename_without_ext, ext = os.path.splitext(image_filename)
        image_filename = f"{imag_filename_without_ext}_{uuid.uuid4().hex[:6]}{ext}" # add random string to avoid duplication
        tmp_image_path = donwload_image_to_local(image_url, image_filename, tmp_dir)
        if not tmp_image_path:
            continue
        tmp_files.append(tmp_image_path)
        
        mime_type, _ = mimetypes.guess_type(tmp_image_path)
        if mime_type is None:
            print(f"Unsuppored file type: {tmp_image_path}")
            continue
        
        file_metadata = {
            "name": image_filename,
            "parents": [folder_id]
        }
        media = MediaFileUpload(str(tmp_image_path).replace("\\", "/"), resumable=True, mimetype=mime_type)

        file = drive_service.files().create(
            body=file_metadata,
            media_body=media,
            fields="id",
            supportsAllDrives=True
        ).execute()
        
        print(f"Uploaded {image_filename} to {full_path}. File ID: {file.get('id')}")
        
    # share the folder
    shareable_link = create_shareable_link(drive_service, folder_id)
    comment["share_link"] = shareable_link


def create_shareable_link(drive_service, file_id):
    drive_service.permissions().create(
        fileId=file_id,
        body={"role": "reader", "type": "anyone"},
        fields="id",
    ).execute()
    
    file = drive_service.files().get(
        fileId=file_id,
        fields="webViewLink"
    ).execute()
    return file.get("webViewLink")