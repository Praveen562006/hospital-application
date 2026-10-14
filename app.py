import os
import sqlite3
import hashlib
from datetime import datetime, date, time, timedelta, timezone
from functools import wraps

from flask import (
    Flask,
    render_template,
    request,
    redirect,
    url_for,
    session,
    flash,
    jsonify,
    abort
)

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DB_PATH = os.path.join(BASE_DIR, "instance", "hospital.db")

# ============================================================
# APPOINTMENT CONFIGURATION
# ============================================================
SLOT_MINUTES = 30
OPEN_TIME = time(9, 0)
CLOSE_TIME = time(17, 0)
BOOKING_DAYS = 30
WORKING_DAYS = {0, 1, 2, 3, 4, 5}  # Monday (0) - Saturday (5)

# ============================================================
# DOCTOR DIRECTORY (rich profiles)
# ============================================================
DOCTOR_PROFILES = {
    "Walter White": {"qualification": "MBBS, MD Cardiology", "experience": 16, "languages": "English, Hindi", "fee": 800, "rating": 4.9, "bio": "Senior interventional cardiologist specialising in preventive cardiology, angioplasty and heart-failure management with 16+ years of clinical leadership."},
    "Sarah Jhonson": {"qualification": "MBBS, DM Neurology", "experience": 12, "languages": "English, Tamil", "fee": 750, "rating": 4.8, "bio": "Neurologist focused on migraine, epilepsy, stroke recovery and movement disorders. Known for clear explanations and patient-first care plans."},
    "William Anderson": {"qualification": "MBBS, DM Gastroenterology", "experience": 14, "languages": "English, Hindi, Telugu", "fee": 700, "rating": 4.8, "bio": "Hepatology and liver-care specialist treating fatty liver, hepatitis, cirrhosis and digestive disorders with modern endoscopic care."},
    "Amanda Jepson": {"qualification": "MBBS, MD Pediatrics", "experience": 10, "languages": "English, Hindi", "fee": 500, "rating": 4.9, "bio": "Paediatrician loved by families for newborn care, vaccinations, growth tracking and friendly, unhurried consultations."},
    "Michael Brown": {"qualification": "MBBS, MS Ophthalmology", "experience": 11, "languages": "English, Hindi, Kannada", "fee": 600, "rating": 4.7, "bio": "Eye-care surgeon offering cataract, LASIK evaluation, glaucoma screening and complete vision care for all ages."},
    "Kristin Miller": {"qualification": "MBBS, MS Orthopedics", "experience": 13, "languages": "English, Hindi", "fee": 650, "rating": 4.8, "bio": "Orthopedic surgeon specialising in joint pain, sports injuries, fractures and arthritis with rehab-focused recovery plans."},
    "Ananya Sharma": {"qualification": "MBBS, MD Cardiology", "experience": 9, "languages": "English, Hindi, Marathi", "fee": 700, "rating": 4.9, "bio": "Cardiologist with focus on women's heart health, hypertension and cholesterol management through lifestyle + medication."},
    "Rajesh Kumar": {"qualification": "MBBS, DM Cardiology", "experience": 18, "languages": "English, Hindi, Tamil", "fee": 900, "rating": 4.9, "bio": "Veteran cardiologist for complex coronary disease, pacemakers and post-bypass rehabilitation and second opinions."},
    "Priya Nair": {"qualification": "MBBS, DM Neurology", "experience": 8, "languages": "English, Malayalam, Hindi", "fee": 700, "rating": 4.8, "bio": "Neurologist specialising in headaches, vertigo, neuropathy and sleep disorders with emphasis on early diagnosis."},
    "Arjun Mehta": {"qualification": "MBBS, MCh Neurosurgery", "experience": 15, "languages": "English, Hindi, Gujarati", "fee": 950, "rating": 4.7, "bio": "Neurosurgeon for spine pain, slipped disc, sciatica and minimally invasive spine procedures."},
    "Kavya Reddy": {"qualification": "MBBS, MD Pediatrics", "experience": 7, "languages": "English, Telugu, Hindi", "fee": 500, "rating": 4.9, "bio": "Paediatrician focused on infant nutrition, developmental milestones, asthma and childhood immunisation."},
    "Vikram Singh": {"qualification": "MBBS, MS Orthopedics", "experience": 12, "languages": "English, Hindi, Punjabi", "fee": 650, "rating": 4.7, "bio": "Sports-medicine orthopedist for knee, shoulder and ligament injuries trusted by athletes and fitness enthusiasts."},
    "Sneha Patel": {"qualification": "MBBS, MS Ophthalmology", "experience": 9, "languages": "English, Hindi, Gujarati", "fee": 550, "rating": 4.8, "bio": "Eye specialist for dry eye, diabetic retinopathy screening, paediatric vision and contact-lens care."},
    "Deepak Rao": {"qualification": "MBBS, DM Gastroenterology", "experience": 11, "languages": "English, Telugu, Kannada", "fee": 700, "rating": 4.7, "bio": "Gastro and liver physician for acidity, IBS, ulcers and liver screening with diet-led treatment plans."},
    "Meera Iyer": {"qualification": "MBBS, DGO, MD Obstetrics", "experience": 13, "languages": "English, Tamil, Hindi", "fee": 750, "rating": 4.9, "bio": "Women's health and high-risk pregnancy specialist offering antenatal care, PCOS and fertility guidance."},
    "Sanjay Gupta": {"qualification": "MBBS, MD Dermatology", "experience": 10, "languages": "English, Hindi", "fee": 600, "rating": 4.8, "bio": "Dermatologist for acne, eczema, hair loss, psoriasis and cosmetic skin consultations with evidence-based care."},
    "Lakshmi Venkat": {"qualification": "MBBS, MD General Medicine", "experience": 14, "languages": "English, Tamil, Telugu", "fee": 550, "rating": 4.8, "bio": "General physician for diabetes, thyroid, infections and full-body health checks. Your first stop for any symptom."},
    "Rahul Verma": {"qualification": "MBBS, MS Orthopedics", "experience": 8, "languages": "English, Hindi", "fee": 600, "rating": 4.6, "bio": "Joint-replacement and arthritis specialist focused on pain-free mobility and physiotherapy-led recovery."},
}

DEPARTMENT_INFO = {
    "Cardiology": "Heart, blood pressure, cholesterol and cardiac prevention care.",
    "Neurology": "Brain, spine, nerve, migraine, stroke and sleep care.",
    "Hepatology": "Liver, gallbladder, digestive and metabolic care.",
    "Pediatrics": "Newborn, child growth, vaccination and development care.",
    "Eye Care": "Vision testing, cataract, glaucoma and complete eye health.",
    "Orthopedics": "Bones, joints, spine, sports injuries and arthritis care.",
}

SEED_REVIEWS = [
    ("Karthik R.", 5, "Quick booking, zero waiting", "Booked Dr. Walter White for my father's chest pain. Slot was confirmed instantly and the doctor was thorough. Best hospital experience we've had.", None),
    ("Divya S.", 5, "Caring pediatrician", "Dr. Amanda Jepson is wonderful with kids. My daughter actually looks forward to checkups now. Vaccination tracking is seamless.", None),
    ("Mohammed F.", 4, "Good eye checkup", "Complete eye examination in 30 minutes with clear prescription. Billing was transparent and the staff guided payment well.", None),
    ("Anitha K.", 5, "Migraine finally under control", "After years of headaches, Dr. Sarah Jhonson found the trigger in one visit. Online payment and instant receipt made it easy.", None),
    ("Ravi Teja", 5, "Knee pain relief", "Dr. Vikram Singh explained my MRI patiently and avoided surgery with physio. Honest advice — highly recommended.", None),
    ("Sowmya P.", 5, "Clean, professional clinic", "From reception to consultation everything felt organised. Booking online saved at least an hour of waiting.", None),
]
CONSULTATION_FEE = 500
CURRENCY = "INR"
CURRENCY_SYMBOL = "₹"
PAYMENT_HOLD_MINUTES = 10  # unpaid bookings are released after this
TEST_DECLINE_CARD = "4000000000000002"  # demo card that always declines

app = Flask(__name__)
app.secret_key = os.environ.get("SECRET_KEY", "psmhealthcare-secure-hospital-key-2026")
app.config["JSON_SORT_KEYS"] = False
app.url_map.strict_slashes = False


# ============================================================
# DATABASE HELPERS
# ============================================================
def db():
    os.makedirs(os.path.dirname(DB_PATH), exist_ok=True)
    connection = sqlite3.connect(DB_PATH)
    connection.row_factory = sqlite3.Row
    connection.execute("PRAGMA foreign_keys = ON")
    return connection


def hash_password(password):
    return hashlib.sha512(password.encode("utf-8")).hexdigest()


def init_db():
    os.makedirs(os.path.dirname(DB_PATH), exist_ok=True)
    connection = db()
    connection.executescript("""
        CREATE TABLE IF NOT EXISTS admins (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            username TEXT NOT NULL UNIQUE,
            password_hash TEXT NOT NULL
        );

        CREATE TABLE IF NOT EXISTS branches (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL UNIQUE
        );

        CREATE TABLE IF NOT EXISTS doctors (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            branch_id INTEGER NOT NULL,
            FOREIGN KEY(branch_id) REFERENCES branches(id) ON DELETE CASCADE
        );

        CREATE TABLE IF NOT EXISTS patients (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            username TEXT NOT NULL UNIQUE,
            password_hash TEXT NOT NULL
        );

        CREATE TABLE IF NOT EXISTS appointments (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            appointment_time TEXT NOT NULL,
            doctor_id INTEGER NOT NULL,
            patient_id INTEGER NOT NULL,
            created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
            status TEXT NOT NULL DEFAULT 'confirmed',
            FOREIGN KEY(doctor_id) REFERENCES doctors(id) ON DELETE CASCADE,
            FOREIGN KEY(patient_id) REFERENCES patients(id) ON DELETE CASCADE,
            UNIQUE(appointment_time, doctor_id)
        );

        CREATE TABLE IF NOT EXISTS payments (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            appointment_id INTEGER NOT NULL UNIQUE,
            reference TEXT NOT NULL UNIQUE,
            amount INTEGER NOT NULL,
            currency TEXT NOT NULL DEFAULT 'INR',
            method TEXT NOT NULL,
            card_brand TEXT,
            card_last4 TEXT,
            status TEXT NOT NULL DEFAULT 'paid',
            created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY(appointment_id) REFERENCES appointments(id) ON DELETE CASCADE
        );

        CREATE TABLE IF NOT EXISTS reviews (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            rating INTEGER NOT NULL DEFAULT 5,
            title TEXT NOT NULL DEFAULT '',
            comment TEXT NOT NULL,
            doctor_id INTEGER,
            created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY(doctor_id) REFERENCES doctors(id) ON DELETE SET NULL
        );
    """)

    # --- Lightweight migrations for existing databases ---
    def ensure_column(table, col, ddl):
        cols = {r["name"] for r in connection.execute(f"PRAGMA table_info({table})")}
        if col not in cols:
            connection.execute(f"ALTER TABLE {table} ADD COLUMN {ddl}")

    ensure_column("appointments", "status", "status TEXT NOT NULL DEFAULT 'confirmed'")
    connection.execute(
        "UPDATE appointments SET status = 'confirmed' WHERE status IS NULL OR status = ''"
    )
    for col, ddl in [
        ("qualification", "qualification TEXT NOT NULL DEFAULT ''"),
        ("experience", "experience INTEGER NOT NULL DEFAULT 0"),
        ("bio", "bio TEXT NOT NULL DEFAULT ''"),
        ("languages", "languages TEXT NOT NULL DEFAULT 'English'"),
        ("fee", "fee INTEGER NOT NULL DEFAULT 500"),
        ("rating", "rating REAL NOT NULL DEFAULT 4.8"),
    ]:
        ensure_column("doctors", col, ddl)

    # Seed default admin if empty
    if connection.execute("SELECT COUNT(*) FROM admins").fetchone()[0] == 0:
        connection.execute(
            "INSERT INTO admins (username, password_hash) VALUES (?, ?)",
            ("admin", hash_password("admin"))
        )

    # Seed default departments if empty
    if connection.execute("SELECT COUNT(*) FROM branches").fetchone()[0] == 0:
        departments = [
            "Cardiology",
            "Neurology",
            "Hepatology",
            "Pediatrics",
            "Eye Care",
            "Orthopedics"
        ]
        connection.executemany(
            "INSERT INTO branches (name) VALUES (?)",
            [(d,) for d in departments]
        )

    # Seed doctors if empty
    if connection.execute("SELECT COUNT(*) FROM doctors").fetchone()[0] == 0:
        doctors = [
            ("Walter White", 1),
            ("Sarah Jhonson", 2),
            ("William Anderson", 3),
            ("Amanda Jepson", 4),
            ("Michael Brown", 5),
            ("Kristin Miller", 6)
        ]
        connection.executemany(
            "INSERT INTO doctors (name, branch_id) VALUES (?, ?)",
            doctors
        )

    # Backfill / expand to the full 18-doctor directory
    branch_ids = {r["name"]: r["id"] for r in connection.execute("SELECT id, name FROM branches")}
    doctor_branch_map = {
        "Walter White": "Cardiology", "Ananya Sharma": "Cardiology", "Rajesh Kumar": "Cardiology",
        "Sarah Jhonson": "Neurology", "Priya Nair": "Neurology", "Arjun Mehta": "Neurology",
        "William Anderson": "Hepatology", "Deepak Rao": "Hepatology",
        "Amanda Jepson": "Pediatrics", "Kavya Reddy": "Pediatrics",
        "Michael Brown": "Eye Care", "Sneha Patel": "Eye Care",
        "Kristin Miller": "Orthopedics", "Vikram Singh": "Orthopedics", "Rahul Verma": "Orthopedics",
        "Meera Iyer": "Pediatrics", "Sanjay Gupta": "Hepatology", "Lakshmi Venkat": "Cardiology",
    }
    # Extra departments some profiles belong to — ensure they exist
    for extra in ["General Medicine", "Dermatology", "Obstetrics & Gynaecology"]:
        if extra not in branch_ids:
            cur = connection.execute("INSERT INTO branches (name) VALUES (?)", (extra,))
            branch_ids[extra] = cur.lastrowid
    doctor_branch_map.update({
        "Meera Iyer": "Obstetrics & Gynaecology",
        "Sanjay Gupta": "Dermatology",
        "Lakshmi Venkat": "General Medicine",
    })
    # Fix legacy Pediatrics mapping for Hepatology-named William Anderson etc. (keep map above)
    # Ensure every mapped department exists (handles renamed/custom DBs)
    for dept in set(doctor_branch_map.values()):
        if dept not in branch_ids:
            # Reuse close spelling variants already in DB (Orthopedics vs Orthopaedics)
            alias = None
            for existing in list(branch_ids):
                if existing.lower().replace("ae", "e") == dept.lower().replace("ae", "e"):
                    alias = existing
                    break
            if alias:
                branch_ids[dept] = branch_ids[alias]
            else:
                cur = connection.execute("INSERT INTO branches (name) VALUES (?)", (dept,))
                branch_ids[dept] = cur.lastrowid
    existing_names = {r["name"] for r in connection.execute("SELECT name FROM doctors")}
    for dname, profile in DOCTOR_PROFILES.items():
        dept = doctor_branch_map.get(dname)
        if not dept or dept not in branch_ids:
            continue
        if dname not in existing_names:
            connection.execute(
                "INSERT INTO doctors (name, branch_id, qualification, experience, bio, languages, fee, rating) VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
                (dname, branch_ids[dept], profile["qualification"], profile["experience"], profile["bio"], profile["languages"], profile["fee"], profile["rating"]),
            )
    # Backfill profile fields for legacy rows
    for dname, profile in DOCTOR_PROFILES.items():
        connection.execute(
            "UPDATE doctors SET qualification=?, experience=?, bio=?, languages=?, fee=?, rating=? WHERE name=? AND (qualification IS NULL OR qualification='')",
            (profile["qualification"], profile["experience"], profile["bio"], profile["languages"], profile["fee"], profile["rating"], dname),
        )
    # Generic backfill for any custom doctors lacking profiles (keeps cards attractive)
    fallbacks = [
        ("MBBS, MD General Medicine", 8, "Experienced clinician providing thorough diagnosis, preventive screening and friendly follow-up care.", "English, Hindi", 550, 4.7),
        ("MBBS, MS Orthopedics", 10, "Specialist in joint care, fracture management and mobility-focused rehabilitation.", "English, Hindi", 650, 4.7),
        ("MBBS, MD Cardiology", 12, "Heart-care specialist focused on prevention, accurate diagnosis and long-term cardiac wellness.", "English, Hindi", 750, 4.8),
    ]
    for i, r in enumerate(connection.execute("SELECT id FROM doctors WHERE qualification IS NULL OR qualification=''")):
        q, ex, bio, lang, fee, rat = fallbacks[i % len(fallbacks)]
        connection.execute(
            "UPDATE doctors SET qualification=?, experience=?, bio=?, languages=?, fee=?, rating=? WHERE id=?",
            (q, ex, bio, lang, fee, rat, r["id"]),
        )

    # Seed reviews if empty
    if connection.execute("SELECT COUNT(*) FROM reviews").fetchone()[0] == 0:
        connection.executemany(
            "INSERT INTO reviews (name, rating, title, comment, doctor_id) VALUES (?, ?, ?, ?, ?)",
            SEED_REVIEWS
        )

    # Seed demo patient if empty
    if connection.execute("SELECT COUNT(*) FROM patients").fetchone()[0] == 0:
        connection.execute(
            "INSERT INTO patients (username, password_hash) VALUES (?, ?)",
            ("berk", hash_password("berk"))
        )

    connection.commit()
    connection.close()


# ============================================================
# AUTHENTICATION HELPERS & CONTEXT
# ============================================================
def current_user():
    return session.get("user")


def login_required(role=None):
    def decorator(fn):
        @wraps(fn)
        def wrapper(*args, **kwargs):
            user = current_user()
            if not user:
                return redirect(url_for("login", role=role or "patient"))
            if role and user.get("role") != role:
                return redirect(url_for("index"))
            return fn(*args, **kwargs)
        return wrapper
    return decorator


@app.context_processor
def globals_for_templates():
    return {
        "current_user": current_user(),
        "today": date.today().isoformat(),
        "booking_days": BOOKING_DAYS,
        "consultation_fee": CONSULTATION_FEE,
        "currency_symbol": CURRENCY_SYMBOL,
        "hold_minutes": PAYMENT_HOLD_MINUTES
    }


# ============================================================
# PAYMENT HELPERS (demo gateway)
# ============================================================
def luhn_valid(card_number):
    digits = [int(ch) for ch in card_number if ch.isdigit()]
    if len(digits) < 13 or len(digits) > 19:
        return False
    checksum = 0
    parity = len(digits) % 2
    for index, digit in enumerate(digits):
        if index % 2 == parity:
            digit *= 2
            if digit > 9:
                digit -= 9
        checksum += digit
    return checksum % 10 == 0


def card_brand(card_number):
    digits = "".join(ch for ch in card_number if ch.isdigit())
    if digits.startswith("4"):
        return "Visa"
    if digits[:2] in ("51", "52", "53", "54", "55") or (
        len(digits) >= 4 and 2221 <= int(digits[:4]) <= 2720
    ):
        return "Mastercard"
    if digits.startswith(("34", "37")):
        return "Amex"
    if digits.startswith("6"):
        return "RuPay"
    return "Card"


def expiry_valid(expiry):
    try:
        month_str, year_str = expiry.replace(" ", "").split("/")
        month = int(month_str)
        year = int(year_str)
        if year < 100:
            year += 2000
        if not 1 <= month <= 12:
            return False
        now = datetime.now()
        return datetime(year, month, 1) >= datetime(now.year, now.month, 1)
    except (ValueError, AttributeError):
        return False


def expire_stale_holds():
    """Release unpaid bookings so their slots return to the pool."""
    cutoff = (
        datetime.now(timezone.utc) - timedelta(minutes=PAYMENT_HOLD_MINUTES)
    ).strftime("%Y-%m-%d %H:%M:%S")
    connection = db()
    connection.execute(
        "DELETE FROM appointments WHERE status = 'pending' AND created_at < ?",
        (cutoff,)
    )
    connection.commit()
    connection.close()


# ============================================================
# AVAILABILITY LOGIC
# ============================================================
def available_slots(doctor_id, selected_date):
    try:
        selected = date.fromisoformat(selected_date)
    except (ValueError, TypeError):
        return []

    expire_stale_holds()

    today = date.today()
    if selected < today or selected > (today + timedelta(days=BOOKING_DAYS)):
        return []

    # Closed on Sundays
    if selected.weekday() not in WORKING_DAYS:
        return []

    connection = db()
    booked_rows = connection.execute(
        """
        SELECT appointment_time
        FROM appointments
        WHERE doctor_id = ?
        AND date(appointment_time) = ?
        """,
        (doctor_id, selected_date)
    ).fetchall()
    connection.close()

    booked = {
        datetime.fromisoformat(row["appointment_time"]).strftime("%H:%M")
        for row in booked_rows
    }

    slots = []
    current = datetime.combine(selected, OPEN_TIME)
    closing = datetime.combine(selected, CLOSE_TIME)
    now = datetime.now()

    while current < closing:
        # Don't show past times for today
        if selected == today and current <= now:
            current += timedelta(minutes=SLOT_MINUTES)
            continue

        slot_key = current.strftime("%H:%M")
        if slot_key not in booked:
            slots.append({
                "value": current.isoformat(timespec="minutes"),
                "label": current.strftime("%I:%M %p")
            })

        current += timedelta(minutes=SLOT_MINUTES)

    return slots


# ============================================================
# PUBLIC ROUTES
# ============================================================
@app.route("/")
def index():
    connection = db()
    stats = {
        "doctors": connection.execute("SELECT COUNT(*) c FROM doctors").fetchone()["c"],
        "specialties": connection.execute("SELECT COUNT(*) c FROM branches").fetchone()["c"],
        "patients": connection.execute("SELECT COUNT(*) c FROM patients").fetchone()["c"],
        "appointments": connection.execute("SELECT COUNT(*) c FROM appointments").fetchone()["c"]
    }
    branches = connection.execute("SELECT * FROM branches ORDER BY name").fetchall()
    doctors = connection.execute("""
        SELECT d.*, b.name AS branch
        FROM doctors d
        JOIN branches b ON b.id = d.branch_id
        ORDER BY d.rating DESC, d.experience DESC
    """).fetchall()
    featured_reviews = connection.execute(
        "SELECT * FROM reviews ORDER BY rating DESC, id DESC LIMIT 6"
    ).fetchall()
    avg_row = connection.execute("SELECT AVG(rating) a, COUNT(*) c FROM reviews").fetchone()
    connection.close()

    avg_rating = round(avg_row["a"] or 4.8, 1)
    return render_template(
        "index.html",
        stats=stats,
        branches=branches,
        doctors=doctors,
        featured_reviews=featured_reviews,
        avg_rating=avg_rating,
        review_count=avg_row["c"] or 0,
        department_info=DEPARTMENT_INFO
    )


@app.route("/about")
def about():
    connection = db()
    stats = {
        "doctors": connection.execute("SELECT COUNT(*) c FROM doctors").fetchone()["c"],
        "specialties": connection.execute("SELECT COUNT(*) c FROM branches").fetchone()["c"],
        "patients": connection.execute("SELECT COUNT(*) c FROM patients").fetchone()["c"],
        "appointments": connection.execute("SELECT COUNT(*) c FROM appointments").fetchone()["c"]
    }
    doctors = connection.execute("""
        SELECT d.*, b.name AS branch FROM doctors d
        JOIN branches b ON b.id = d.branch_id
        ORDER BY d.rating DESC LIMIT 4
    """).fetchall()
    connection.close()
    return render_template("about.html", stats=stats, doctors=doctors)


@app.route("/reviews", methods=["GET", "POST"])
def reviews_page():
    connection = db()
    if request.method == "POST":
        name = request.form.get("name", "").strip()[:60]
        title = request.form.get("title", "").strip()[:120]
        comment = request.form.get("comment", "").strip()[:1000]
        try:
            rating = int(request.form.get("rating", 5))
        except (ValueError, TypeError):
            rating = 5
        rating = max(1, min(5, rating))
        doctor_id = request.form.get("doctor_id", type=int)
        if not name or not comment:
            flash("Please add your name and a short review.", "error")
        else:
            if doctor_id:
                exists = connection.execute("SELECT id FROM doctors WHERE id=?", (doctor_id,)).fetchone()
                if not exists:
                    doctor_id = None
            connection.execute(
                "INSERT INTO reviews (name, rating, title, comment, doctor_id) VALUES (?, ?, ?, ?, ?)",
                (name, rating, title or "Verified patient review", comment, doctor_id),
            )
            connection.commit()
            flash("Thank you! Your review has been published.", "success")
            connection.close()
            return redirect(url_for("reviews_page"))

    reviews = connection.execute("""
        SELECT r.*, d.name AS doctor_name, b.name AS doctor_branch
        FROM reviews r LEFT JOIN doctors d ON d.id = r.doctor_id
        LEFT JOIN branches b ON b.id = d.branch_id
        ORDER BY r.id DESC
    """).fetchall()
    avg_row = connection.execute("SELECT AVG(rating) a, COUNT(*) c FROM reviews").fetchone()
    dist_rows = connection.execute("SELECT rating, COUNT(*) c FROM reviews GROUP BY rating").fetchall()
    doctors = connection.execute("SELECT id, name FROM doctors ORDER BY name").fetchall()
    connection.close()
    dist = {i: 0 for i in range(1, 6)}
    for r in dist_rows:
        dist[int(r["rating"])] = r["c"]
    return render_template(
        "reviews.html",
        reviews=reviews,
        avg_rating=round(avg_row["a"] or 5.0, 1),
        review_count=avg_row["c"] or 0,
        dist=dist,
        doctors=doctors,
    )


@app.route("/doctors")
def doctors_page():
    q = (request.args.get("q") or "").strip()
    dept = request.args.get("dept", type=int)
    connection = db()
    branches = connection.execute("SELECT * FROM branches ORDER BY name").fetchall()
    sql = """
        SELECT d.*, b.name AS branch FROM doctors d
        JOIN branches b ON b.id = d.branch_id WHERE 1=1
    """
    params = []
    if dept:
        sql += " AND d.branch_id = ?"
        params.append(dept)
    if q:
        sql += " AND (d.name LIKE ? OR d.qualification LIKE ? OR b.name LIKE ?)"
        params += [f"%{q}%", f"%{q}%", f"%{q}%"]
    sql += " ORDER BY d.rating DESC, d.experience DESC"
    doctors = connection.execute(sql, params).fetchall()
    connection.close()
    return render_template("doctors.html", doctors=doctors, branches=branches, q=q, active_dept=dept)


@app.route("/doctors/<int:doctor_id>")
def doctor_detail(doctor_id):
    connection = db()
    doc = connection.execute("""
        SELECT d.*, b.name AS branch FROM doctors d
        JOIN branches b ON b.id = d.branch_id WHERE d.id = ?
    """, (doctor_id,)).fetchone()
    if not doc:
        connection.close()
        abort(404)
    related = connection.execute("""
        SELECT d.*, b.name AS branch FROM doctors d
        JOIN branches b ON b.id = d.branch_id
        WHERE d.branch_id = ? AND d.id != ? LIMIT 3
    """, (doc["branch_id"], doctor_id)).fetchall()
    doc_reviews = connection.execute(
        "SELECT * FROM reviews WHERE doctor_id = ? ORDER BY id DESC LIMIT 5", (doctor_id,)
    ).fetchall()
    all_reviews = connection.execute("SELECT * FROM reviews ORDER BY id DESC LIMIT 3").fetchall()
    # Next available day preview
    upcoming_preview = []
    for offset in range(0, 7):
        day = date.today() + timedelta(days=offset)
        slots = available_slots(doctor_id, day.isoformat())
        if slots:
            upcoming_preview.append({"date": day, "count": len(slots), "iso": day.isoformat()})
        if len(upcoming_preview) >= 4:
            break
    connection.close()
    return render_template(
        "doctor_detail.html", doc=doc, related=related,
        doc_reviews=doc_reviews, all_reviews=all_reviews,
        upcoming_preview=upcoming_preview,
    )


@app.route("/login")
def login_index():
    user = current_user()
    if user:
        return redirect(url_for("patient_dashboard" if user["role"] == "patient" else "admin_dashboard"))
    return redirect(url_for("login", role="patient"))


@app.route("/login/<role>", methods=["GET", "POST"])
def login(role):
    if role not in ("patient", "admin"):
        abort(404)

    user = current_user()
    if user and user.get("role") == role:
        return redirect(url_for("patient_dashboard" if role == "patient" else "admin_dashboard"))

    if request.method == "POST":
        username = request.form.get("username", "").strip()
        password = hash_password(request.form.get("password", ""))
        connection = db()
        table = "patients" if role == "patient" else "admins"
        row = connection.execute(
            f"SELECT id, username FROM {table} WHERE username=? AND password_hash=?",
            (username, password)
        ).fetchone()
        connection.close()

        if row:
            session["user"] = {
                "id": row["id"],
                "username": row["username"],
                "role": role
            }
            return redirect(url_for("patient_dashboard" if role == "patient" else "admin_dashboard"))

        flash("Invalid username or password.", "error")

    return render_template("login.html", role=role)


@app.route("/signup", methods=["GET", "POST"])
def signup():
    user = current_user()
    if user:
        return redirect(url_for("patient_dashboard" if user["role"] == "patient" else "admin_dashboard"))

    if request.method == "POST":
        username = request.form.get("username", "").strip()
        password = request.form.get("password", "")
        confirm_password = request.form.get("confirm_password")

        if len(username) < 3 or len(password) < 4:
            flash("Username must be 3+ characters and password 4+ characters.", "error")
        elif confirm_password is not None and password != confirm_password:
            flash("Passwords do not match. Please re-enter your password.", "error")
        else:
            connection = db()
            try:
                cur = connection.execute(
                    "INSERT INTO patients (username, password_hash) VALUES (?, ?)",
                    (username, hash_password(password))
                )
                connection.commit()
                session["user"] = {
                    "id": cur.lastrowid,
                    "username": username,
                    "role": "patient"
                }
                flash("Account created successfully! Welcome to Psmhealthcare.", "success")
                return redirect(url_for("patient_dashboard"))
            except sqlite3.IntegrityError:
                flash("That username is already registered. Please choose another.", "error")
            finally:
                connection.close()

    return render_template("signup.html")


@app.route("/logout")
def logout():
    session.clear()
    return redirect(url_for("index"))


# ============================================================
# PATIENT PORTAL & BOOKING
# ============================================================
@app.route("/patient")
@login_required("patient")
def patient_dashboard():
    uid = session["user"]["id"]
    expire_stale_holds()
    connection = db()
    now_iso = datetime.now().isoformat(timespec="minutes")
    upcoming = connection.execute("""
        SELECT a.id, a.appointment_time, a.status,
           d.name AS doctor, d.fee AS consultation_fee, b.name AS branch,
               pay.reference, pay.amount, pay.method, pay.card_brand, pay.card_last4
        FROM appointments a
        JOIN doctors d ON d.id = a.doctor_id
        JOIN branches b ON b.id = d.branch_id
        LEFT JOIN payments pay ON pay.appointment_id = a.id
        WHERE a.patient_id = ? AND a.appointment_time >= ?
        ORDER BY a.appointment_time ASC
    """, (uid, now_iso)).fetchall()

    past_count = connection.execute("""
        SELECT COUNT(*) c
        FROM appointments
        WHERE patient_id = ? AND appointment_time < ?
    """, (uid, now_iso)).fetchone()["c"]
    connection.close()

    return render_template(
        "patient_dashboard.html",
        upcoming=upcoming,
        past_count=past_count
    )


@app.route("/book")
@login_required("patient")
def book():
    expire_stale_holds()
    connection = db()
    branches = connection.execute("SELECT * FROM branches ORDER BY name").fetchall()
    doctors = connection.execute("""
        SELECT d.*, b.name AS branch
        FROM doctors d
        JOIN branches b ON b.id = d.branch_id
        ORDER BY d.name
    """).fetchall()
    connection.close()

    return render_template(
        "book.html",
        branches=branches,
        doctors=doctors
    )


@app.route("/appointment/book", methods=["POST"])
@app.route("/book", methods=["POST"])
@login_required("patient")
def book_appointment():
    doctor_id = request.form.get("doctor_id", type=int)
    appointment_time = request.form.get("appointment_time", "").strip()

    if not doctor_id or not appointment_time:
        flash("Please select a department, doctor and consultation time.", "error")
        return redirect(url_for("book"))

    try:
        selected_dt = datetime.fromisoformat(appointment_time)
    except ValueError:
        flash("Invalid appointment time format.", "error")
        return redirect(url_for("book"))

    # Verify slot availability on the server side
    expire_stale_holds()
    available = available_slots(doctor_id, selected_dt.date().isoformat())
    requested_val = selected_dt.isoformat(timespec="minutes")

    if not any(slot["value"] == requested_val for slot in available):
        flash("That appointment slot is no longer available. Please select another time.", "error")
        return redirect(url_for("book"))

    payment_choice = request.form.get("payment_choice", "pay_online")
    if payment_choice not in ("pay_online", "pay_later"):
        flash("Please choose whether to pay online or at the clinic.", "error")
        return redirect(url_for("book"))

    appointment_status = "confirmed" if payment_choice == "pay_later" else "pending"
    connection = db()
    try:
        cur = connection.execute(
            """
            INSERT INTO appointments (appointment_time, doctor_id, patient_id, status)
            VALUES (?, ?, ?, ?)
            """,
            (requested_val, doctor_id, session["user"]["id"], appointment_status)
        )
        appointment_id = cur.lastrowid
        connection.commit()
    except sqlite3.IntegrityError:
        connection.rollback()
        connection.close()
        flash("That time was just booked by another patient. Please select another slot.", "error")
        return redirect(url_for("book"))
    finally:
        connection.close()

    if payment_choice == "pay_later":
        flash(
            "Appointment confirmed. You can pay the consultation fee at the clinic "
            "or pay online later from your appointments.",
            "success"
        )
        return redirect(url_for("patient_dashboard"))

    return redirect(url_for("payment_checkout", appointment_id=appointment_id))


@app.route("/bookings/<int:appointment_id>/release", methods=["POST"])
@login_required("patient")
def release_booking(appointment_id):
    connection = db()
    cur = connection.execute(
        "DELETE FROM appointments WHERE id = ? AND patient_id = ? AND status = 'pending'",
        (appointment_id, session["user"]["id"])
    )
    connection.commit()
    connection.close()

    if cur.rowcount > 0:
        flash("Booking released. The slot is available again.", "success")
    else:
        flash("That booking could not be released.", "error")

    return redirect(url_for("book"))


# ============================================================
# ONLINE PAYMENT (demo gateway)
# ============================================================
@app.route("/payment/<int:appointment_id>")
@login_required("patient")
def payment_checkout(appointment_id):
    expire_stale_holds()
    connection = db()
    row = connection.execute("""
        SELECT a.id, a.appointment_time, a.status, a.patient_id,
               d.name AS doctor, d.fee AS consultation_fee, b.name AS branch, pay.reference
        FROM appointments a
        JOIN doctors d ON d.id = a.doctor_id
        JOIN branches b ON b.id = d.branch_id
        LEFT JOIN payments pay ON pay.appointment_id = a.id
        WHERE a.id = ?
    """, (appointment_id,)).fetchone()
    connection.close()

    if not row or row["patient_id"] != session["user"]["id"]:
        abort(404)

    if row["reference"]:
        flash("This appointment is already paid for.", "success")
        return redirect(url_for("patient_dashboard"))
    if row["status"] not in ("pending", "confirmed"):
        abort(404)

    return render_template(
        "payment.html",
        appointment=row,
        consultation_fee=row["consultation_fee"]
    )


@app.route("/payment/<int:appointment_id>/pay", methods=["POST"])
@login_required("patient")
def payment_process(appointment_id):
    expire_stale_holds()
    connection = db()
    appointment = connection.execute(
        """
        SELECT a.id, a.appointment_time, a.status, a.patient_id,
               d.name AS doctor, d.fee AS consultation_fee, b.name AS branch, pay.reference
        FROM appointments a
        JOIN doctors d ON d.id = a.doctor_id
        JOIN branches b ON b.id = d.branch_id
        LEFT JOIN payments pay ON pay.appointment_id = a.id
        WHERE a.id = ?
        """,
        (appointment_id,)
    ).fetchone()

    if not appointment or appointment["patient_id"] != session["user"]["id"]:
        connection.close()
        abort(404)

    if appointment["reference"]:
        connection.close()
        flash("This appointment is already paid for.", "success")
        return redirect(url_for("patient_dashboard"))
    if appointment["status"] not in ("pending", "confirmed"):
        connection.close()
        abort(404)

    method = request.form.get("method", "card")
    card_name = request.form.get("card_name", "").strip()
    card_number = "".join(ch for ch in request.form.get("card_number", "") if ch.isdigit())
    card_expiry = request.form.get("card_expiry", "").strip()
    card_cvv = "".join(ch for ch in request.form.get("card_cvv", "") if ch.isdigit())

    error = None
    if method == "card":
        if len(card_name) < 3:
            error = "Please enter the name printed on your card."
        elif not luhn_valid(card_number):
            error = "That card number is not valid. Please check and try again."
        elif card_number == TEST_DECLINE_CARD:
            error = "Your card was declined by the issuer. Try another card."
        elif not expiry_valid(card_expiry):
            error = "The card expiry date is invalid or has passed."
        elif not 3 <= len(card_cvv) <= 4:
            error = "Please enter the 3 or 4 digit security code."
    elif method == "upi":
        vpa = request.form.get("upi_id", "").strip()
        if "@" not in vpa or len(vpa) < 5:
            error = "Please enter a valid UPI ID (e.g. name@upi)."
    elif method == "netbanking":
        if not request.form.get("bank"):
            error = "Please choose your bank."
    else:
        error = "Please choose a payment method."

    if error:
        connection.close()
        flash(error, "error")
        return redirect(url_for("payment_checkout", appointment_id=appointment_id))

    # Demo gateway approval
    reference = "ML-" + hashlib.sha512(
        f"{appointment_id}-{datetime.now().isoformat()}".encode()
    ).hexdigest()[:10].upper()

    last4 = card_number[-4:] if method == "card" else None
    brand = card_brand(card_number) if method == "card" else None
    consultation_fee = appointment["consultation_fee"]

    try:
        connection.execute(
            "UPDATE appointments SET status = 'confirmed' WHERE id = ?",
            (appointment_id,)
        )
        connection.execute(
            """
            INSERT INTO payments
                (appointment_id, reference, amount, currency, method, card_brand, card_last4, status)
            VALUES (?, ?, ?, ?, ?, ?, ?, 'paid')
            """,
            (
                appointment_id,
                reference,
                consultation_fee,
                CURRENCY,
                method,
                brand,
                last4
            )
        )
        connection.commit()
    except sqlite3.IntegrityError:
        connection.rollback()
        connection.close()
        flash("Payment could not be recorded. Please try again.", "error")
        return redirect(url_for("payment_checkout", appointment_id=appointment_id))
    finally:
        connection.close()

    flash(
        f"Payment of {CURRENCY_SYMBOL}{consultation_fee} successful. "
        f"Receipt {reference} - your appointment is confirmed.",
        "success"
    )
    return redirect(url_for("patient_dashboard"))


@app.route("/appointments/<int:appointment_id>/cancel", methods=["POST"])
@login_required("patient")
def cancel_appointment(appointment_id):
    connection = db()
    now_iso = datetime.now().isoformat(timespec="minutes")
    row = connection.execute(
        """
        SELECT a.status, pay.reference, pay.amount, d.fee AS consultation_fee
        FROM appointments a
        JOIN doctors d ON d.id = a.doctor_id
        LEFT JOIN payments pay ON pay.appointment_id = a.id
        WHERE a.id = ? AND a.patient_id = ? AND a.appointment_time >= ?
        """,
        (appointment_id, session["user"]["id"], now_iso)
    ).fetchone()

    if not row:
        connection.close()
        flash("Appointment could not be cancelled.", "error")
        return redirect(url_for("patient_dashboard"))

    paid = row["reference"] is not None
    connection.execute(
        "DELETE FROM appointments WHERE id = ? AND patient_id = ?",
        (appointment_id, session["user"]["id"])
    )
    connection.commit()
    connection.close()

    if paid:
        flash(
            f"Appointment cancelled. {CURRENCY_SYMBOL}{row['amount']} "
            "will be refunded to your original payment method.",
            "success"
        )
    else:
        flash("Booking cancelled. The slot is available again.", "success")

    return redirect(url_for("patient_dashboard"))


# ============================================================
# ADMINISTRATION PORTAL
# ============================================================
@app.route("/admin")
@login_required("admin")
def admin_dashboard():
    expire_stale_holds()
    connection = db()
    now_iso = datetime.now().isoformat(timespec="minutes")
    stats = {
        "patients": connection.execute("SELECT COUNT(*) c FROM patients").fetchone()["c"],
        "doctors": connection.execute("SELECT COUNT(*) c FROM doctors").fetchone()["c"],
        "branches": connection.execute("SELECT COUNT(*) c FROM branches").fetchone()["c"],
        "appointments": connection.execute("SELECT COUNT(*) c FROM appointments WHERE appointment_time >= ?", (now_iso,)).fetchone()["c"],
        "revenue": connection.execute("SELECT COALESCE(SUM(amount), 0) s FROM payments WHERE status = 'paid'").fetchone()["s"],
        "pending": connection.execute("SELECT COUNT(*) c FROM appointments WHERE status = 'pending'").fetchone()["c"]
    }
    appointments = connection.execute("""
        SELECT a.id, a.appointment_time, a.status, p.username AS patient,
               d.name AS doctor, d.fee AS consultation_fee, b.name AS branch,
               pay.reference, pay.amount, pay.method
        FROM appointments a
        JOIN patients p ON p.id = a.patient_id
        JOIN doctors d ON d.id = a.doctor_id
        JOIN branches b ON b.id = d.branch_id
        LEFT JOIN payments pay ON pay.appointment_id = a.id
        WHERE a.appointment_time >= ?
        ORDER BY a.appointment_time ASC
        LIMIT 15
    """, (now_iso,)).fetchall()

    branches = connection.execute("""
        SELECT b.id, b.name, COUNT(d.id) AS doctors
        FROM branches b
        LEFT JOIN doctors d ON d.branch_id = b.id
        GROUP BY b.id
        ORDER BY b.name
    """).fetchall()
    connection.close()

    return render_template(
        "admin_dashboard.html",
        stats=stats,
        appointments=appointments,
        branches=branches
    )


@app.route("/admin/doctors", methods=["GET", "POST"])
@login_required("admin")
def admin_doctors():
    connection = db()
    if request.method == "POST":
        name = request.form.get("name", "").strip()
        branch_id = request.form.get("branch_id", type=int)
        qualification = request.form.get("qualification", "").strip() or "MBBS, MD"
        try:
            experience = int(request.form.get("experience", 5) or 5)
        except (ValueError, TypeError):
            experience = 5
        bio = request.form.get("bio", "").strip() or "Experienced clinician providing evidence-based, patient-first care."
        languages = request.form.get("languages", "").strip() or "English, Hindi"
        try:
            fee = int(request.form.get("fee", CONSULTATION_FEE) or CONSULTATION_FEE)
        except (ValueError, TypeError):
            fee = CONSULTATION_FEE
        try:
            rating = float(request.form.get("rating", 4.8) or 4.8)
        except (ValueError, TypeError):
            rating = 4.8
        if name and branch_id:
            connection.execute(
                "INSERT INTO doctors (name, branch_id, qualification, experience, bio, languages, fee, rating) VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
                (name, branch_id, qualification, experience, bio, languages, fee, max(1.0, min(5.0, rating))),
            )
            connection.commit()
            flash("Doctor added successfully.", "success")
        else:
            flash("Doctor name and department are required.", "error")

    doctors = connection.execute("""
        SELECT d.*, b.name AS branch
        FROM doctors d
        JOIN branches b ON b.id = d.branch_id
        ORDER BY d.name
    """).fetchall()
    branches = connection.execute("SELECT * FROM branches ORDER BY name").fetchall()
    connection.close()

    return render_template("admin_doctors.html", doctors=doctors, branches=branches)


@app.route("/admin/doctors/<int:doctor_id>/delete", methods=["POST"])
@login_required("admin")
def delete_doctor(doctor_id):
    connection = db()
    connection.execute("DELETE FROM doctors WHERE id = ?", (doctor_id,))
    connection.commit()
    connection.close()
    flash("Doctor removed successfully.", "success")
    return redirect(url_for("admin_doctors"))


@app.route("/admin/branches", methods=["GET", "POST"])
@login_required("admin")
def admin_branches():
    connection = db()
    if request.method == "POST":
        name = request.form.get("name", "").strip()
        if name:
            try:
                connection.execute("INSERT INTO branches (name) VALUES (?)", (name,))
                connection.commit()
                flash("Department added successfully.", "success")
            except sqlite3.IntegrityError:
                flash("Department already exists.", "error")
        else:
            flash("Department name is required.", "error")

    branches = connection.execute("""
        SELECT b.*, COUNT(d.id) AS doctors
        FROM branches b
        LEFT JOIN doctors d ON d.branch_id = b.id
        GROUP BY b.id
        ORDER BY b.name
    """).fetchall()
    connection.close()

    return render_template("admin_branches.html", branches=branches)


@app.route("/admin/appointments")
@login_required("admin")
def admin_appointments():
    connection = db()
    rows = connection.execute("""
        SELECT a.id, a.appointment_time, a.status, p.username AS patient,
               d.name AS doctor, d.fee AS consultation_fee, b.name AS branch,
               pay.reference, pay.amount, pay.method, pay.card_last4
        FROM appointments a
        JOIN patients p ON p.id = a.patient_id
        JOIN doctors d ON d.id = a.doctor_id
        JOIN branches b ON b.id = d.branch_id
        LEFT JOIN payments pay ON pay.appointment_id = a.id
        ORDER BY a.appointment_time DESC
    """).fetchall()
    connection.close()

    return render_template("admin_appointments.html", appointments=rows)


@app.route("/admin/appointments/<int:appointment_id>/cancel", methods=["POST"])
@login_required("admin")
def admin_cancel_appointment(appointment_id):
    connection = db()
    row = connection.execute(
        """
        SELECT a.status, pay.reference, pay.amount, d.fee AS consultation_fee
        FROM appointments a
        JOIN doctors d ON d.id = a.doctor_id
        LEFT JOIN payments pay ON pay.appointment_id = a.id
        WHERE a.id = ?
        """,
        (appointment_id,)
    ).fetchone()
    connection.execute("DELETE FROM appointments WHERE id = ?", (appointment_id,))
    connection.commit()
    connection.close()

    if row and row["reference"]:
        flash(f"Appointment removed. {CURRENCY_SYMBOL}{row['amount']} refund due to the patient.", "success")
    else:
        flash("Appointment cancelled and removed.", "success")
    return redirect(url_for("admin_appointments"))


# ============================================================
# API ENDPOINTS
# ============================================================
@app.route("/api/doctors")
def api_doctors():
    branch_id = request.args.get("branch_id", type=int)
    connection = db()
    if branch_id:
        rows = connection.execute(
            """
            SELECT d.id, d.name, b.name AS branch, d.qualification, d.experience, d.fee, d.rating
            FROM doctors d
            JOIN branches b ON b.id = d.branch_id
            WHERE d.branch_id = ?
            ORDER BY d.rating DESC, d.name
            """,
            (branch_id,)
        ).fetchall()
    else:
        rows = connection.execute(
            """
            SELECT d.id, d.name, b.name AS branch, d.qualification, d.experience, d.fee, d.rating
            FROM doctors d
            JOIN branches b ON b.id = d.branch_id
            ORDER BY d.rating DESC, d.name
            """
        ).fetchall()
    connection.close()

    return jsonify([dict(r) for r in rows])


@app.route("/api/availability")
def api_availability():
    doctor_id = request.args.get("doctor_id", type=int)
    selected_date = request.args.get("date", "").strip()

    if not doctor_id or not selected_date:
        return jsonify({
            "slots": [],
            "error": "Doctor and date are required."
        }), 400

    response = jsonify({
        "slots": available_slots(doctor_id, selected_date)
    })
    response.headers["Cache-Control"] = "no-store, no-cache, must-revalidate"
    return response


# ============================================================
# APPLICATION ENTRYPOINT
# ============================================================
init_db()

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 8085))
    print(f"\n=======================================================")
    print(f"Psmhealthcare System Running!")
    print(f" Open your browser: http://127.0.0.1:{port}")
    print(f"=======================================================\n")
    app.run(host="0.0.0.0", port=port, debug=True)