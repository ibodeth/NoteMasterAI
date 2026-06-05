<p align="center">
  <img src="https://img.shields.io/badge/Flutter-02569B?style=for-the-badge&logo=flutter&logoColor=white"/>
  <img src="https://img.shields.io/badge/Dart-0175C2?style=for-the-badge&logo=dart&logoColor=white"/>
  <img src="https://img.shields.io/badge/Android-3DDC84?style=for-the-badge&logo=android&logoColor=white"/>
  <img src="https://img.shields.io/badge/Python-3776AB?style=for-the-badge&logo=python&logoColor=white"/>
  <img src="https://img.shields.io/badge/OpenCV-27338e?style=for-the-badge&logo=opencv&logoColor=white"/>
  <img src="https://img.shields.io/badge/Gemini%20AI-4285F4?style=for-the-badge&logo=google&logoColor=white"/>
  <img src="https://img.shields.io/badge/Poppler-PDF-444444?style=for-the-badge"/>
  <img src="https://img.shields.io/badge/License-MIT-97CA00?style=for-the-badge"/>
</p>

# NoteMaster 🧠📄

**NoteMaster** is an intelligent exam grading and assessment system designed to digitize and automate the exam evaluation workflow. By utilizing AI and computer vision, NoteMaster mimics teacher-like grading decisions, providing detailed justifications, partial grading, and context-aware assessments via a combined desktop and mobile ecosystem.

---

## 📸 Screenshots

<p align="center">
  <img src="assets/screenshots/1.png" width="30%" />
  <img src="assets/screenshots/2.png" width="30%" />
  <img src="assets/screenshots/3.png" width="30%" />
</p>

---

## ✨ Key Features

### 🧠 Teacher-Like AI Grading
* **Partial Credit Evaluation:** Rather than simple binary correct/incorrect grading, the system evaluates logical progress (e.g., awarding 0.25, 0.50, or 0.75 points based on intermediate steps).
* **Justified Feedback:** The AI provides explicit reasons for its grading decisions (e.g., "One calculation error detected in the final step, 75% score awarded").
* **Custom Teacher Guidelines:** Instruct the AI to ignore spelling errors, grade based only on final results, or focus on specific process steps.

### 🖼️ Context-Aware OCR & Visual Analysis
* Evaluates students' work based on surrounding charts, tables, and handwritten annotations.
* Built-in anti-hallucination guardrails to prevent AI from inventing information not present in the scanned paper.

### 📄 Layout Template System
* Define custom reusable layout templates from blank PDF exams.
* Configure per-question point distributions, bounding box coordinates, and specialized instructions.

### 📱 Wireless Mobile Scan Client
* Use the companion mobile application to take high-resolution captures of physical exams.
* Auto-transfer scans to the desktop grading server in real-time over the local network (Wi-Fi).

### 🧪 Bounding Box Auto-Detection (YOLO)
* Instantly detect question boundaries using a custom-trained YOLO model.
* Trained on a hand-labeled dataset of over 750 custom exam sheets.
* [Dataset and YOLO Model Registry](https://universe.roboflow.com/erbascan/)

### 📊 Reports & Exporting
* Full classroom performance dashboards.
* Clean PDF export support for class grading results.

---

## 🛠 Tech Stack

* **Core Backend & Desktop GUI:** Python 3.10+, PyQt5
* **Mobile Client:** Flutter / Dart
* **Artificial Intelligence:** Google Gemini API (Multimodal LLM)
* **Computer Vision & OCR:** Google Cloud Vision API, OpenCV, YOLO
* **PDF Utility:** Poppler

---

## ⚙️ Configuration & Setup

### Prerequisites

* Python 3.10+
* Flutter SDK (for mobile client build)
* Google Cloud Platform account with Vision API access enabled
* Gemini API Key

### Credentials Setup

1. Place your Google Cloud Service Account credentials JSON file as `service-account.json` in the root folder.
2. Provide your Gemini API key during the initial launch or save it manually inside `secrets.json`:

```json
{
  "gemini_api_key": "YOUR_GEMINI_API_KEY"
}
```

> 🔐 **Security Note:** Never commit `secrets.json` or `service-account.json` to public version control.

---

## 🚀 Running the Applications

### Desktop Application (Server & Grading Interface)

```bash
cd NoteMasterAI
pip install -r requirements.txt
python main_qt.py
```

### Mobile App (Scanner Client)

```bash
cd NoteMasterMobile
flutter pub get
flutter run
```

---

## 📄 License

This project is licensed under the **MIT License**.
