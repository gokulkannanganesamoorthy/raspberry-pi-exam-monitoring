# Exam Camera Dashboard

A React dashboard for viewing exam camera data from Firebase and ImageBB.

## Features

- 📊 Real-time data visualization from Firebase Firestore
- 🖼️ Image gallery with ImageBB integration
- 📱 Responsive Material-UI design
- 🔍 Detailed data table with filtering and sorting
- 📈 Summary statistics cards
- 🎯 Event tracking and face detection monitoring

## Setup Instructions

### 1. Firebase Configuration

1. Go to your Firebase project console
2. Navigate to Project Settings > General
3. Copy your Firebase configuration
4. Update `src/firebase.js` with your actual Firebase config:

```javascript
const firebaseConfig = {
  apiKey: "your-actual-api-key",
  authDomain: "your-project.firebaseapp.com",
  projectId: "your-actual-project-id",
  storageBucket: "your-project.appspot.com",
  messagingSenderId: "your-sender-id",
  appId: "your-app-id"
};
```

### 2. Collection Name

Update the collection name in `src/Dashboard.js`:

```javascript
// Replace 'your-collection-name' with your actual collection name
const q = query(collection(db, 'your-actual-collection-name'), orderBy('created_at', 'desc'));
```

### 3. Install Dependencies

```bash
npm install
```

### 4. Start the Development Server

```bash
npm start
```

## Data Structure

The dashboard expects Firebase documents with the following structure:

```javascript
{
  angle: 0,                    // number
  camera_id: "CAM_01",         // string
  created_at: timestamp,       // Firebase timestamp
  events: ["Turning back detected"], // array of strings
  faces_detected: [],           // array
  image_url: "https://i.ibb.co/...", // string (ImageBB URL)
  language: "en",               // string
  location: "Unknown",          // string
  sensor_readings: [0,0,0,0,0], // array of numbers
  timestamp: "20251011-052627", // string
  unknown_faces: 0              // number
}
```

## Components

- **Summary Cards**: Display total records, unknown faces, events, and active cameras
- **Image Gallery**: Grid view of captured images with click-to-expand functionality
- **Data Table**: Detailed view of all records with event chips and sensor readings
- **Image Dialog**: Full-size image viewer

## Technologies Used

- React 18
- Material-UI (MUI)
- Firebase Firestore
- ImageBB integration
- Recharts (for future chart implementations)
- date-fns (for date formatting)

## Customization

You can customize the dashboard by:

1. Modifying the theme in `src/App.js`
2. Adding new data visualizations
3. Implementing real-time updates with Firebase listeners
4. Adding filtering and search functionality
5. Creating export features for reports

## Security Notes

- Ensure your Firebase security rules are properly configured
- Consider implementing authentication for production use
- Validate all data inputs and handle errors gracefully