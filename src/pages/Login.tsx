import React, { useState, useEffect } from "react";
import { useNavigate } from "react-router-dom";
import { signInWithEmailAndPassword } from "firebase/auth";
import { auth } from "../lib/auth";

export const Login: React.FC = () => {
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);
  const navigate = useNavigate();

  useEffect(() => {
    document.title = "Log in | Antigravity OTC";
  }, []);

  const handleLogin = async (e: React.FormEvent, customEmail?: string) => {
    if (e) e.preventDefault();
    setError(null);
    setLoading(true);

    const loginEmail = customEmail || email;
    const useMock = import.meta.env.VITE_USE_MOCK_AUTH === "true";

    try {
      if (useMock) {
        const profile = { 
          uid: "mock-uid", 
          email: loginEmail || "admin@hospital.org", 
          role: "admin", 
          display_name: "OTC Administrator" 
        };
        localStorage.setItem("mock_user", JSON.stringify(profile));
        navigate("/orders");
        window.location.reload();
        return;
      }

      const userCredential = await signInWithEmailAndPassword(auth, loginEmail, password);
      const idToken = await userCredential.user.getIdToken();
      
      const backendUrl = import.meta.env.VITE_API_URL || "http://localhost:8000";
      const response = await fetch(`${backendUrl}/api/v1/auth/session`, {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
          "Authorization": `Bearer ${idToken}`
        }
      });

      if (!response.ok) {
        throw new Error("Backend authentication failed to map user role.");
      }

      const userProfile = await response.json();
      const role = userProfile.role;

      if (role === "executive") {
        navigate("/executive");
      } else if (role === "auditor") {
        navigate("/hitl");
      } else {
        navigate("/orders");
      }
    } catch (err: any) {
      console.error(err);
      setError(err.message || "Invalid email or password. Please try again.");
    } finally {
      setLoading(false);
    }
  };

  const handleQuickLogin = (emailAddr: string) => {
    setEmail(emailAddr);
    setPassword("password123");
    handleLogin(null as any, emailAddr);
  };

  return (
    <div style={{
      fontFamily: "'Roboto', -apple-system, BlinkMacSystemFont, 'Segoe UI', Arial, sans-serif",
      color: "#2b2b2b",
      backgroundColor: "#f7f9f8",
      minHeight: "100vh",
      display: "flex",
      flexDirection: "column",
      boxSizing: "border-box",
      borderTop: "4px solid #006039"
    }}>
      {/* Custom Styles Injection */}
      <style dangerouslySetInnerHTML={{__html: `
        @import url('https://fonts.googleapis.com/css2?family=Roboto:wght@300;400;500;700&display=swap');

        .quest-btn-outline {
          border: 2px solid #006039;
          color: #006039;
          background-color: transparent;
          padding: 10px 24px;
          border-radius: 24px;
          font-weight: 700;
          font-size: 13px;
          cursor: pointer;
          text-align: center;
          transition: all 0.2s ease;
          text-decoration: none;
          display: inline-block;
          font-family: 'Roboto', sans-serif;
        }
        .quest-btn-outline:hover {
          background-color: #006039;
          color: white;
        }
        .quest-btn-solid {
          background-color: #006039;
          color: white;
          border: none;
          padding: 12px 24px;
          border-radius: 24px;
          font-weight: 700;
          font-size: 13px;
          cursor: pointer;
          text-align: center;
          transition: background-color 0.2s ease;
          width: 100%;
          font-family: 'Roboto', sans-serif;
        }
        .quest-btn-solid:hover {
          background-color: #004d2e;
        }
        .quest-input {
          width: 100%;
          padding: 10px 12px;
          border: 1px solid #cccccc;
          border-radius: 4px;
          font-size: 14px;
          margin-top: 4px;
          box-sizing: border-box;
          font-family: 'Roboto', sans-serif;
        }
        .quest-input:focus {
          outline: none;
          border-color: #006039;
          box-shadow: 0 0 0 2px rgba(0, 96, 57, 0.15);
        }
        .quest-label {
          font-size: 11px;
          font-weight: 700;
          color: #555555;
          text-transform: uppercase;
          letter-spacing: 0.5px;
          font-family: 'Roboto', sans-serif;
        }
        .quest-footer-link {
          color: #666666;
          text-decoration: none;
          transition: color 0.2s;
        }
        .quest-footer-link:hover {
          color: #006039;
          text-decoration: underline;
        }
      `}} />

      {/* Main Corporate Header (Logo only, clean) */}
      <header style={{
        backgroundColor: "#ffffff",
        borderBottom: "1px solid #e5e8e6",
        padding: "16px 40px",
        display: "flex",
        justifyContent: "center",
        alignItems: "center"
      }}>
        <img 
          src="https://s7d6.scene7.com/is/image/questdiagnostics/Quest-Diagnostics-RGB-gradient?$corp-header-logo$" 
          alt="Quest Diagnostics" 
          style={{ height: "36px", display: "block" }}
        />
      </header>

      {/* Centered Main Area */}
      <main style={{
        display: "flex",
        alignItems: "center",
        justifyContent: "center",
        flex: 1,
        padding: "40px 24px",
        boxSizing: "border-box"
      }}>
        {/* Antigravity OTC Platform Login Card */}
        <div style={{
          backgroundColor: "#ffffff",
          border: "1px solid #e5e8e6",
          borderTop: "4px solid #006039",
          borderRadius: "4px",
          padding: "36px",
          width: "100%",
          maxWidth: "420px",
          boxShadow: "0 4px 16px rgba(0,0,0,0.05)",
          boxSizing: "border-box"
        }}>
          <h1 style={{
            fontSize: "24px",
            fontWeight: 300,
            color: "#2b2b2b",
            margin: "0 0 8px 0",
            letterSpacing: "-0.5px",
            textAlign: "center"
          }}>
            Antigravity OTC Platform
          </h1>
          <p style={{
            fontSize: "13px",
            color: "#666666",
            lineHeight: "1.5",
            margin: "0 0 24px 0",
            textAlign: "center"
          }}>
            Access pre-submission claims risk scoring, audit remediation logs, and executive management dashboards.
          </p>

          {error && (
            <div style={{
              backgroundColor: "#fff0f0",
              color: "#d93838",
              padding: "10px 12px",
              borderRadius: "4px",
              fontSize: "12px",
              marginBottom: "16px",
              border: "1px solid #fcd2d2"
            }}>
              {error}
            </div>
          )}

          <form onSubmit={handleLogin} style={{ display: "flex", flexDirection: "column", gap: "16px" }}>
            <div>
              <label className="quest-label" htmlFor="email">Email address</label>
              <input
                className="quest-input"
                id="email"
                type="email"
                required
                value={email}
                onChange={(e) => setEmail(e.target.value)}
                placeholder="name@hospital.org"
              />
            </div>
            <div>
              <label className="quest-label" htmlFor="password">Password</label>
              <input
                className="quest-input"
                id="password"
                type="password"
                required
                value={password}
                onChange={(e) => setPassword(e.target.value)}
                placeholder="••••••••"
              />
            </div>
            <button 
              className="quest-btn-solid" 
              type="submit" 
              disabled={loading}
              style={{ marginTop: "8px", padding: "12px 24px" }}
            >
              {loading ? "Signing in..." : "Sign in"}
            </button>
          </form>

          <div style={{ borderTop: "1px solid #eeeeee", marginTop: "24px", paddingTop: "16px" }}>
            <button 
              onClick={() => handleQuickLogin("admin@hospital.org")} 
              className="quest-btn-outline"
              style={{ width: "100%", padding: "10px 24px" }}
            >
              All-Access Quick Login
            </button>
          </div>
        </div>
      </main>

      {/* Corporate Footer */}
      <footer style={{
        backgroundColor: "#ffffff",
        borderTop: "1px solid #e5e8e6",
        padding: "20px 40px",
        fontSize: "12px",
        color: "#666666",
        marginTop: "auto"
      }}>
        <div style={{ maxWidth: "1200px", margin: "0 auto", display: "flex", justifyContent: "space-between", flexWrap: "wrap", gap: "16px" }}>
          <div style={{ display: "flex", gap: "16px" }}>
            <a href="https://www.questdiagnostics.com/about/privacy-policy" target="_blank" rel="noreferrer" className="quest-footer-link">Privacy Policy</a>
            <span>|</span>
            <a href="https://www.questdiagnostics.com/about/terms-of-use" target="_blank" rel="noreferrer" className="quest-footer-link">Terms of Use</a>
            <span>|</span>
            <a href="https://www.questdiagnostics.com/contact-us" target="_blank" rel="noreferrer" className="quest-footer-link">Contact us</a>
          </div>
          <div>
            © {new Date().getFullYear()} Quest Diagnostics Incorporated. All rights reserved. Antigravity OTC Simulation Portal.
          </div>
        </div>
      </footer>
    </div>
  );
};

export default Login;
