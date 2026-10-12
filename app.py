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
# PAYMENT CONFIGURATION (demo gateway - no real charges)
# ============================================================
CONSULTATION_FEE = 500
CURRENCY = "INR"
CURRENCY_SYMBOL = "?"
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
    """)

    # Migrate databases created before the payment feature existed
    appointment_cols = {
        row["name"]
        for row in connection.execute("PRAGMA table_info(appointments)")
    }
    if "status" not in appointment_cols:
        connection.execute(
            "ALTER TABLE appointments ADD COLUMN status TEXT NOT NULL DEFAULT 'confirmed'"
        )
        connection.execute(
            "UPDATE appointments SET status = 'confirmed' WHERE status IS NULL OR status = ''"
        )

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
        ORDER BY d.name
    """).fetchall()
    connection.close()

    return render_template(
        "index.html",
        stats=stats,
        branches=branches,
        doctors=doctors
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
               d.name AS doctor, b.name AS branch,
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
               d.name AS doctor, b.name AS branch, pay.reference
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

    return render_template("payment.html", appointment=row)


@app.route("/payment/<int:appointment_id>/pay", methods=["POST"])
@login_required("patient")
def payment_process(appointment_id):
    expire_stale_holds()
    connection = db()
    appointment = connection.execute(
        """
        SELECT a.id, a.appointment_time, a.status, a.patient_id,
               d.name AS doctor, b.name AS branch, pay.reference
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
                CONSULTATION_FEE,
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
        f"Payment of {CURRENCY_SYMBOL}{CONSULTATION_FEE} successful. "
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
        SELECT a.status, pay.reference
        FROM appointments a
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
            f"Appointment cancelled. {CURRENCY_SYMBOL}{CONSULTATION_FEE} "
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
               d.name AS doctor, b.name AS branch,
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
        if name and branch_id:
            connection.execute(
                "INSERT INTO doctors (name, branch_id) VALUES (?, ?)",
                (name, branch_id)
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
               d.name AS doctor, b.name AS branch,
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
        SELECT a.status, pay.reference
        FROM appointments a
        LEFT JOIN payments pay ON pay.appointment_id = a.id
        WHERE a.id = ?
        """,
        (appointment_id,)
    ).fetchone()
    connection.execute("DELETE FROM appointments WHERE id = ?", (appointment_id,))
    connection.commit()
    connection.close()

    if row and row["reference"]:
        flash(f"Appointment removed. {CURRENCY_SYMBOL}{CONSULTATION_FEE} refund due to the patient.", "success")
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
            SELECT d.id, d.name, b.name AS branch
            FROM doctors d
            JOIN branches b ON b.id = d.branch_id
            WHERE d.branch_id = ?
            ORDER BY d.name
            """,
            (branch_id,)
        ).fetchall()
    else:
        rows = connection.execute(
            """
            SELECT d.id, d.name, b.name AS branch
            FROM doctors d
            JOIN branches b ON b.id = d.branch_id
            ORDER BY d.name
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