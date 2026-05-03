import logging
import re
import secrets
from datetime import datetime, timedelta, timezone

from flask import Blueprint, current_app, jsonify, request, url_for
from flask_login import current_user, login_required, login_user, logout_user
from werkzeug.security import check_password_hash, generate_password_hash

from models import Admin, Opportunity, PasswordResetToken, db


bp = Blueprint("routes", __name__)
logger = logging.getLogger(__name__)

EMAIL_RE = re.compile(r"^[^\s@]+@[^\s@]+\.[^\s@]+$")
CATEGORY_MAP = {
    "technology": "Technology",
    "business": "Business",
    "design": "Design",
    "marketing": "Marketing",
    "data": "Data Science",
    "data science": "Data Science",
    "other": "Other",
}


def json_data():
    return request.get_json(silent=True) or request.form.to_dict()


def error(message, status=400):
    return jsonify({"status": "error", "error": message}), status


def validate_email(email):
    return bool(email and EMAIL_RE.match(email))


@bp.route("/api/signup", methods=["POST"])
def signup():
    data = json_data()
    full_name = (data.get("full_name") or data.get("name") or "").strip()
    email = (data.get("email") or "").strip().lower()
    password = data.get("password") or ""
    confirm_password = data.get("confirm_password") or data.get("confirmPassword") or ""

    if not full_name or not email or not password or not confirm_password:
        return error("All fields are required")
    if not validate_email(email):
        return error("Please enter a valid email address")
    if len(password) < 8:
        return error("Password must be at least 8 characters")
    if password != confirm_password:
        return error("Passwords do not match")
    if Admin.query.filter_by(email=email).first():
        return error("Account already exists", 409)

    admin = Admin(
        full_name=full_name,
        email=email,
        password_hash=generate_password_hash(password),
    )
    db.session.add(admin)
    db.session.commit()

    return jsonify({"status": "success", "message": "Account created successfully"}), 201


@bp.route("/api/login", methods=["POST"])
def login():
    data = json_data()
    email = (data.get("email") or "").strip().lower()
    password = data.get("password") or ""
    remember = bool(data.get("remember"))

    admin = Admin.query.filter_by(email=email).first()
    if not admin or not check_password_hash(admin.password_hash, password):
        return error("Invalid email or password", 401)

    login_user(admin, remember=remember)
    return jsonify(
        {
            "status": "success",
            "message": "Login successful",
            "admin": {"id": admin.id, "full_name": admin.full_name, "email": admin.email},
        }
    )


@bp.route("/api/logout", methods=["POST"])
@login_required
def logout():
    logout_user()
    return jsonify({"status": "success", "message": "Signed out successfully"})


@bp.route("/api/me", methods=["GET"])
def me():
    if not current_user.is_authenticated:
        return error("Authentication required", 401)
    return jsonify(
        {
            "status": "success",
            "admin": {
                "id": current_user.id,
                "full_name": current_user.full_name,
                "email": current_user.email,
            },
        }
    )


@bp.route("/api/forgot-password", methods=["POST"])
def forgot_password():
    data = json_data()
    email = (data.get("email") or "").strip().lower()
    admin = Admin.query.filter_by(email=email).first() if validate_email(email) else None

    if admin:
        token = secrets.token_urlsafe(32)
        reset = PasswordResetToken(
            token=token,
            admin_id=admin.id,
            expires_at=datetime.now(timezone.utc) + timedelta(hours=1),
        )
        db.session.add(reset)
        db.session.commit()
        reset_link = url_for("routes.check_reset_token", token=token, _external=True)
        logger.warning("Password reset link for %s: %s", admin.email, reset_link)
        current_app.logger.warning("Password reset link for %s: %s", admin.email, reset_link)

    return jsonify(
        {
            "status": "success",
            "message": "If an account exists for that email, a reset link has been generated.",
        }
    )


@bp.route("/reset-password/<token>", methods=["GET"])
def check_reset_token(token):
    reset = PasswordResetToken.query.filter_by(token=token, used=False).first()
    now = datetime.now(timezone.utc)
    if not reset:
        return "Invalid or already used reset link.", 400
    expires_at = reset.expires_at
    if expires_at.tzinfo is None:
        expires_at = expires_at.replace(tzinfo=timezone.utc)
    if expires_at < now:
        return "This reset link has expired. Please request a new one.", 400
    return "Reset link is valid. Password update UI is not required for this stage.", 200


def normalize_opportunity_payload(data):
    name = (data.get("name") or data.get("title") or "").strip()
    duration = (data.get("duration") or "").strip()
    start_date = (data.get("start_date") or data.get("startDate") or "").strip()
    description = (data.get("description") or "").strip()
    skills_value = data.get("skills") or data.get("skills_text") or data.get("skillsText") or ""
    if isinstance(skills_value, list):
        skills = ", ".join(str(skill).strip() for skill in skills_value if str(skill).strip())
    else:
        skills = ", ".join(skill.strip() for skill in str(skills_value).split(",") if skill.strip())
    raw_category = str(data.get("category") or "").strip()
    category = CATEGORY_MAP.get(raw_category.lower())
    future_opportunities = (
        data.get("future_opportunities") or data.get("futureOpportunities") or ""
    ).strip()
    raw_max = data.get("max_applicants") or data.get("maxApplicants") or None

    if not name or not duration or not start_date or not description or not skills or not category or not future_opportunities:
        return None, "Please fill all required fields"

    max_applicants = None
    if raw_max not in (None, ""):
        try:
            max_applicants = int(raw_max)
        except (TypeError, ValueError):
            return None, "Maximum Applicants must be a number"
        if max_applicants < 0:
            return None, "Maximum Applicants must be zero or greater"

    return {
        "name": name,
        "duration": duration,
        "start_date": start_date,
        "description": description,
        "skills": skills,
        "category": category,
        "future_opportunities": future_opportunities,
        "max_applicants": max_applicants,
    }, None


@bp.route("/api/opportunities", methods=["GET"])
@login_required
def list_opportunities():
    opportunities = (
        Opportunity.query.filter_by(admin_id=current_user.id)
        .order_by(Opportunity.created_at.desc())
        .all()
    )
    return jsonify({"status": "success", "data": [op.to_dict() for op in opportunities]})


@bp.route("/api/opportunities", methods=["POST"])
@login_required
def create_opportunity():
    payload, validation_error = normalize_opportunity_payload(json_data())
    if validation_error:
        return error(validation_error)

    opportunity = Opportunity(**payload, admin_id=current_user.id)
    db.session.add(opportunity)
    db.session.commit()
    return jsonify({"status": "success", "data": opportunity.to_dict()}), 201


@bp.route("/api/opportunities/<int:opportunity_id>", methods=["GET"])
@login_required
def get_opportunity(opportunity_id):
    opportunity = Opportunity.query.filter_by(id=opportunity_id, admin_id=current_user.id).first()
    if not opportunity:
        return error("Opportunity not found", 404)
    return jsonify({"status": "success", "data": opportunity.to_dict()})


@bp.route("/api/opportunities/<int:opportunity_id>", methods=["PUT", "POST"])
@login_required
def update_opportunity(opportunity_id):
    opportunity = Opportunity.query.filter_by(id=opportunity_id, admin_id=current_user.id).first()
    if not opportunity:
        return error("Opportunity not found", 404)

    payload, validation_error = normalize_opportunity_payload(json_data())
    if validation_error:
        return error(validation_error)

    for key, value in payload.items():
        setattr(opportunity, key, value)
    db.session.commit()
    return jsonify({"status": "success", "data": opportunity.to_dict()})


@bp.route("/api/opportunities/<int:opportunity_id>", methods=["DELETE"])
@login_required
def delete_opportunity(opportunity_id):
    opportunity = Opportunity.query.filter_by(id=opportunity_id, admin_id=current_user.id).first()
    if not opportunity:
        return error("Opportunity not found", 404)

    db.session.delete(opportunity)
    db.session.commit()
    return jsonify({"status": "success", "message": "Opportunity deleted successfully"})
