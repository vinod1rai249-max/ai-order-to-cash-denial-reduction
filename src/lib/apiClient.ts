import axios from "axios";
import { auth } from "./auth";

const apiClient = axios.create({
  baseURL: import.meta.env.VITE_API_URL || "http://localhost:8000",
});

// Interceptor to attach Bearer Authorization token automatically
apiClient.interceptors.request.use(
  async (config) => {
    const useMock = import.meta.env.VITE_USE_MOCK_AUTH === "true";
    if (useMock) {
      const stored = localStorage.getItem("mock_user");
      if (stored) {
        try {
          const mockUser = JSON.parse(stored);
          config.headers.Authorization = `Bearer mock-token-${mockUser.role}`;
        } catch (e) {}
      }
      return config;
    }

    const user = auth.currentUser;
    if (user) {
      try {
        const idToken = await user.getIdToken();
        config.headers.Authorization = `Bearer ${idToken}`;
      } catch (err) {
        console.error("Error retrieving Firebase ID token:", err);
      }
    }
    return config;
  },
  (error) => {
    return Promise.reject(error);
  }
);

// Interceptor to extract X-Trace-ID for debugging and audit logs
apiClient.interceptors.response.use(
  (response) => {
    const traceId = response.headers["x-trace-id"];
    if (traceId) {
      // Store in session storage or attach to response body for components to display
      (response.data as any).trace_id = traceId;
    }
    return response;
  },
  (error) => {
    const traceId = error.response?.headers["x-trace-id"];
    if (traceId && error.response?.data) {
      error.response.data.trace_id = traceId;
    }
    return Promise.reject(error);
  }
);

export default apiClient;
