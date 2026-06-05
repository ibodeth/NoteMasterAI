# NoteMasterAI 🧠📄

NoteMaster is an exam grading and assessment tool designed to help evaluate written exams. It scans exam papers, detects question zones using a custom YOLOv8 model, and processes handwriting to score answers and provide feedback based on grading rubrics.

## How it Works
The project uses a Python-based server and PyQt GUI alongside a companion Flutter mobile client. The mobile app captures high-resolution images of exam papers and streams them to the server over Wi-Fi. The server processes the images using OpenCV, runs OCR on specific zones, and queries the Gemini Vision API to score answers and give detailed feedback.

## Tech Stack
- **Desktop App & Backend:** Python 3.10+, PyQt5
- **Mobile Client:** Flutter, Dart
- **Computer Vision & OCR:** OpenCV, YOLOv8, Google Cloud Vision API
- **AI Engine:** Google Gemini API
- **PDF Extraction:** Poppler

## Configuration & Setup

### Prerequisites
- Python 3.10+
- Flutter SDK (for building the mobile app)
- Google Cloud Platform account with Vision API enabled
- Gemini API Key

### Credentials
1. Place your Google Cloud Service Account credentials JSON as `service-account.json` in the root folder.
2. Add your Gemini API key in `secrets.json`:
   ```json
   {
     "gemini_api_key": "YOUR_GEMINI_API_KEY"
   }
   ```

## Installation & Running

### Desktop Server & GUI
```bash
cd NoteMasterAI
pip install -r requirements.txt
python main_qt.py
```

### Mobile Scanner Client
```bash
cd NoteMasterMobile
flutter pub get
flutter run
```

## License
MIT
