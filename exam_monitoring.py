# ------------------------------------------------------------------------------
# Detect specific objects (especially 'person') and use face and hand regions
# to focus motion detection, noting significant movements. Includes face recognition
# to display the name of the person when a face is detected, or seat number for unknown faces.
# ------------------------------------------------------------------------------

import os
import sys
import cv2
import time
import numpy as np
from picamera2 import Picamera2
import pickle
import face_recognition
import json
import requests
from datetime import datetime
import firebase_admin
from firebase_admin import credentials, firestore
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# --- Configuration Constants ---
IMAGE_WIDTH = 1280
IMAGE_HEIGHT = 720
MOTION_BLUR = True

# Camera configuration
CAMERA_ID = os.getenv('CAMERA_ID', 'camera_001')
LOCATION = os.getenv('LOCATION', 'Main Entrance')

# Minimum size (in pixels) for regions to be considered valid
MIN_FACE_AREA = 30 * 30  # e.g., 900 pixels
MIN_HAND_AREA = 20 * 20  # e.g., 400 pixels

# Higher MSE threshold for significant, non-jitter motion
# (e.g., turning the face, hand gestures).
FOCUSED_MSE_THRESHOLD = 250

# --- Seat Configuration ---
ROWS = 4
COLS = 5
SEAT_WIDTH = IMAGE_WIDTH // COLS  # 1280 / 5 = 256
SEAT_HEIGHT = IMAGE_HEIGHT // ROWS  # 720 / 4 = 180

# Seat labels (A1-A5, B1-B5, C1-C5, D1-D5)
SEAT_LABELS = []
for row in range(ROWS):
    row_label = chr(65 + row)  # A, B, C, D
    for col in range(COLS):
        SEAT_LABELS.append(f"{row_label}{col + 1}")

# --- Global Variables for FPS and Motion ---
cnt_frame = 0
fps = 0
frame_gray_p = None  # Previous grayscale frame for motion detection
face_region_p = None  # Previous face region
hand_regions_p = None  # Previous hand regions

# --- Paths for Object Detection Model (Update these paths as necessary!) ---
classFile = "/home/pi/Desktop/Object_Detection_Files/coco.names"
configPath = "/home/pi/Desktop/Object_Detection_Files/ssd_mobilenet_v3_large_coco_2020_01_14.pbtxt"
weightsPath = "/home/pi/Desktop/Object_Detection_Files/frozen_inference_graph.pb"

# Path for OpenCV's Haar cascade for face detection
face_cascade_path = cv2.data.haarcascades + \
    'haarcascade_frontalface_default.xml'

# Path for face recognition database (from registration script)
# Use the same file as registration script
FACE_DATABASE_FILE = "face_database.pkl"

# Firebase credentials path
FIREBASE_CREDENTIALS_PATH = "firebase-credentials.json"

# ImgBB API key from environment
IMGBB_API_KEY = os.getenv('IMGBB_API_KEY')

# --- Firebase Initialization ---
try:
    cred = credentials.Certificate(FIREBASE_CREDENTIALS_PATH)
    firebase_admin.initialize_app(cred)
    db = firestore.client()
    print("Firebase initialized successfully")
except Exception as e:
    print(f"Error initializing Firebase: {e}")
    sys.exit(1)

# --- Seat Mapping Functions ---


def get_seat_number(x, y, w, h):
    """Calculate seat number based on face position."""
    # Use the center of the face for more accurate seat detection
    center_x = x + w // 2
    center_y = y + h // 2

    # Calculate row and column
    col = min(center_x // SEAT_WIDTH, COLS - 1)
    row = min(center_y // SEAT_HEIGHT, ROWS - 1)

    # Convert to seat label
    seat_index = row * COLS + col
    return SEAT_LABELS[seat_index]


def draw_seat_grid(img):
    """Draw seat grid overlay on the image."""
    # Draw vertical lines
    for i in range(1, COLS):
        x = i * SEAT_WIDTH
        cv2.line(img, (x, 0), (x, IMAGE_HEIGHT), (100, 100, 100), 2)

    # Draw horizontal lines
    for i in range(1, ROWS):
        y = i * SEAT_HEIGHT
        cv2.line(img, (0, y), (IMAGE_WIDTH, y), (100, 100, 100), 2)

    # Add seat labels with background for better visibility
    for row in range(ROWS):
        for col in range(COLS):
            seat_index = row * COLS + col
            label = SEAT_LABELS[seat_index]

            # Position label at top-left of each seat
            x = col * SEAT_WIDTH + 10
            y = row * SEAT_HEIGHT + 25

            # Add background rectangle for better visibility
            (text_width, text_height), _ = cv2.getTextSize(
                label, cv2.FONT_HERSHEY_SIMPLEX, 0.6, 1)
            cv2.rectangle(img, (x-5, y-20),
                          (x + text_width + 5, y), (50, 50, 50), -1)
            cv2.putText(img, label, (x, y),
                        cv2.FONT_HERSHEY_SIMPLEX, 0.6, (200, 200, 200), 1)

    return img

# --- Seat Registration Functions ---


def register_student_to_seat(student_name, seat_number):
    """Register a student to a specific seat."""
    try:
        doc_ref = db.collection('seat_assignments').document(seat_number)
        doc_ref.set({
            'student_name': student_name,
            'seat_number': seat_number,
            'registered_at': firestore.SERVER_TIMESTAMP
        })
        print(f"Registered {student_name} to seat {seat_number}")
        return True
    except Exception as e:
        print(f"Error registering seat: {e}")
        return False


def get_student_at_seat(seat_number):
    """Get the student name assigned to a seat."""
    try:
        doc_ref = db.collection('seat_assignments').document(seat_number)
        doc = doc_ref.get()
        if doc.exists:
            return doc.to_dict().get('student_name', 'Unknown')
        return 'Unknown'
    except Exception as e:
        print(f"Error getting seat assignment: {e}")
        return 'Unknown'


def display_seat_assignments():
    """Display all seat assignments."""
    try:
        docs = db.collection('seat_assignments').stream()
        print("\nCurrent Seat Assignments:")
        for doc in docs:
            data = doc.to_dict()
            print(f"  {data['seat_number']}: {data['student_name']}")
    except Exception as e:
        print(f"Error displaying seat assignments: {e}")

# --- Seat Status Update Functions ---


def update_seat_status(seat_number, person_name, event_type, is_occupied=True):
    """Update the real-time status of a seat in Firebase."""
    try:
        seat_ref = db.collection('seat_status').document(seat_number)
        seat_data = {
            'seat_number': seat_number,
            'current_occupant': person_name,
            'is_occupied': is_occupied,
            'last_activity': event_type,
            'last_updated': firestore.SERVER_TIMESTAMP,
            'camera_id': CAMERA_ID,
            'location': LOCATION
        }

        # Check if this is a known or unknown person
        is_unknown = person_name.startswith("Seat") or person_name == "Unknown"
        seat_data['is_unknown'] = is_unknown

        # Update the seat status
        seat_ref.set(seat_data, merge=True)

        # Also update a collection for current session tracking
        session_ref = db.collection('current_session').document(seat_number)
        session_data = {
            'seat_number': seat_number,
            'person_name': person_name,
            'session_start': firestore.SERVER_TIMESTAMP,
            'last_activity': event_type,
            'activities': firestore.ArrayUnion([{
                'activity': event_type,
                'timestamp': firestore.SERVER_TIMESTAMP
            }])
        }
        session_ref.set(session_data, merge=True)

        return True
    except Exception as e:
        print(f"Error updating seat status: {e}")
        return False


def clear_seat_status(seat_number):
    """Clear a seat status when no one is detected."""
    try:
        seat_ref = db.collection('seat_status').document(seat_number)
        seat_ref.update({
            'is_occupied': False,
            'current_occupant': None,
            'last_updated': firestore.SERVER_TIMESTAMP
        })

        # End the session
        session_ref = db.collection('current_session').document(seat_number)
        session_ref.update({
            'session_end': firestore.SERVER_TIMESTAMP,
            'is_active': False
        })

        return True
    except Exception as e:
        print(f"Error clearing seat status: {e}")
        return False

# --- ImgBB Upload Function ---


def upload_to_imgbb(image, max_size=(640, 480), quality=85, max_retries=3):
    """Upload optimized image to ImgBB with retry mechanism."""
    for attempt in range(max_retries):
        try:
            # Resize image if larger than max_size
            h, w = image.shape[:2]
            if w > max_size[0] or h > max_size[1]:
                # Calculate scaling factor
                scale = min(max_size[0]/w, max_size[1]/h)
                new_w, new_h = int(w * scale), int(h * scale)
                image = cv2.resize(image, (new_w, new_h),
                                   interpolation=cv2.INTER_AREA)

            # Compress image
            encode_param = [int(cv2.IMWRITE_JPEG_QUALITY), quality]
            _, img_encoded = cv2.imencode('.jpg', image, encode_param)
            img_bytes = img_encoded.tobytes()

            # Check image size (ImgBB has a 32MB limit)
            if len(img_bytes) > 32 * 1024 * 1024:  # 32MB
                print("Image too large for ImgBB, skipping upload")
                return None

            # Prepare the request
            url = "https://api.imgbb.com/1/upload"
            payload = {
                "key": IMGBB_API_KEY,
                "expiration": 3600,  # 1 hour expiration
                "name": f"exam_alert_{int(time.time())}"  # Unique filename
            }
            files = {
                "image": img_bytes
            }

            # Send the request with timeout
            response = requests.post(
                url,
                files=files,
                data=payload,
                timeout=10  # 10 second timeout
            )
            response.raise_for_status()

            # Parse the response
            result = response.json()
            if result.get("success"):
                print(f"Image uploaded successfully (attempt {attempt + 1})")
                return result["data"]["url"]
            else:
                error_msg = result.get('error', 'Unknown error')
                print(
                    f"ImgBB upload failed (attempt {attempt + 1}): {error_msg}")

        except requests.exceptions.RequestException as e:
            print(f"Network error during upload (attempt {attempt + 1}): {e}")
        except Exception as e:
            print(f"Error uploading to ImgBB (attempt {attempt + 1}): {e}")

        if attempt < max_retries - 1:
            time.sleep(2 ** attempt)  # Exponential backoff

    print(f"Failed to upload after {max_retries} attempts")
    return None

# --- Firebase Update Function ---


def update_firebase(event_type, person_name, mse_value, image_url=None, device_name=None, seat_number=None):
    """Update Firebase with exam_alerts."""
    try:
        doc_ref = db.collection('exam_alerts').document()

        # Determine if this is an unknown person
        is_unknown = person_name.startswith("Seat") or person_name == "Unknown"

        doc_data = {
            'camera_id': CAMERA_ID,
            'location': LOCATION,
            'event_type': event_type,
            'person_name': person_name,
            'timestamp': datetime.now().isoformat(),
            'created_at': firestore.SERVER_TIMESTAMP,
            'mse_value': mse_value,
            'image_url': image_url,
            'events': [f"{person_name}'s {event_type.upper()} DETECTED"],
            'unknown_faces': 1 if is_unknown else 0,
            'faces_detected': [person_name] if not is_unknown else [],
            'sensor_readings': [f"MSE: {mse_value:.2f}" if mse_value else "N/A"],
            'angle': 0,  # You can add actual angle detection if needed
            'language': 'en',
            'is_unknown': is_unknown
        }

        # ALWAYS add seat number if provided
        if seat_number:
            doc_data['seat_number'] = seat_number
            # Update seat status for all detections
            update_seat_status(seat_number, person_name, event_type)

            # For unknown persons, update their activity in a separate collection
            if is_unknown:
                unknown_ref = db.collection(
                    'unknown_persons').document(seat_number)
                unknown_data = {
                    'seat_number': seat_number,
                    'last_seen': firestore.SERVER_TIMESTAMP,
                    'last_activity': event_type,
                    'activity_count': firestore.Increment(1),
                    'camera_id': CAMERA_ID,
                    'location': LOCATION,
                    'person_name': person_name  # Store the display name
                }
                unknown_ref.set(unknown_data, merge=True)

        # Add device name if provided
        if device_name:
            doc_data['device_name'] = device_name
            doc_data['events'] = [
                f"{person_name}'s {device_name.upper()} USAGE DETECTED"]

        doc_ref.set(doc_data)
        print(
            f"Firebase updated with {event_type} event for {person_name} at seat {seat_number}")
        return True
    except Exception as e:
        print(f"Error updating Firebase: {e}")
        return False

# --- Motion Detection Helper Function ---


def mse(image_a, image_b):
    """Calculates the Mean Squared Error between two images."""
    if image_a.shape != image_b.shape:
        return float('inf')
    err = np.sum((image_a.astype("float") - image_b.astype("float")) ** 2)
    err /= float(image_a.shape[0] * image_a.shape[1])
    return err

# --- FPS Visualization Function ---


def visualize_fps(image, current_fps: float):
    """Draws the FPS counter on the image."""
    if len(np.shape(image)) < 3:
        text_color = (255, 255, 255)
    else:
        text_color = (0, 255, 0)

    row_size = 20
    left_margin = 24
    font_size = 1
    font_thickness = 1

    fps_text = 'FPS = {:.1f}'.format(current_fps)
    text_location = (left_margin, row_size)
    cv2.putText(image, fps_text, text_location, cv2.FONT_HERSHEY_PLAIN,
                font_size, text_color, font_thickness)
    return image


# --- Object Detection Setup and Function ---
try:
    # Load class names
    classNames = []
    with open(classFile, "rt") as f:
        classNames = f.read().rstrip("\n").split("\n")

    # Initialize detection model
    net = cv2.dnn_DetectionModel(weightsPath, configPath)
    net.setInputSize(320, 320)
    net.setInputScale(1.0 / 127.5)
    net.setInputMean((127.5, 127.5, 127.5))
    net.setInputSwapRB(True)

    # Define the list of specific objects to detect
    target_objects = ['person', 'cell phone',
                      'book', 'laptop']  # Added book and laptop

    # Initialize face detector
    face_cascade = cv2.CascadeClassifier(face_cascade_path)
    if face_cascade.empty():
        print("Error loading face cascade classifier")
        sys.exit(1)

    # Load face recognition database
    known_face_encodings = []
    known_face_names = []

    if os.path.exists(FACE_DATABASE_FILE):
        with open(FACE_DATABASE_FILE, 'rb') as f:
            data = pickle.load(f)
            known_face_encodings = data['encodings']
            known_face_names = data['names']
        print(f"Loaded {len(known_face_names)} registered faces.")
    else:
        print("Warning: No face database found. Run register_faces.py first.")

except Exception as e:
    print(f"Error loading model files: {e}")
    print("Please ensure your paths are correct and files exist.")
    sys.exit(1)


def getObjects(img, thres, nms, draw=True, objects=[]):
    """Performs object detection using the pre-loaded DNN model."""
    classIds, confs, bbox = net.detect(
        img, confThreshold=thres, nmsThreshold=nms)

    if len(objects) == 0:
        objects = target_objects

    objectInfo = []
    if len(classIds) != 0:
        for classId, confidence, box in zip(classIds.flatten(), confs.flatten(), bbox):
            className = classNames[classId - 1]
            if className in objects:
                # Unpack the bounding box: box is [x, y, w, h]
                x, y, w, h = box

                objectInfo.append([box, className, confidence])
                if (draw):
                    # Different colors for different objects
                    if className == 'person':
                        color = (0, 255, 0)  # Green for person
                    elif className == 'cell phone':
                        color = (0, 0, 255)  # Red for cell phone
                    elif className == 'book':
                        color = (255, 0, 255)  # Magenta for book
                    elif className == 'laptop':
                        color = (255, 165, 0)  # Orange for laptop
                    else:
                        color = (0, 255, 0)  # Default green

                    # Draw rectangle with the specified color
                    cv2.rectangle(img, box, color=color, thickness=2)

                    # Label without confidence score
                    label = f"{className.upper()}"
                    cv2.putText(img, label, (x + 10, y + 30),
                                cv2.FONT_HERSHEY_COMPLEX, 0.7, color, 2)

    return img, objectInfo


def detect_faces(img, draw=True, recognize=True):
    """Detect faces and assign seat numbers to unknown faces."""
    # Convert to RGB for face_recognition
    rgb_img = cv2.cvtColor(img, cv2.COLOR_BGR2RGB)

    # Detect faces using Haar cascade
    gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
    faces = face_cascade.detectMultiScale(gray, 1.1, 4)

    face_info = []
    for (x, y, w, h) in faces:
        # Filter by minimum area
        if w * h >= MIN_FACE_AREA:
            person_name = "Unknown"
            seat_number = get_seat_number(x, y, w, h)

            # Try to recognize the face if requested and we have known faces
            if recognize and len(known_face_encodings) > 0:
                try:
                    # Get face encoding for the detected face
                    face_encoding = face_recognition.face_encodings(
                        rgb_img,
                        known_face_locations=[(y, x+w, y+h, x)]
                    )

                    if face_encoding and len(face_encoding) > 0:
                        # Compare with known faces
                        matches = face_recognition.compare_faces(
                            known_face_encodings,
                            face_encoding[0],
                            tolerance=0.6
                        )

                        # Find the best match
                        face_distances = face_recognition.face_distance(
                            known_face_encodings,
                            face_encoding[0]
                        )
                        if face_distances and len(face_distances) > 0:
                            best_match_index = np.argmin(face_distances)
                            if best_match_index < len(matches) and matches[best_match_index]:
                                person_name = known_face_names[best_match_index]
                except Exception as e:
                    print(f"Face recognition error: {e}")

            # Use seat number for unknown faces
            display_name = person_name if person_name != "Unknown" else f"Seat {seat_number}"

            face_info.append(
                [(x, y, w, h), "face", display_name, 0, seat_number])
            if draw:
                # Different colors for known vs unknown faces
                color = (0, 255, 0) if person_name != "Unknown" else (0, 0, 255)

                # Draw a thicker rectangle for unknown faces
                thickness = 3 if person_name == "Unknown" else 2
                cv2.rectangle(img, (x, y), (x+w, y+h), color, thickness)

                # Display name or seat number
                if person_name != "Unknown":
                    label = f"FACE: {display_name} ({seat_number})"
                    cv2.putText(img, label, (x, y-10),
                                cv2.FONT_HERSHEY_SIMPLEX, 0.7, color, 2)
                else:
                    # For unknown faces, make the seat number more prominent
                    label = f"UNKNOWN PERSON - SEAT {seat_number}"
                    # Add a warning background
                    cv2.rectangle(img, (x, y-35), (x+len(label)
                                  * 12+10, y), (0, 0, 255), -1)
                    cv2.putText(img, label, (x, y-10),
                                cv2.FONT_HERSHEY_SIMPLEX, 0.7, (255, 255, 255), 2)

    return img, face_info


if __name__ == "__main__":

    picam2 = None
    try:
        # Initialize Picamera2
        picam2 = Picamera2()
        camera_config = picam2.create_preview_configuration(
            main={"format": 'XRGB8888', "size": (IMAGE_WIDTH, IMAGE_HEIGHT)})
        picam2.configure(camera_config)
        picam2.start()

        print(f"Camera started at {IMAGE_WIDTH}x{IMAGE_HEIGHT}.")
        print(
            f"Focused motion detection threshold (MSE): {FOCUSED_MSE_THRESHOLD}")
        print(f"Seat grid: {ROWS}x{COLS} (A1-{SEAT_LABELS[-1]})")

        # Track detected devices to avoid multiple uploads for the same detection
        detected_devices = {}
        DEVICE_DETECTION_COOLDOWN = 30  # seconds between uploads for the same device type

        # Rate limiting for uploads
        last_upload_time = 0
        MIN_UPLOAD_INTERVAL = 5  # Minimum 5 seconds between uploads

        # Track last seen faces to update seat status when someone leaves
        last_seen_faces = {}
        FACE_ABSENCE_THRESHOLD = 10  # Number of frames without face before clearing seat

        while True:
            start_time = time.time()

            # Read the frame
            im = picam2.capture_array()
            frame_raw = cv2.cvtColor(im, cv2.COLOR_RGBA2BGR)

            if frame_raw is None:
                continue

            # 1. Image Pre-processing
            frame = cv2.GaussianBlur(
                frame_raw, (3, 3), 0) if MOTION_BLUR else frame_raw
            frame_gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)

            # 2. Draw seat grid
            display_frame = draw_seat_grid(frame_raw.copy())

            # 3. Object Detection
            display_frame, objectInfo = getObjects(display_frame, 0.45, 0.2)

            # 4. Face Detection and Recognition
            display_frame, faceInfo = detect_faces(
                display_frame, recognize=True)

            # Get person name and seat number for device detection
            person_name = "Unknown"
            seat_number = None
            current_detected_seats = set()

            if faceInfo and len(faceInfo) > 0:
                for face in faceInfo:
                    person_name = face[2]
                    seat_number = face[4] if len(face) > 4 else None
                    if seat_number:
                        current_detected_seats.add(seat_number)
                        last_seen_faces[seat_number] = cnt_frame

            # Check for faces that are no longer detected
            seats_to_clear = []
            for seat, last_frame in last_seen_faces.items():
                if cnt_frame - last_frame > FACE_ABSENCE_THRESHOLD:
                    seats_to_clear.append(seat)

            for seat in seats_to_clear:
                clear_seat_status(seat)
                del last_seen_faces[seat]
                print(f"Cleared status for seat {seat} - no longer detected")

            # 5. Device Detection (Cellphone, Book, Laptop)
            current_time = time.time()
            for box, object_name, confidence in objectInfo:
                if object_name in ['cell phone', 'book', 'laptop']:
                    # Check if we've recently uploaded this device type
                    last_detection_time = detected_devices.get(object_name, 0)

                    if current_time - last_detection_time > DEVICE_DETECTION_COOLDOWN:
                        # Draw a warning box around the device
                        x, y, w, h = box
                        cv2.rectangle(display_frame, (x-5, y-5),
                                      (x+w+5, y+h+5), (0, 0, 255), 3)

                        # Add warning text
                        warning_text = f"{person_name} USING {object_name.upper()}!"
                        cv2.putText(display_frame, warning_text, (x, y-15),
                                    cv2.FONT_HERSHEY_SIMPLEX, 0.7, (0, 0, 255), 2)

                        print(
                            f'Frame{cnt_frame}: **{person_name} USING {object_name.upper()}!** at seat {seat_number}')

                        # Check upload rate limit
                        if current_time - last_upload_time >= MIN_UPLOAD_INTERVAL:
                            image_url = upload_to_imgbb(display_frame)
                            if image_url:
                                last_upload_time = current_time
                                update_firebase(
                                    "device usage", person_name, None, image_url, object_name, seat_number)

                        # Update the last detection time
                        detected_devices[object_name] = current_time

            # Extract hand regions (cell phones as proxies)
            hand_regions = [(box, conf) for box, name,
                            conf in objectInfo if name == 'cell phone']

            # 6. Focused Motion Detection for Face
            current_face_region = None
            if faceInfo and len(faceInfo) > 0:
                for face in faceInfo:
                    current_face_region = face[0]  # Get the face region
                    person_name = face[2]  # Get the person's name
                    seat_number = face[4] if len(face) > 4 else None

                    # Update seat status for face detection
                    if seat_number:
                        update_seat_status(
                            seat_number, person_name, "face detected")

                    if cnt_frame > 0 and frame_gray_p is not None and face_region_p is not None:
                        # Get current face region
                        (x, y, w, h) = current_face_region
                        x, y = max(0, x), max(0, y)
                        x_end, y_end = min(
                            IMAGE_WIDTH, x + w), min(IMAGE_HEIGHT, y + h)

                        # Get previous face region
                        (x_p, y_p, w_p, h_p) = face_region_p

                        # Crop current and previous frames to face region
                        cropped_current_face = frame_gray[y:y_end, x:x_end]

                        # Use the same region coordinates from the previous frame
                        x_p_end, y_p_end = min(
                            IMAGE_WIDTH, x_p + w_p), min(IMAGE_HEIGHT, y_p + h_p)
                        cropped_previous_face = frame_gray_p[y_p:y_p_end, x_p:x_p_end]

                        # Resize to same dimensions if needed
                        if cropped_current_face.size > 0 and cropped_previous_face.size > 0:
                            if cropped_current_face.shape != cropped_previous_face.shape:
                                cropped_previous_face = cv2.resize(cropped_previous_face,
                                                                   (cropped_current_face.shape[1],
                                                                    cropped_current_face.shape[0]))

                            face_mse = mse(cropped_current_face,
                                           cropped_previous_face)

                            if face_mse > FOCUSED_MSE_THRESHOLD:
                                # Significant face movement detected
                                movement_text = f"{person_name}'s FACE MOVEMENT DETECTED"
                                cv2.putText(display_frame, movement_text, (x, y - 30),
                                            cv2.FONT_HERSHEY_COMPLEX, 0.7, (0, 0, 255), 2)
                                print(
                                    f'Frame{cnt_frame}: **{person_name}\'s FACE MOVEMENT DETECTED!** MSE: {face_mse:.2f} at seat {seat_number}')

                                # Check upload rate limit
                                if current_time - last_upload_time >= MIN_UPLOAD_INTERVAL:
                                    image_url = upload_to_imgbb(display_frame)
                                    if image_url:
                                        last_upload_time = current_time
                                        update_firebase(
                                            "face movement", person_name, face_mse, image_url, None, seat_number)

            # 7. Focused Motion Detection for Hands
            current_hand_regions = []
            if hand_regions:
                for i, (box, conf) in enumerate(hand_regions):
                    (x, y, w, h) = box
                    x, y = max(0, x), max(0, y)
                    x_end, y_end = min(
                        IMAGE_WIDTH, x + w), min(IMAGE_HEIGHT, y + h)

                    # Store current hand region
                    current_hand_regions.append((x, y, w, h))

                    if cnt_frame > 0 and frame_gray_p is not None and hand_regions_p is not None and len(hand_regions_p) > 0 and i < len(hand_regions_p):
                        # Get previous hand region
                        (x_p, y_p, w_p, h_p) = hand_regions_p[i]

                        # Crop current and previous frames to hand region
                        cropped_current_hand = frame_gray[y:y_end, x:x_end]

                        # Use the same region coordinates from the previous frame
                        x_p_end, y_p_end = min(
                            IMAGE_WIDTH, x_p + w_p), min(IMAGE_HEIGHT, y_p + h_p)
                        cropped_previous_hand = frame_gray_p[y_p:y_p_end, x_p:x_p_end]

                        # Resize to same dimensions if needed
                        if cropped_current_hand.size > 0 and cropped_previous_hand.size > 0:
                            if cropped_current_hand.shape != cropped_previous_hand.shape:
                                cropped_previous_hand = cv2.resize(cropped_previous_hand,
                                                                   (cropped_current_hand.shape[1],
                                                                    cropped_current_hand.shape[0]))

                            hand_mse = mse(cropped_current_hand,
                                           cropped_previous_hand)

                            if hand_mse > FOCUSED_MSE_THRESHOLD:
                                person_name = faceInfo[0][2] if faceInfo and len(
                                    faceInfo) > 0 else "Unknown"
                                seat_number = faceInfo[0][4] if faceInfo and len(
                                    faceInfo) > 0 and len(faceInfo[0]) > 4 else None
                                movement_text = f"{person_name}'s HAND MOVEMENT DETECTED"
                                cv2.putText(display_frame, movement_text, (x, y - 10),
                                            cv2.FONT_HERSHEY_COMPLEX, 0.7, (0, 0, 255), 2)
                                print(
                                    f'Frame{cnt_frame}: **{person_name}\'s HAND MOVEMENT DETECTED!** MSE: {hand_mse:.2f} at seat {seat_number}')

                                # Check upload rate limit
                                if current_time - last_upload_time >= MIN_UPLOAD_INTERVAL:
                                    image_url = upload_to_imgbb(display_frame)
                                    if image_url:
                                        last_upload_time = current_time
                                        update_firebase(
                                            "hand movement", person_name, hand_mse, image_url, None, seat_number)

            # 8. Visualization (FPS)
            display_frame = visualize_fps(display_frame, fps)

            cv2.imshow("Focused Detection Output", display_frame)

            # 9. Update State
            frame_gray_p = frame_gray.copy()  # Store current gray frame
            if current_face_region is not None:
                face_region_p = current_face_region  # Store current face region

            if current_hand_regions:
                hand_regions_p = current_hand_regions.copy()  # Store current hand regions

            # 10. FPS Calculation
            end_time = time.time()
            seconds = end_time - start_time
            if seconds > 0:
                fps = 1.0 / seconds

            cnt_frame += 1

            # Exit check
            key = cv2.waitKey(1) & 0xFF
            if key == ord('q') or key == 27:
                break

    except Exception as e:
        print(f"\nAn error occurred: {e}")
    finally:
        print("\nCleaning up...")
        cv2.destroyAllWindows()
        if picam2:
            picam2.stop()
        sys.exit(0)
