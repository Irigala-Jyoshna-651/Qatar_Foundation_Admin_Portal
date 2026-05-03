from datetime import datetime, timezone

from flask_login import UserMixin
from flask_sqlalchemy import SQLAlchemy


db = SQLAlchemy()


class Admin(UserMixin, db.Model):
    id = db.Column(db.Integer, primary_key=True)
    full_name = db.Column(db.String(100), nullable=False)
    email = db.Column(db.String(120), unique=True, nullable=False, index=True)
    password_hash = db.Column(db.String(255), nullable=False)
    created_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc), nullable=False)

    opportunities = db.relationship(
        "Opportunity",
        backref="admin",
        lazy=True,
        cascade="all, delete-orphan",
    )


class Opportunity(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(150), nullable=False)
    duration = db.Column(db.String(100), nullable=False)
    start_date = db.Column(db.String(30), nullable=False)
    description = db.Column(db.Text, nullable=False)
    skills = db.Column(db.Text, nullable=False)
    category = db.Column(db.String(50), nullable=False)
    future_opportunities = db.Column(db.Text, nullable=False)
    max_applicants = db.Column(db.Integer, nullable=True)
    created_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc), nullable=False)
    updated_at = db.Column(
        db.DateTime,
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc),
        nullable=False,
    )

    admin_id = db.Column(db.Integer, db.ForeignKey("admin.id"), nullable=False, index=True)

    def to_dict(self):
        skill_list = [skill.strip() for skill in self.skills.split(",") if skill.strip()]
        return {
            "id": self.id,
            "name": self.name,
            "duration": self.duration,
            "start_date": self.start_date,
            "description": self.description,
            "skills": skill_list,
            "skills_text": self.skills,
            "category": self.category,
            "category_value": category_to_value(self.category),
            "future_opportunities": self.future_opportunities,
            "max_applicants": self.max_applicants,
        }


class PasswordResetToken(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    token = db.Column(db.String(128), unique=True, nullable=False, index=True)
    admin_id = db.Column(db.Integer, db.ForeignKey("admin.id"), nullable=False, index=True)
    expires_at = db.Column(db.DateTime, nullable=False)
    used = db.Column(db.Boolean, default=False, nullable=False)
    created_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc), nullable=False)

    admin = db.relationship("Admin", backref="password_reset_tokens")


def category_to_value(category):
    mapping = {
        "Technology": "technology",
        "Business": "business",
        "Design": "design",
        "Marketing": "marketing",
        "Data Science": "data",
        "Other": "other",
    }
    return mapping.get(category, "")
