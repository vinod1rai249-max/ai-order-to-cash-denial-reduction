import { initializeApp } from "firebase/app";
import { 
  getAuth, 
  onAuthStateChanged 
} from "firebase/auth";
import { useEffect, useState } from "react";
import axios from "axios";

const firebaseConfig = {
  apiKey: import.meta.env.VITE_FIREBASE_API_KEY || "mock-api-key-for-local-dev",
  authDomain: import.meta.env.VITE_FIREBASE_AUTH_DOMAIN || "mock-auth-domain",
  projectId: import.meta.env.VITE_FIREBASE_PROJECT_ID || "adpo-healthcare-agent",
};

// Initialize Firebase
const app = initializeApp(firebaseConfig);
export const auth = getAuth(app);

export interface UserProfile {
  uid: string;
  email: string;
  role: string;
  display_name: string;
}

export function useAuth() {
  const [currentUser, setCurrentUser] = useState<UserProfile | null>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    const useMock = import.meta.env.VITE_USE_MOCK_AUTH === "true";
    if (useMock) {
      const stored = localStorage.getItem("mock_user");
      if (stored) {
        try {
          setCurrentUser(JSON.parse(stored));
        } catch (e) {
          setCurrentUser(null);
        }
      } else {
        setCurrentUser(null);
      }
      setLoading(false);
      return;
    }

    const unsubscribe = onAuthStateChanged(auth, async (firebaseUser) => {
      if (firebaseUser) {
        try {
          const idToken = await firebaseUser.getIdToken();
          const backendUrl = import.meta.env.VITE_API_URL || "http://localhost:8000";
          const res = await axios.post(
            `${backendUrl}/api/v1/auth/session`,
            {},
            {
              headers: {
                Authorization: `Bearer ${idToken}`
              }
            }
          );
          setCurrentUser(res.data);
        } catch (err) {
          console.error("Failed to verify user session with backend:", err);
          setCurrentUser({
            uid: firebaseUser.uid,
            email: firebaseUser.email || "",
            role: "billing_ops",
            display_name: firebaseUser.displayName || firebaseUser.email || "User"
          });
        }
      } else {
        setCurrentUser(null);
      }
      setLoading(false);
    });

    return unsubscribe;
  }, []);

  return { currentUser, loading };
}
