import io
import os
import requests
import zipfile
import pdfplumber
from pdf2image import convert_from_bytes, exceptions

# Constants
BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__))) # NoteMasterAI/
POPPLER_DIR = os.path.join(BASE_DIR, "poppler")
POPPLER_BIN_DIR = os.path.join(POPPLER_DIR, "Library", "bin")
POPPLER_API_URL = "https://api.github.com/repos/oschwartz10612/poppler-windows/releases/latest"
PDF_DPI = 300 

def check_poppler_bundled():
    """
    Check if 'poppler/Library/bin/pdftoppm.exe' file exists.
    """
    pdftoppm_path = os.path.join(POPPLER_BIN_DIR, "pdftoppm.exe")
    exists = os.path.exists(pdftoppm_path)
    return exists, POPPLER_BIN_DIR

def get_latest_poppler_url():
    """
    Connects to GitHub API and finds the download URL of the latest Poppler .zip release.
    """
    print("Searching for the latest Poppler version via GitHub API...")
    try:
        headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64)',
            'Accept': 'application/vnd.github.v3+json'
        }
        response = requests.get(POPPLER_API_URL, headers=headers)
        response.raise_for_status() 
        data = response.json()
        assets = data.get('assets', [])
        
        for asset in assets:
            asset_name = asset.get('name', '')
            if asset_name.endswith('.zip'):
                download_url = asset.get('browser_download_url')
                if download_url:
                    print(f"Latest version found: {asset_name}")
                    return download_url
        
        print("No .zip file found in the API response.")
        return None

    except requests.exceptions.RequestException as e:
        print(f"Error connecting to GitHub API: {e}")
        return None

def download_and_extract_poppler(download_url):
    """
    Downloads Poppler from the given URL and extracts it to the 'poppler' directory.
    """
    try:
        print(f"Downloading Poppler... {download_url}")
        headers = {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64)'}
        response = requests.get(download_url, stream=True, headers=headers)
        response.raise_for_status() 
        
        print("Download completed. Extracting ZIP file...")
        zip_data = io.BytesIO(response.content)
        
        with zipfile.ZipFile(zip_data, 'r') as zip_ref:
            file_list = zip_ref.namelist()
            if not file_list:
                print("ZIP file is empty.")
                return False
                
            zip_parent_folder = file_list[0].split('/')[0] + "/"
            
            os.makedirs(POPPLER_DIR, exist_ok=True)
            
            for member in zip_ref.infolist():
                filename = member.filename
                
                if filename.startswith(zip_parent_folder):
                    new_filename = filename.replace(zip_parent_folder, "", 1)
                    if new_filename:
                        target_path = os.path.join(POPPLER_DIR, new_filename)
                        if member.is_dir():
                            os.makedirs(target_path, exist_ok=True)
                        else:
                            os.makedirs(os.path.dirname(target_path), exist_ok=True)
                            with open(target_path, 'wb') as f:
                                f.write(zip_ref.read(member.filename))
                                
        print("Poppler successfully installed in 'poppler' folder!")
        return True
    except Exception as e:
        print(f"Unexpected error during installation: {e}")
        return False

def get_text_from_pdf(pdf_bytes):
    """
    Takes PDF bytes, reads with pdfplumber, and returns all text (natural text) inside.
    """
    all_text = ""
    if not pdf_bytes:
        return ""
    try:
        with io.BytesIO(pdf_bytes) as f:
            with pdfplumber.open(f) as pdf:
                for i, page in enumerate(pdf.pages):
                    page_text = page.extract_text()
                    if page_text:
                        all_text += f"--- PAGE {i+1} ---\n{page_text}\n\n"
        return all_text
    except Exception as e:
        print(f"Error extracting PDF text: {e}")
        return None

def pdf_to_images(pdf_bytes):
    """Wrapper around pdf2image to use common settings."""
    exists, bin_dir = check_poppler_bundled()
    if not exists:
         raise FileNotFoundError(f"Poppler not found: {bin_dir}")
         
    return convert_from_bytes(pdf_bytes, poppler_path=bin_dir, dpi=PDF_DPI)