

Of course! Here is a comprehensive `README.md` file for your GitHub repository. It includes all the necessary information for someone to understand, set up, and use your project.

---

# Raspberry Pi Exam Monitoring System

An AI-powered system for automated exam proctoring using a Raspberry Pi. It detects suspicious activities like unauthorized device usage and significant movements, identifies students by face or seat number, and sends real-time alerts to a Firebase database.

![Python Version](https://img.shields.io/badge/python-3.7%2B-blue)
![License](https://img.shields.io/badge/license-MIT-green)
![Platform](https://img.shields.io/badge/platform-Raspberry%20Pi-lightgrey)

## Features

- **Real-time Object Detection**: Detects persons, cell phones, books, and laptops using a pre-trained COCO model.
- **Face Recognition**: Identifies registered students by name.
- **Seat-Based Identification**: Assigns seat numbers (e.g., A1, B3) to unknown faces based on their position in a 4x5 grid.
- **Focused Motion Detection**: Analyzes significant movements specifically in face and hand regions to reduce false alarms.
- **Alert Imaging**: Automatically captures and uploads an image to ImgBB when an alert is triggered.
- **Real-time Database**: Logs all alerts with details (student name, seat, event type, image URL) to a Firestore (Firebase) database.
- **Visual Feedback**: Displays a seat grid overlay and bounding boxes for detected objects and faces.
- **Integrated Registration**: A single script to register students to seats and capture their face data.

## Prerequisites

### Hardware
- Raspberry Pi 4 (recommended for performance)
- Raspberry Pi Camera Module v2 or v3 (compatible with `picamera2`)
- MicroSD Card (16GB or more)
- Monitor (for setup and visualization, optional for headless operation)

### Software & Services
- Raspberry Pi OS (Bullseye or later)
- Python 3.7+
- A Firebase project with Firestore Database enabled
- An ImgBB account for image hosting API key

## Installation

### 1. Clone the Repository
```bash
git clone https://github.com/gokulkannanganesamoorthy/raspberry-pi-exam-monitoring.git
cd raspberry-pi-exam-monitoring
```

### 2. Set Up a Python Virtual Environment
```bash
python3 -m venv venv
source venv/bin/activate
```

### 3. Install Dependencies
Create a `requirements.txt` file with the following content ( available already ):
```
opencv-python
picamera2
face-recognition
numpy
requests
firebase-admin
python-dotenv
pickle5
```

Then install them:
```bash
pip install -r requirements.txt
```

### 4. Download Object Detection Model Files
Download the COCO SSD MobileNet model files and place them in the specified directory (default: `/home/pi/Desktop/Object_Detection_Files/`).

- `frozen_inference_graph.pb`
- `ssd_mobilenet_v3_large_coco_2020_01_14.pbtxt`
- `coco.names`

You can find these in the [OpenCV Model Zoo](https://github.com/opencv/opencv_zoo/tree/main/models/object_detection/ssd_mobilenet_v3_large_coco_2020_01_14).

### 5. Configure Environment Variables
Create a `.env` file in the project root and add your credentials:
```ini
# ImgBB API Key for image uploads
IMGBB_API_KEY=your_imgbb_api_key_here

# Camera and Location Identifiers
CAMERA_ID=camera_001
LOCATION=Exam Hall A
```

### 6. Set Up Firebase
1. Go to your Firebase project console.
2. Go to Project Settings > Service Accounts.
3. Click "Generate new private key" and download the JSON file.
4. Rename this file to `firebase-credentials.json` and place it in the project root.

### 7. Register Students
Run the registration script to add students and their faces to the system.
```bash
python3 register_seats.py
```
Follow the on-screen menu to:
- Register a student with face capture.
- Register a student without a face.
- View current seat assignments.
- Remove a student.

## Usage

### Start Monitoring
Once students are registered, run the main detection script:
```bash
python3 exam_monitoring.py
```

A window will appear showing the camera feed with:
- A 4x5 seat grid overlay.
- Bounding boxes around detected objects and faces.
- Student names or seat numbers above detected faces.
- FPS counter.

The system will automatically:
- Detect devices (cell phones, laptops, books) and log alerts.
- Detect significant face or hand movements and log alerts.
- Upload an image to ImgBB and update Firebase for each alert.

### Exit the Application
Press `q` or `ESC` in the preview window to stop the script cleanly.

## Project Structure
```
.
├── .env                           # Environment variables (API keys, etc.)
├── firebase-credentials.json      # Firebase service account key
├── face_database.pkl              # Local storage for face encodings
├── exam_monitoring.py # Main detection script
├── register_seats.py              # Student registration script
├── requirements.txt               # Python dependencies
└── /home/pi/Desktop/Object_Detection_Files/  # Directory for model files
    ├── coco.names
    ├── frozen_inference_graph.pb
    └── ssd_mobilenet_v3_large_coco_2020_01_14.pbtxt
```

## Configuration

You can tweak the following constants in the main Python script:
- `IMAGE_WIDTH`, `IMAGE_HEIGHT`: Camera resolution.
- `ROWS`, `COLS`: Define the seat grid layout (default is 4x5).
- `FOCUSED_MSE_THRESHOLD`: Sensitivity for motion detection. Increase for less sensitivity, decrease for more.
- `DEVICE_DETECTION_COOLDOWN`: Seconds to wait before logging another alert for the same device type.
- `MIN_UPLOAD_INTERVAL`: Minimum seconds between image uploads to prevent rate-limiting.

## Contributing

Contributions are what make the open-source community such an amazing place to learn, inspire, and create. Any contributions you make are **greatly appreciated**.

1. Fork the Project
2. Create your Feature Branch (`git checkout -b feature/AmazingFeature`)
3. Commit your Changes (`git commit -m 'Add some AmazingFeature'`)
4. Push to the Branch (`git push origin feature/AmazingFeature`)
5. Open a Pull Request

## License

Distributed under the MIT License. See `LICENSE` for more information.

## Author

**Gokul Kannan Ganesamoorthy**

- GitHub: [@gokulkannanganesamoorthy](https://github.com/gokulkannanganesamoorthy)

---