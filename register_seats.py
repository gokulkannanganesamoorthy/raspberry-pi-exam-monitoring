#!/usr/bin/env python3
import os
import sys
import cv2
import time
import numpy as np
from picamera2 import Picamera2
import pickle
import face_recognition
import firebase_admin
from firebase_admin import credentials, firestore

# --- Configuration Constants ---
IMAGE_WIDTH = 640
IMAGE_HEIGHT = 480
FACE_DATABASE_FILE = "face_database.pkl"
FIREBASE_CREDENTIALS_PATH = "firebase-credentials.json"

# --- Initialize Firebase ---
try:
    cred = credentials.Certificate(FIREBASE_CREDENTIALS_PATH)
    firebase_admin.initialize_app(cred)
    db = firestore.client()
    print("Firebase initialized successfully")
except Exception as e:
    print(f"Error initializing Firebase: {e}")
    sys.exit(1)

# --- Initialize Camera ---
picam2 = None
try:
    picam2 = Picamera2()
    camera_config = picam2.create_preview_configuration(
        main={"format": 'XRGB8888', "size": (IMAGE_WIDTH, IMAGE_HEIGHT)})
    picam2.configure(camera_config)
    picam2.start()
    print("Camera initialized successfully")
except Exception as e:
    print(f"Error initializing camera: {e}")
    sys.exit(1)

# --- Load existing face database ---


def load_face_database():
    """Load existing face database or create new one. Handles migration from old format."""
    # This is the structure for a new database
    default_data = {'encodings': [], 'names': [], 'seats': []}

    if os.path.exists(FACE_DATABASE_FILE):
        try:
            with open(FACE_DATABASE_FILE, 'rb') as f:
                data = pickle.load(f)
                # --- MIGRATION LOGIC ---
                # Check if the 'seats' key exists (for backward compatibility)
                if 'seats' not in data:
                    print("\n!!! MIGRATING OLD FACE DATABASE FORMAT !!!")
                    # Add the 'seats' key and populate it with 'Unknown' to match existing entries
                    data['seats'] = ['Unknown'] * len(data.get('names', []))
                    print(
                        "Migration complete. Existing faces are now associated with 'Unknown' seats.")
                    # Save the migrated format immediately to avoid this step again
                    save_face_database(data)
                    print("Database updated to new format.")
                # --- END MIGRATION LOGIC ---
                return data
        except (pickle.UnpicklingError, EOFError, Exception) as e:
            print(f"\nError reading face database file: {e}")
            print("The file might be corrupt. Starting with a new face database.")
            # If the file is corrupt, it's safer to start fresh.
            return default_data
    else:
        # If no file exists, return the default empty structure
        return default_data

# --- Save face database ---


def save_face_database(data):
    """Save face database to file."""
    with open(FACE_DATABASE_FILE, 'wb') as f:
        pickle.dump(data, f)

# --- Face detection and encoding ---


def detect_and_encode_face(frame):
    """Detect face in frame and return encoding."""
    try:
        # Convert to RGB for face_recognition
        rgb_frame = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)

        # Detect faces
        face_locations = face_recognition.face_locations(rgb_frame)

        if len(face_locations) > 0:
            # Get the first face encoding
            face_encoding = face_recognition.face_encodings(
                rgb_frame, face_locations)[0]
            return face_encoding, face_locations[0]
        return None, None
    except Exception as e:
        print(f"Error detecting face: {e}")
        return None, None

# --- Register student with face ---


def register_student_with_face(student_name, seat_number):
    """Register a student with face capture to a specific seat."""
    print(f"\nRegistering {student_name} to seat {seat_number}")
    print("Position your face in the frame. Press 'c' to capture, 'q' to quit.")

    # Load existing database (now with migration logic)
    face_data = load_face_database()

    # Check if student already registered
    if student_name in face_data['names']:
        print(f"Warning: {student_name} is already registered. Overwriting...")
        # Remove old entry
        idx = face_data['names'].index(student_name)
        face_data['encodings'].pop(idx)
        face_data['names'].pop(idx)
        face_data['seats'].pop(idx)

    captured = False
    face_encoding = None

    while not captured:
        # Capture frame
        im = picam2.capture_array()
        frame = cv2.cvtColor(im, cv2.COLOR_RGBA2BGR)

        # Detect face
        encoding, location = detect_and_encode_face(frame)

        # Draw face rectangle if detected
        if location:
            top, right, bottom, left = location
            cv2.rectangle(frame, (left, top), (right, bottom), (0, 255, 0), 2)
            cv2.putText(frame, "Face Detected - Press 'c' to capture",
                        (10, 30), cv2.FONT_HERSHEY_SIMPLEX, 0.7, (0, 255, 0), 2)
        else:
            cv2.putText(frame, "No face detected - Position your face",
                        (10, 30), cv2.FONT_HERSHEY_SIMPLEX, 0.7, (0, 0, 255), 2)

        # Add instructions
        cv2.putText(frame, "Press 'c' to capture | 'q' to quit",
                    (10, IMAGE_HEIGHT - 20), cv2.FONT_HERSHEY_SIMPLEX, 0.6, (255, 255, 255), 2)

        cv2.imshow("Face Registration", frame)

        key = cv2.waitKey(1) & 0xFF

        if key == ord('c') and encoding is not None:
            face_encoding = encoding
            captured = True
            print("Face captured successfully!")
        elif key == ord('q'):
            print("Registration cancelled.")
            cv2.destroyAllWindows()
            return False

    cv2.destroyAllWindows()

    # Save face encoding
    if face_encoding is not None:
        face_data['encodings'].append(face_encoding)
        face_data['names'].append(student_name)
        face_data['seats'].append(seat_number)
        save_face_database(face_data)

        # Register to Firebase
        try:
            doc_ref = db.collection('seat_assignments').document(seat_number)
            doc_ref.set({
                'student_name': student_name,
                'seat_number': seat_number,
                'registered_at': firestore.SERVER_TIMESTAMP,
                'face_registered': True
            })
            print(
                f"Successfully registered {student_name} to seat {seat_number} with face recognition")
            return True
        except Exception as e:
            print(f"Error registering to Firebase: {e}")
            return False

    return False

# --- Register student without face ---


def register_student_only(student_name, seat_number):
    """Register a student to a seat without face capture."""
    try:
        doc_ref = db.collection('seat_assignments').document(seat_number)
        doc_ref.set({
            'student_name': student_name,
            'seat_number': seat_number,
            'registered_at': firestore.SERVER_TIMESTAMP,
            'face_registered': False
        })
        print(f"Registered {student_name} to seat {seat_number} (no face)")
        return True
    except Exception as e:
        print(f"Error registering seat: {e}")
        return False

# --- Display seat assignments ---


def display_seat_assignments():
    """Display all seat assignments."""
    try:
        docs = db.collection('seat_assignments').stream()
        print("\nCurrent Seat Assignments:")
        print("-" * 40)
        for doc in docs:
            data = doc.to_dict()
            face_status = "✓" if data.get('face_registered', False) else "✗"
            print(
                f"  {data['seat_number']}: {data['student_name']} [Face: {face_status}]")
    except Exception as e:
        print(f"Error displaying seat assignments: {e}")

# --- Remove student from seat ---


def remove_student_from_seat(seat_number):
    """Remove student from seat and their face data."""
    try:
        # Get student name
        doc_ref = db.collection('seat_assignments').document(seat_number)
        doc = doc_ref.get()

        if doc.exists:
            student_name = doc.to_dict().get('student_name')

            # Remove from Firebase
            doc_ref.delete()

            # Remove from face database
            face_data = load_face_database()
            if student_name in face_data['names']:
                idx = face_data['names'].index(student_name)
                face_data['encodings'].pop(idx)
                face_data['names'].pop(idx)
                face_data['seats'].pop(idx)
                save_face_database(face_data)

            print(f"Removed {student_name} from seat {seat_number}")
            return True
        else:
            print(f"Seat {seat_number} is empty")
            return False
    except Exception as e:
        print(f"Error removing student: {e}")
        return False

# --- View unknown persons activity ---


def view_unknown_persons_activity():
    """View activity of unknown persons by seat."""
    try:
        docs = db.collection('unknown_persons').stream()
        print("\nUnknown Persons Activity:")
        print("-" * 40)
        for doc in docs:
            data = doc.to_dict()
            print(f"  Seat {data['seat_number']}:")
            print(f"    Last seen: {data.get('last_seen', 'N/A')}")
            print(f"    Last activity: {data.get('last_activity', 'N/A')}")
            print(f"    Activity count: {data.get('activity_count', 0)}")
            print(f"    Camera: {data.get('camera_id', 'N/A')}")
            print()
    except Exception as e:
        print(f"Error viewing unknown persons: {e}")

# --- View current seat status ---


def view_current_seat_status():
    """View real-time status of all seats."""
    try:
        docs = db.collection('seat_status').stream()
        print("\nCurrent Seat Status:")
        print("-" * 40)

        # Create a dictionary of seat statuses
        seat_status = {}
        for doc in docs:
            data = doc.to_dict()
            seat_status[data['seat_number']] = data

        # Display all seats (A1-D5)
        rows = ['A', 'B', 'C', 'D']
        for row in rows:
            for col in range(1, 6):
                seat = f"{row}{col}"
                if seat in seat_status:
                    status = seat_status[seat]
                    occupant = status.get('current_occupant', 'Unknown')
                    last_activity = status.get('last_activity', 'N/A')
                    last_updated = status.get('last_updated', 'N/A')

                    # Format the display
                    if status.get('is_occupied', False):
                        print(f"  {seat}: {occupant} [{last_activity}]")
                    else:
                        print(f"  {seat}: [EMPTY]")
                else:
                    print(f"  {seat}: [NO DATA]")
        print()
    except Exception as e:
        print(f"Error viewing seat status: {e}")

# --- View current session ---


def view_current_session():
    """View current active sessions."""
    try:
        docs = db.collection('current_session').where(
            'is_active', '==', True).stream()
        print("\nCurrent Active Sessions:")
        print("-" * 40)
        for doc in docs:
            data = doc.to_dict()
            print(f"  Seat {data['seat_number']}: {data['person_name']}")
            print(f"    Session started: {data.get('session_start', 'N/A')}")
            print(f"    Activities: {len(data.get('activities', []))}")
            print()
    except Exception as e:
        print(f"Error viewing sessions: {e}")

# --- Main menu ---


def main():
    print("=" * 50)
    print("    Student Registration System with Face Recognition")
    print("=" * 50)

    while True:
        print("\nOptions:")
        print("1. Register student with face capture")
        print("2. Register student without face")
        print("3. Display all seat assignments")
        print("4. Remove student from seat")
        print("5. View unknown persons activity")
        print("6. View current seat status")
        print("7. View current active sessions")
        print("8. Exit")

        choice = input("\nEnter your choice (1-8): ").strip()

        if choice == "1":
            seat = input("Enter seat number (e.g., A1, B3): ").upper()
            name = input("Enter student name: ").strip()
            if name and seat:
                register_student_with_face(name, seat)
            else:
                print("Invalid input. Please try again.")

        elif choice == "2":
            seat = input("Enter seat number (e.g., A1, B3): ").upper()
            name = input("Enter student name: ").strip()
            if name and seat:
                register_student_only(name, seat)
            else:
                print("Invalid input. Please try again.")

        elif choice == "3":
            display_seat_assignments()

        elif choice == "4":
            seat = input(
                "Enter seat number to remove (e.g., A1, B3): ").upper()
            if seat:
                remove_student_from_seat(seat)
            else:
                print("Invalid seat number.")

        elif choice == "5":
            view_unknown_persons_activity()

        elif choice == "6":
            view_current_seat_status()

        elif choice == "7":
            view_current_session()

        elif choice == "8":
            print("Exiting...")
            break

        else:
            print("Invalid choice. Please try again.")


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\nExiting...")
    finally:
        cv2.destroyAllWindows()
        if picam2:
            picam2.stop()
