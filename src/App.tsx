import React from "react";
import { 
  BrowserRouter as Router, 
  Routes, 
  Route, 
  Link, 
  Navigate, 
  useLocation 
} from "react-router-dom";
import { useAuth } from "./lib/auth";
import { Login } from "./pages/Login";
import { OrderEntry } from "./pages/OrderEntry";
import { RemediationTimeline } from "./pages/RemediationTimeline";
import { ReviewQueue } from "./pages/ReviewQueue";
import { ManagerDashboard } from "./pages/ManagerDashboard";
import { auth } from "./lib/auth";
import { signOut } from "firebase/auth";

// Sidebar Layout Wrapper for Authenticated Screens
const DashboardLayout: React.FC<{ children: React.ReactNode }> = ({ children }) => {
  const { currentUser } = useAuth();
  const location = useLocation();
  
  const handleLogout = () => {
    if (import.meta.env.VITE_USE_MOCK_AUTH === "true") {
      localStorage.removeItem("mock_user");
      window.location.reload();
      return;
    }
    signOut(auth);
  };

  const isActive = (path: string) => location.pathname === path;

  // Filter links by role permissions
  const role = currentUser?.role || "billing_ops";
  const showLink = (path: string) => {
    if (role === "admin") return true;
    if (role === "executive") return path === "/executive";
    if (role === "auditor") return ["/orders", "/remediation", "/hitl"].includes(path);
    if (role === "billing_ops") return ["/orders", "/remediation"].includes(path);
    return false;
  };

  return (
    <div className="app-container">
      <aside className="sidebar">
        <div className="sidebar-title">Quest Smart OTC</div>
        
        <nav style={{ flex: 1 }}>
          <ul className="nav-links">
            {showLink("/orders") && (
              <li>
                <Link to="/orders" className={`nav-item ${isActive("/orders") ? "active" : ""}`}>
                  Order Intake
                </Link>
              </li>
            )}
            {showLink("/remediation") && (
              <li>
                <Link to="/remediation" className={`nav-item ${isActive("/remediation") ? "active" : ""}`}>
                  Audit Trail
                </Link>
              </li>
            )}
            {showLink("/hitl") && (
              <li>
                <Link to="/hitl" className={`nav-item ${isActive("/hitl") ? "active" : ""}`}>
                  HITL Queue
                </Link>
              </li>
            )}
            {showLink("/executive") && (
              <li>
                <Link to="/executive" className={`nav-item ${isActive("/executive") ? "active" : ""}`}>
                  Executive Dashboard
                </Link>
              </li>
            )}
          </ul>
        </nav>
        
        <div style={{ borderTop: "0.5px solid var(--border-color)", paddingTop: "16px", marginTop: "auto" }}>
          <div style={{ fontSize: "13px", fontWeight: 600, color: "var(--text-main)", marginBottom: "4px" }}>
            {currentUser?.display_name}
          </div>
          <div style={{ fontSize: "11px", color: "var(--text-muted)", textTransform: "uppercase", marginBottom: "16px" }}>
            Role: {role}
          </div>
          <button 
            className="btn btn-secondary" 
            onClick={handleLogout}
            style={{ width: "100%", padding: "8px", fontSize: "13px", justifyContent: "center" }}
          >
            Sign Out
          </button>
        </div>
      </aside>
      
      <main className="main-content">
        {children}
      </main>
    </div>
  );
};

// Route Guard to verify Authentication and Roles
const ProtectedRoute: React.FC<{ children: React.ReactNode, allowedRoles: string[] }> = ({ 
  children, 
  allowedRoles 
}) => {
  const { currentUser, loading } = useAuth();

  if (loading) {
    return (
      <div style={{ display: "flex", alignItems: "center", justifyContent: "center", minHeight: "100vh", backgroundColor: "var(--bg-primary)" }}>
        <div style={{ fontSize: "14px", color: "var(--text-muted)", fontWeight: 500 }}>
          Verifying security session...
        </div>
      </div>
    );
  }

  if (!currentUser) {
    return <Navigate to="/login" replace />;
  }

  const role = currentUser.role;
  if (!allowedRoles.includes(role) && role !== "admin") {
    // Redirect unauthorized roles to their default permitted pages
    if (role === "executive") return <Navigate to="/executive" replace />;
    if (role === "auditor") return <Navigate to="/hitl" replace />;
    return <Navigate to="/orders" replace />;
  }

  return <DashboardLayout>{children}</DashboardLayout>;
};

export const App: React.FC = () => {
  return (
    <Router>
      <Routes>
        <Route path="/login" element={<Login />} />
        
        <Route 
          path="/orders" 
          element={
            <ProtectedRoute allowedRoles={["billing_ops", "auditor"]}>
              <OrderEntry />
            </ProtectedRoute>
          } 
        />
        
        <Route 
          path="/remediation" 
          element={
            <ProtectedRoute allowedRoles={["billing_ops", "auditor"]}>
              <RemediationTimeline />
            </ProtectedRoute>
          } 
        />
        
        <Route 
          path="/hitl" 
          element={
            <ProtectedRoute allowedRoles={["auditor"]}>
              <ReviewQueue />
            </ProtectedRoute>
          } 
        />
        
        <Route 
          path="/executive" 
          element={
            <ProtectedRoute allowedRoles={["executive"]}>
              <ManagerDashboard />
            </ProtectedRoute>
          } 
        />
        
        <Route path="*" element={<Navigate to="/orders" replace />} />
      </Routes>
    </Router>
  );
};

export default App;
