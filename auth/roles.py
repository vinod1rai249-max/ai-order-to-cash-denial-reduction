# Define system roles and access lists

ROLE_BILLING_OPS = "billing_ops"
ROLE_AUDITOR = "auditor"
ROLE_EXECUTIVE = "executive"
ROLE_ADMIN = "admin"

ALL_ROLES = [ROLE_BILLING_OPS, ROLE_AUDITOR, ROLE_EXECUTIVE, ROLE_ADMIN]

# Gating mappings for screen permissions (used as server-side route guards)
ROLE_PERMISSIONS = {
    ROLE_BILLING_OPS: ["/orders", "/remediation", "/billing"],
    ROLE_AUDITOR: ["/orders", "/remediation", "/billing", "/hitl"],
    ROLE_EXECUTIVE: ["/executive"],
    ROLE_ADMIN: ["/orders", "/remediation", "/billing", "/hitl", "/executive", "/admin"]
}

def has_permission(role: str, path: str) -> bool:
    """Checks if a role is permitted to access a given UI path or backend action path."""
    if role == ROLE_ADMIN:
        return True
    
    allowed_paths = ROLE_PERMISSIONS.get(role, [])
    # Check prefixes to support dynamic sub-paths like /orders/123
    for allowed in allowed_paths:
        if path.startswith(allowed):
            return True
            
    return False
