# NoteMasterAI

An exam grading and assessment utility that uses object detection and language models to evaluate handwritten student answers.

## How it Works
The application uses a Python-based server and PyQt GUI alongside a companion Flutter mobile client. The mobile app captures high-resolution images of exam papers and streams them to the server over Wi-Fi. The server processes the images using OpenCV, runs OCR on specific zones detected by a custom YOLOv8 model, and queries the Google Gemini Vision API to score answers and generate feedback.

## Tech Stack
- **Languages/Frameworks:** Python, PyQt5, Flutter, Dart
- **Services/Libraries:** OpenCV, YOLOv8, Google Cloud Vision API, Google Gemini API, Poppler
- **Infrastructure:** Windows, Linux, Android, iOS

## Local Setup
1. Clone the repository:
   ```bash
   git clone https://github.com/ibodeth/NoteMasterAI.git
   cd NoteMasterAI
   ```
2. Place your Google Cloud Service Account credentials JSON as `service-account.json` in the root folder, and add your Gemini API key in `secrets.json`:
   ```json
   {
     "gemini_api_key": "YOUR_GEMINI_API_KEY"
   }
   ```
3. Run the desktop server:
   ```bash
   cd NoteMasterAI
   pip install -r requirements.txt
   python main_qt.py
   ```
4. Run the mobile scanner client:
   ```bash
   cd NoteMasterMobile
   flutter pub get
   flutter run
   ```

## License
MIT
