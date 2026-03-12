"""
Database Seed Script
Creates sample school, admin user, teacher, and classroom for local development.
Run with: docker compose exec backend python scripts/seed_db.py

WARNING: Do not run in production. Deletes existing seed data first.
"""
import asyncio
import os
import sys
import secrets

# Add parent directory to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine, async_sessionmaker
from sqlalchemy import text

from core.config import settings
from core.security import hash_password, encrypt_field, hmac_hash_email

engine = create_async_engine(settings.database_url, echo=False)
AsyncSession = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)


async def seed():
    async with AsyncSession() as session:
        print("Seeding database...")

        # Ensure pgvector is installed
        await session.execute(text("CREATE EXTENSION IF NOT EXISTS vector;"))
        await session.commit()

        # Create sample school
        school_id = "11111111-1111-1111-1111-111111111111"
        school_secret = secrets.token_bytes(32)

        await session.execute(text("""
            INSERT INTO schools (id, name, district, state, secret_key, join_code, settings)
            VALUES (:id, :name, :district, :state, :secret_key, :join_code, :settings)
            ON CONFLICT (id) DO NOTHING
        """), {
            "id": school_id,
            "name": "Sample Elementary School",
            "district": "Sample School District",
            "state": "MD",
            "secret_key": school_secret,
            "join_code": "SAMPLE2026",
            "settings": '{"proficiency_threshold": 0.70}',
        })

        # Create school admin
        admin_email = "admin@sampleschool.edu"
        admin_id = "22222222-2222-2222-2222-222222222222"
        await session.execute(text("""
            INSERT INTO users (id, school_id, email, email_hash, password_hash, full_name, role, is_verified)
            VALUES (:id, :school_id, :email, :email_hash, :password_hash, :full_name, :role, TRUE)
            ON CONFLICT (id) DO NOTHING
        """), {
            "id": admin_id,
            "school_id": school_id,
            "email": encrypt_field(admin_email),
            "email_hash": hmac_hash_email(admin_email),
            "password_hash": hash_password("Admin@SecurePass123!"),
            "full_name": encrypt_field("Sample Admin"),
            "role": "school_admin",
        })

        # Create sample teacher
        teacher_email = "teacher@sampleschool.edu"
        teacher_id = "33333333-3333-3333-3333-333333333333"
        await session.execute(text("""
            INSERT INTO users (id, school_id, email, email_hash, password_hash, full_name, role, is_verified)
            VALUES (:id, :school_id, :email, :email_hash, :password_hash, :full_name, :role, TRUE)
            ON CONFLICT (id) DO NOTHING
        """), {
            "id": teacher_id,
            "school_id": school_id,
            "email": encrypt_field(teacher_email),
            "email_hash": hmac_hash_email(teacher_email),
            "password_hash": hash_password("Teacher@SecurePass123!"),
            "full_name": encrypt_field("Sample Teacher"),
            "role": "teacher",
        })

        # Create classroom
        classroom_id = "44444444-4444-4444-4444-444444444444"
        await session.execute(text("""
            INSERT INTO classrooms (id, school_id, teacher_id, name, grade_level, academic_year)
            VALUES (:id, :school_id, :teacher_id, :name, :grade_level, :academic_year)
            ON CONFLICT (id) DO NOTHING
        """), {
            "id": classroom_id,
            "school_id": school_id,
            "teacher_id": teacher_id,
            "name": "3rd Grade - Room 101",
            "grade_level": "3",
            "academic_year": "2025-2026",
        })

        await session.commit()

        print("\n========== SEED COMPLETE ==========")
        print(f"School:    Sample Elementary School")
        print(f"Join Code: SAMPLE2026")
        print(f"\nAdmin login:")
        print(f"  Email:    {admin_email}")
        print(f"  Password: Admin@SecurePass123!")
        print(f"\nTeacher login:")
        print(f"  Email:    {teacher_email}")
        print(f"  Password: Teacher@SecurePass123!")
        print(f"\nClassroom: 3rd Grade - Room 101")
        print("====================================\n")
        print("Next: Upload sample_data/sample_assessment.csv and sample_metadata.csv")
        print("using the teacher account on the Upload page.")


if __name__ == "__main__":
    asyncio.run(seed())
