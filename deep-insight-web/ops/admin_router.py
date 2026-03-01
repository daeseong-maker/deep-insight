"""
Admin Router — FastAPI APIRouter for /admin/* routes.

Provides authentication (Cognito) and job monitoring API for the admin dashboard.
All routes are prefixed with /admin. Protected routes use require_admin dependency.
"""

import logging
import os
from pathlib import Path

import boto3
from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import FileResponse, HTMLResponse, JSONResponse, RedirectResponse
from pydantic import BaseModel

from ops.auth import require_admin

logger = logging.getLogger(__name__)

AWS_REGION = os.environ.get("AWS_REGION", "us-west-2")
COGNITO_USER_POOL_ID = os.environ.get("COGNITO_USER_POOL_ID", "")
COGNITO_CLIENT_ID = os.environ.get("COGNITO_CLIENT_ID", "")
DYNAMODB_TABLE_NAME = os.environ.get("DYNAMODB_TABLE_NAME", "")

OPS_STATIC_DIR = Path(__file__).resolve().parent / "static"

admin_router = APIRouter(prefix="/admin")

_ADMIN_STATIC_EXT = {".js", ".css"}


@admin_router.get("/static/{filename}")
def admin_static(filename: str):
    """Serve admin static assets (JS, CSS only)."""
    file_path = OPS_STATIC_DIR / filename
    if file_path.suffix.lower() not in _ADMIN_STATIC_EXT:
        raise HTTPException(status_code=404)
    if not file_path.exists() or not file_path.is_file():
        raise HTTPException(status_code=404)
    if not file_path.resolve().is_relative_to(OPS_STATIC_DIR.resolve()):
        raise HTTPException(status_code=404)
    return FileResponse(file_path)


# ---------- Request Models ----------


class LoginRequest(BaseModel):
    username: str
    password: str


class ChangePasswordRequest(BaseModel):
    username: str
    session: str
    new_password: str


# ---------- Cookie Helper ----------

_COOKIE_OPTS = {
    "key": "token",
    "httponly": True,
    "samesite": "Lax",
    "path": "/admin",
    "secure": False,  # Phase 2: True when HTTPS added
    "max_age": 3600,  # 1 hour, matches Cognito token expiry
}


def _set_auth_cookie(response, token: str):
    """Set JWT token as HTTP-only cookie."""
    response.set_cookie(value=token, **_COOKIE_OPTS)


# ---------- Public Routes (no auth) ----------


@admin_router.get("/login", response_class=HTMLResponse)
def login_page():
    """Serve the admin login page."""
    html_path = OPS_STATIC_DIR / "login.html"
    if not html_path.exists():
        return HTMLResponse("<h1>Admin login page not deployed yet</h1>", status_code=503)
    return HTMLResponse(html_path.read_text())


@admin_router.post("/login")
def login(request: LoginRequest):
    """Authenticate via Cognito InitiateAuth."""
    if not COGNITO_USER_POOL_ID or not COGNITO_CLIENT_ID:
        raise HTTPException(status_code=503, detail="Cognito not configured")

    try:
        cognito = boto3.client("cognito-idp", region_name=AWS_REGION)
        result = cognito.initiate_auth(
            ClientId=COGNITO_CLIENT_ID,
            AuthFlow="USER_PASSWORD_AUTH",
            AuthParameters={
                "USERNAME": request.username,
                "PASSWORD": request.password,
            },
        )

        # Check for NEW_PASSWORD_REQUIRED challenge (first login)
        if result.get("ChallengeName") == "NEW_PASSWORD_REQUIRED":
            return JSONResponse({
                "challenge": "NEW_PASSWORD_REQUIRED",
                "session": result["Session"],
                "username": request.username,
            })

        # Successful authentication
        token = result["AuthenticationResult"]["IdToken"]
        response = JSONResponse({"success": True, "redirect": "/admin/dashboard"})
        _set_auth_cookie(response, token)
        return response

    except cognito.exceptions.NotAuthorizedException:
        raise HTTPException(status_code=401, detail="Invalid username or password")
    except cognito.exceptions.UserNotFoundException:
        raise HTTPException(status_code=401, detail="Invalid username or password")
    except Exception as e:
        logger.error(f"Login failed: {e}")
        raise HTTPException(status_code=500, detail="Authentication failed")


@admin_router.post("/change-password")
def change_password(request: ChangePasswordRequest):
    """Handle NEW_PASSWORD_REQUIRED challenge (first login)."""
    if not COGNITO_USER_POOL_ID or not COGNITO_CLIENT_ID:
        raise HTTPException(status_code=503, detail="Cognito not configured")

    try:
        cognito = boto3.client("cognito-idp", region_name=AWS_REGION)
        result = cognito.respond_to_auth_challenge(
            ClientId=COGNITO_CLIENT_ID,
            ChallengeName="NEW_PASSWORD_REQUIRED",
            Session=request.session,
            ChallengeResponses={
                "USERNAME": request.username,
                "NEW_PASSWORD": request.new_password,
            },
        )

        token = result["AuthenticationResult"]["IdToken"]
        response = JSONResponse({"success": True, "redirect": "/admin/dashboard"})
        _set_auth_cookie(response, token)
        return response

    except cognito.exceptions.InvalidPasswordException:
        raise HTTPException(
            status_code=400,
            detail="Password does not meet requirements: min 12 chars, uppercase, lowercase, number, symbol",
        )
    except Exception as e:
        logger.error(f"Change password failed: {e}")
        raise HTTPException(status_code=500, detail="Password change failed")


@admin_router.post("/logout")
def logout():
    """Clear JWT cookie."""
    response = JSONResponse({"success": True})
    response.delete_cookie(key="token", path="/admin")
    return response


# ---------- Protected Routes (require auth) ----------


@admin_router.get("/dashboard", response_class=HTMLResponse)
def dashboard_page(claims: dict = Depends(require_admin)):
    """Serve the admin dashboard page."""
    html_path = OPS_STATIC_DIR / "jobs.html"
    if not html_path.exists():
        return HTMLResponse("<h1>Admin dashboard not deployed yet</h1>", status_code=503)
    return HTMLResponse(html_path.read_text())


@admin_router.get("/dashboard/{job_id}", response_class=HTMLResponse)
def job_detail_page(job_id: str, claims: dict = Depends(require_admin)):
    """Serve the job detail page."""
    html_path = OPS_STATIC_DIR / "job.html"
    if not html_path.exists():
        return HTMLResponse("<h1>Job detail page not deployed yet</h1>", status_code=503)
    return HTMLResponse(html_path.read_text())


@admin_router.get("/api/jobs")
def list_jobs(status: str = "", claims: dict = Depends(require_admin)):
    """Query jobs from DynamoDB. Optional status filter."""
    if not DYNAMODB_TABLE_NAME:
        return {"success": False, "error": "DYNAMODB_TABLE_NAME not configured"}

    try:
        dynamodb = boto3.resource("dynamodb", region_name=AWS_REGION)
        table = dynamodb.Table(DYNAMODB_TABLE_NAME)

        if status:
            # Query StatusStartedIndex GSI with status filter
            response = table.query(
                IndexName="StatusStartedIndex",
                KeyConditionExpression="status = :s",
                ExpressionAttributeValues={":s": status},
                ScanIndexForward=False,  # newest first
            )
        else:
            # Scan all jobs, sorted client-side
            response = table.scan()

        items = response.get("Items", [])

        # Sort by started_at descending (scan results are unsorted)
        items.sort(key=lambda x: x.get("started_at", 0), reverse=True)

        # Convert Decimal to int/float for JSON serialization
        jobs = []
        for item in items:
            job = {}
            for k, v in item.items():
                if hasattr(v, "as_integer_ratio"):
                    job[k] = int(v) if v == int(v) else float(v)
                elif isinstance(v, list):
                    job[k] = [str(i) for i in v]
                else:
                    job[k] = str(v) if not isinstance(v, (str, bool)) else v
            jobs.append(job)

        return {"success": True, "jobs": jobs}

    except Exception as e:
        logger.error(f"List jobs failed: {e}")
        return {"success": False, "error": "Failed to retrieve jobs"}


@admin_router.get("/api/jobs/{job_id}")
def get_job(job_id: str, claims: dict = Depends(require_admin)):
    """Get a single job record from DynamoDB."""
    if not DYNAMODB_TABLE_NAME:
        return {"success": False, "error": "DYNAMODB_TABLE_NAME not configured"}

    try:
        dynamodb = boto3.resource("dynamodb", region_name=AWS_REGION)
        table = dynamodb.Table(DYNAMODB_TABLE_NAME)
        response = table.get_item(Key={"job_id": job_id})
        item = response.get("Item")

        if not item:
            raise HTTPException(status_code=404, detail="Job not found")

        # Convert Decimal to int/float for JSON serialization
        job = {}
        for k, v in item.items():
            if hasattr(v, "as_integer_ratio"):
                job[k] = int(v) if v == int(v) else float(v)
            elif isinstance(v, list):
                job[k] = [str(i) for i in v]
            else:
                job[k] = str(v) if not isinstance(v, (str, bool)) else v

        return {"success": True, "job": job}

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Get job failed: {e}")
        return {"success": False, "error": "Failed to retrieve job"}
