import { initializeApp } from 'firebase/app';
import { getAuth } from 'firebase/auth';
import { getFirestore, connectFirestoreEmulator } from 'firebase/firestore';

// Your Firebase configuration
const firebaseConfig = {
  apiKey: "",
  authDomain: "",
  projectId: "",
  storageBucket: "",
  messagingSenderId: "",
  appId: "",
  measurementId: ""
};

// Initialize Firebase
const app = initializeApp(firebaseConfig);

// Initialize Firestore with error handling
let db;
let auth;
try {
  db = getFirestore(app);
  auth = getAuth(app);
  
  // Only connect to emulator in development if needed
  // Uncomment the lines below if you want to use Firebase emulator
  // if (process.env.NODE_ENV === 'development') {
  //   connectFirestoreEmulator(db, 'localhost', 8080);
  // }
} catch (error) {
  console.error('Error initializing Firestore:', error);
  throw error;
}

export { db, auth };
export default app;
