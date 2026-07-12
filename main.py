import re
import os
import json
import logging
from dotenv import load_dotenv
load_dotenv()
from fastapi import FastAPI, Request, Response
from fastapi.middleware.cors import CORSMiddleware
from starlette.middleware.base import BaseHTTPMiddleware

# Import routes
from gateway.v4_routes import router as v4_router
from governance.governance_logger import init_governance_sink

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = FastAPI(
    title="Order-to-Cash Denial Reduction & Remediation Gateway",
    version="4.0",
    description="Pre-submission Risk Scoring, Reason Detection, and Auto-Remediation Orchestrator"
)

# CORS Policy
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# 1. DLP (Data Loss Prevention) Masking Middleware
# Redacts patterns resembling SSN (XXX-XX-XXXX) or email from responses
SSN_REGEX = re.compile(r"\b\d{3}-\d{2}-\d{4}\b")
EMAIL_REGEX = re.compile(r"\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,7}\b")

class DLPMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next) -> Response:
        response = await call_next(request)
        
        # Only inspect and mask json content types
        content_type = response.headers.get("content-type", "")
        if "application/json" in content_type:
            # We buffer the response body
            body_bytes = b""
            async for chunk in response.body_iterator:
                body_bytes += chunk
                
            body_str = body_bytes.decode("utf-8")
            
            # Apply redactions
            redacted_str = SSN_REGEX.sub("[REDACTED_SSN]", body_str)
            redacted_str = EMAIL_REGEX.sub("[REDACTED_EMAIL]", redacted_str)
            
            # Reconstruct response
            response.headers["Content-Length"] = str(len(redacted_str))
            return Response(
                content=redacted_str,
                status_code=response.status_code,
                headers=dict(response.headers),
                media_type="application/json"
            )
            
        return response

app.add_middleware(DLPMiddleware)

# 2. Trace ID Middleware
class TraceIDMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next) -> Response:
        # Check if trace ID exists in request headers or generate one
        trace_id = request.headers.get("X-Trace-ID") or f"TRC-GATE-{int(os.getpid())}-{int(time_nano())}"
        
        # Inject trace ID into request state for downstream handlers
        request.state.trace_id = trace_id
        
        response = await call_next(request)
        
        # Attach trace ID to response headers
        response.headers["X-Trace-ID"] = trace_id
        return response

import time
def time_nano() -> int:
    return int(time.time() * 1e9)

app.add_middleware(TraceIDMiddleware)

# Mount endpoints
app.include_router(v4_router)

@app.on_event("startup")
def startup_event():
    logger.info("Gateway starting up. Verifying governance sinks...")
    init_governance_sink()

@app.get("/")
def health_check():
    return {
        "status": "healthy",
        "service": "order_to_cash_denial_reduction_gateway",
        "version": "4.0"
    }
