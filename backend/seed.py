"""Seed initial doctors."""
from __future__ import annotations

from models import Doctor, new_id


DEFAULT_DOCTORS = [
    dict(
        name="Dr. Aneeta Rao",
        specialty="Gynecology",
        bio="12 years in women's health, pregnancy care, menstrual disorders.",
        room="204",
        fee=700,
        availability="Tue, Thu, Sat · 10:00 AM – 1:00 PM",
        picture="https://images.pexels.com/photos/5327585/pexels-photo-5327585.jpeg?auto=compress&cs=tinysrgb&w=400",
    ),
    dict(
        name="Dr. Sameer Kulkarni",
        specialty="Cardiology",
        bio="18 years managing heart disease, hypertension, cholesterol.",
        room="308",
        fee=1000,
        availability="Mon, Wed, Fri · 2:00 PM – 6:00 PM",
        picture="https://images.pexels.com/photos/8460157/pexels-photo-8460157.jpeg?auto=compress&cs=tinysrgb&w=400",
    ),
    dict(
        name="Dr. Neha Sharma",
        specialty="Dermatology",
        bio="Skin, hair, acne, allergic disorders, cosmetic dermatology.",
        room="205",
        fee=600,
        availability="Mon – Fri · 10:00 AM – 4:00 PM",
        picture="https://images.pexels.com/photos/4989148/pexels-photo-4989148.jpeg?auto=compress&cs=tinysrgb&w=400",
    ),
    dict(
        name="Dr. Ravi Iyer",
        specialty="Pediatrics",
        bio="15 years in child nutrition, vaccinations, growth monitoring.",
        room="102",
        fee=500,
        availability="Mon – Sat · 9:30 AM – 1:30 PM",
        picture="https://images.pexels.com/photos/6234600/pexels-photo-6234600.jpeg?auto=compress&cs=tinysrgb&w=400",
    ),
    dict(
        name="Dr. Priya Menon",
        specialty="ENT",
        bio="Sinusitis, ear infections, tonsils, hearing tests.",
        room="203",
        fee=650,
        availability="Tue, Wed, Fri · 11:00 AM – 3:00 PM",
        picture="https://images.pexels.com/photos/5214999/pexels-photo-5214999.jpeg?auto=compress&cs=tinysrgb&w=400",
    ),
    dict(
        name="Dr. Arvind Deshmukh",
        specialty="General Medicine",
        bio="Primary care, diabetes, hypertension, seasonal infections.",
        room="101",
        fee=500,
        availability="Mon – Sat · 9:00 AM – 12:00 PM, 4:00 PM – 6:00 PM",
        picture="https://images.pexels.com/photos/4173251/pexels-photo-4173251.jpeg?auto=compress&cs=tinysrgb&w=400",
    ),
]


async def seed_doctors(db):
    existing = await db.doctors.count_documents({})
    if existing > 0:
        return existing
    for spec in DEFAULT_DOCTORS:
        doc = Doctor(doctor_id=new_id("doc"), **spec).model_dump()
        await db.doctors.insert_one(doc)
    return len(DEFAULT_DOCTORS)
