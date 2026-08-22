import os
import random
import sqlite3
from datetime import datetime
from functools import wraps
from flask import Flask, render_template, request, jsonify, redirect, url_for, session, flash
from werkzeug.security import generate_password_hash, check_password_hash

app = Flask(__name__)
app.secret_key = os.environ.get("SECRET_KEY", "nextcamp_secret_key_scaler_sst_2026_prod")
DB_PATH = os.environ.get("NEXTCAMP_DB", os.path.join(os.path.dirname(__file__), "nextcamp.db"))


# ==============================================================================
# DATABASE INITIALIZATION & HELPER FUNCTIONS
# ==============================================================================

def get_db():
    """Returns a SQLite connection with Row factory enabled."""
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def init_db():
    """Initializes SQLite database tables and baseline seeds if empty."""
    conn = get_db()
    cursor = conn.cursor()

    # 1. Users Table
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            email TEXT UNIQUE NOT NULL,
            password_hash TEXT NOT NULL,
            role TEXT NOT NULL,
            student_id TEXT,
            is_active INTEGER DEFAULT 1,
            status TEXT DEFAULT 'Good Standing 🟢',
            fine_amount INTEGER DEFAULT 0,
            reputation REAL DEFAULT 4.7,
            reputation_points INTEGER DEFAULT 94,
            badge TEXT DEFAULT 'Tech Support Pro'
        )
    """)

    # Ensure is_active column exists if upgrading existing DB
    cursor.execute("PRAGMA table_info(users)")
    user_cols = [col[1] for col in cursor.fetchall()]
    if "is_active" not in user_cols:
        cursor.execute("ALTER TABLE users ADD COLUMN is_active INTEGER DEFAULT 1")

    # 2. Events Table
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS events (
            id TEXT PRIMARY KEY,
            name TEXT NOT NULL,
            organizer TEXT NOT NULL,
            venue TEXT NOT NULL,
            date TEXT NOT NULL,
            start_time TEXT NOT NULL,
            end_time TEXT NOT NULL,
            description TEXT
        )
    """)

    # 3. Workers Table
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS workers (
            id TEXT PRIMARY KEY,
            name TEXT NOT NULL,
            category TEXT NOT NULL,
            rating REAL NOT NULL DEFAULT 5.0,
            tasks_solved INTEGER NOT NULL DEFAULT 0,
            phone TEXT,
            email TEXT
        )
    """)

    # 4. Tickets Table
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS tickets (
            id TEXT PRIMARY KEY,
            title TEXT NOT NULL,
            category TEXT NOT NULL,
            location TEXT NOT NULL,
            urgency TEXT NOT NULL,
            description TEXT,
            reporter_name TEXT,
            reported_at TEXT,
            status TEXT NOT NULL DEFAULT 'Assigned',
            assigned_worker TEXT,
            solver_id TEXT,
            solver_name TEXT,
            solver_rating REAL,
            solver_display TEXT,
            rated BOOLEAN DEFAULT 0,
            rating_score REAL
        )
    """)

    # 5. Reviews Table
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS reviews (
            id TEXT PRIMARY KEY,
            ticket_id TEXT NOT NULL,
            worker_id TEXT NOT NULL,
            rating REAL NOT NULL,
            suggestion TEXT,
            student_name TEXT,
            student_roll TEXT,
            worker_name TEXT,
            worker_category TEXT,
            response_time INTEGER,
            quality INTEGER,
            behavior INTEGER,
            timestamp TEXT
        )
    """)

    # Alerts & Announcements Support
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS alerts (
            id TEXT PRIMARY KEY,
            title TEXT NOT NULL,
            message TEXT NOT NULL,
            level TEXT NOT NULL,
            location TEXT,
            timestamp TEXT,
            active BOOLEAN DEFAULT 1
        )
    """)

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS announcements (
            id TEXT PRIMARY KEY,
            title TEXT NOT NULL,
            content TEXT NOT NULL,
            category TEXT NOT NULL,
            badge_color TEXT,
            date TEXT NOT NULL,
            time TEXT,
            venue TEXT,
            organizer TEXT
        )
    """)

    # Seed Default Users (Initial Baseline)
    cursor.execute("SELECT COUNT(*) FROM users")
    if cursor.fetchone()[0] == 0:
        default_users = [
            ("Sameer Verma", "sameer.verma@sst.scaler.com", generate_password_hash("scaler123"), "Student", "SST-2023-CS042", 1, "Good Standing 🟢", 0, 4.7, 94, "Tech Support Pro"),
            ("Campus Administrator", "admin@sst.scaler.com", generate_password_hash("admin123"), "Admin", "SST-FACULTY-01", 1, "Good Standing 🟢", 0, 5.0, 100, "System Overseer")
        ]
        cursor.executemany("""
            INSERT INTO users (name, email, password_hash, role, student_id, is_active, status, fine_amount, reputation, reputation_points, badge)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, default_users)

    # Seed Default Workers
    cursor.execute("SELECT COUNT(*) FROM workers")
    if cursor.fetchone()[0] == 0:
        default_workers = [
            ("WKR-01", "Ravi", "Electrical", 4.9, 84, "+91 98765 43210", "ravi.tech@sst.scaler.com"),
            ("WKR-02", "Amit Singh", "Hardware", 4.8, 62, "+91 98765 43211", "amit.hw@sst.scaler.com"),
            ("WKR-03", "Priya Verma", "IT", 4.95, 112, "+91 98765 43212", "priya.it@sst.scaler.com"),
            ("WKR-04", "Manoj Kumar", "Electrical", 4.6, 45, "+91 98765 43213", "manoj.k@sst.scaler.com"),
            ("WKR-05", "Vikram Rao", "IT", 4.55, 38, "+91 98765 43214", "vikram.r@sst.scaler.com"),
            ("WKR-06", "Suresh Nair", "Hardware", 4.7, 51, "+91 98765 43215", "suresh.n@sst.scaler.com")
        ]
        cursor.executemany("""
            INSERT INTO workers (id, name, category, rating, tasks_solved, phone, email)
            VALUES (?, ?, ?, ?, ?, ?, ?)
        """, default_workers)

    # Seed Default Events
    cursor.execute("SELECT COUNT(*) FROM events")
    if cursor.fetchone()[0] == 0:
        default_events = [
            ("EVT-101", "Annual Tech Symposium 2026", "SST Tech Society", "Main Auditorium", "Today", "09:00", "18:00", "Keynotes, project demos and industry panel discussions in the Auditorium."),
            ("EVT-102", "Placement Coding Sprint", "Career Advancement Cell", "Block C Exam Hall", "Today", "10:00", "17:00", "Online coding round for hiring partner assessments."),
            ("EVT-103", "HPL Quarter-Final Match", "Sports Council", "Sports Complex", "Today", "15:00", "20:00", "Hostel cricket tournament finals.")
        ]
        cursor.executemany("""
            INSERT INTO events (id, name, organizer, venue, date, start_time, end_time, description)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        """, default_events)

    # Seed Default Tickets
    cursor.execute("SELECT COUNT(*) FROM tickets")
    if cursor.fetchone()[0] == 0:
        default_tickets = [
            ("TCK-1001", "Lab 3 High-Voltage Switchboard Sparking", "Electrical", "Innovation Lab 3, Rack A2", "Critical", "Feeder breaker sparking on load activation. Circuit isolated.", "Sameer Verma", "1 hour ago", "Assigned", "Ravi", "WKR-01", "Ravi", 4.9, "Assigned to: Ravi (⭐ 4.9)", 0, None),
            ("TCK-1002", "Corridor Wi-Fi AP Dropping Connections", "IT", "Hostel Block B, 2nd Floor", "Medium", "AP-B-201 authentication timeout for student laptops.", "Sameer Verma", "2 hours ago", "In Progress", "Priya Verma", "WKR-03", "Priya Verma", 4.95, "Assigned to: Priya Verma (⭐ 4.95)", 0, None),
            ("TCK-1000", "Hostel Water Purifier Flow Sensor Glitch", "Hardware", "Hostel Block B, Mess Hall", "High", "Dispenser flow meter calibrated and filtration unit serviced.", "Sameer Verma", "3 hours ago", "Resolved", "Amit Singh", "WKR-02", "Amit Singh", 4.8, "Assigned to: Amit Singh (⭐ 4.8)", 0, None)
        ]
        cursor.executemany("""
            INSERT INTO tickets (id, title, category, location, urgency, description, reporter_name, reported_at, status, assigned_worker, solver_id, solver_name, solver_rating, solver_display, rated, rating_score)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, default_tickets)

    # Seed Default Reviews
    cursor.execute("SELECT COUNT(*) FROM reviews")
    if cursor.fetchone()[0] == 0:
        default_reviews = [
            ("REV-501", "TCK-0998", "WKR-01", 5.0, "Arrived within 10 minutes and completely fixed the tripped circuit breaker. Excellent work!", "Sameer Verma", "SST-2023-CS042", "Ravi", "Electrical", 5, 5, 5, "Today, 10:15 AM"),
            ("REV-502", "TCK-0999", "WKR-03", 4.67, "Wi-Fi access point firmware upgrade resolved the latency issues in the library.", "Aarav Sharma", "SST-2023-CS015", "Priya Verma", "IT", 5, 5, 4, "Yesterday, 4:45 PM")
        ]
        cursor.executemany("""
            INSERT INTO reviews (id, ticket_id, worker_id, rating, suggestion, student_name, student_roll, worker_name, worker_category, response_time, quality, behavior, timestamp)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, default_reviews)

    # Seed Alerts
    cursor.execute("SELECT COUNT(*) FROM alerts")
    if cursor.fetchone()[0] == 0:
        default_alerts = [
            ("ALT-01", "URGENT: Class Rescheduled - CS302 Advanced Algorithms", "CS302 class scheduled for 2:00 PM in Classroom 204 has been moved to Innovation Lab 4 due to emergency AC maintenance. Attendance is mandatory.", "danger", "Classroom 204 &rarr; Innovation Lab 4", "Today, 1:45 PM", 1),
            ("ALT-02", "Hostel Water Valve Maintenance Notice", "Secondary pump line maintenance in Hostel Block B from 4:30 PM to 6:00 PM. Reserve tanks are online.", "warning", "Hostel Block B", "Today, 11:20 AM", 1)
        ]
        cursor.executemany("""
            INSERT INTO alerts (id, title, message, level, location, timestamp, active)
            VALUES (?, ?, ?, ?, ?, ?, ?)
        """, default_alerts)

    # Seed Announcements
    cursor.execute("SELECT COUNT(*) FROM announcements")
    if cursor.fetchone()[0] == 0:
        default_announcements = [
            ("ANN-01", "SST Hackathon 2026: Registrations Open", "Join 400+ student builders for a 36-hour sprint on Smart Campus AI & Distributed Systems. Cash pool ₹2,00,000.", "Events", "emerald", "Aug 28 - Aug 30", "09:00 AM", "Main Auditorium & Innovation Hub", "SST Tech Society"),
            ("ANN-02", "Mid-Semester Examination Hall Allotment Released", "Check your seating plan on the examination sub-portal. Carry your physical SST student ID badge.", "Academic", "indigo", "Aug 25 - Sep 04", "Morning Sessions", "Block C & Exam Halls", "Academic Office"),
            ("ANN-03", "Hostel Premier League (HPL) Cricket Knockouts", "Block B Titans vs Block A Warriors in the evening quarter-finals under floodlights. Refreshments provided!", "Hostel", "amber", "Today, Aug 22", "05:30 PM", "Campus Sports Complex", "Hostel Council"),
            ("ANN-04", "Guest Keynote: Generative AI & Autonomous Agents", "Dr. A. Sharma from Google DeepMind sharing insights on production agent workflows.", "Academic", "purple", "Tomorrow, Aug 23", "11:00 AM", "Seminar Hall 1", "Dept. of Computer Science"),
            ("ANN-05", "Night Canteen Extended Operating Hours", "Hostel canteen will remain operational until 3:00 AM during mid-term examination week.", "Hostel", "rose", "Aug 22 - Sep 05", "10:00 PM - 03:00 AM", "Central Cafeteria", "Campus Services")
        ]
        cursor.executemany("""
            INSERT INTO announcements (id, title, content, category, badge_color, date, time, venue, organizer)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, default_announcements)

    conn.commit()
    conn.close()


# Ensure DB initialized on module load
init_db()


def get_request_data():
    """Safely extracts JSON or form data without raising 415 error."""
    try:
        if request.is_json:
            return request.get_json(silent=True) or {}
    except Exception:
        pass
    return request.form.to_dict() if request.form else {}


# ==============================================================================
# AUTHENTICATION & ROUTE PROTECTION HELPERS
# ==============================================================================

def login_required(allowed_roles=None):
    """Decorator ensuring user is authenticated and matches required role."""
    def decorator(f):
        @wraps(f)
        def decorated_function(*args, **kwargs):
            is_api = request.path.startswith('/api/') or request.is_json or request.headers.get("X-Requested-With") == "XMLHttpRequest"
            
            if 'user' not in session:
                if is_api:
                    return jsonify({"error": "Authentication required. Please log in as Administrator."}), 401
                return redirect(url_for('login_page', next=request.path))
            
            if allowed_roles:
                user_role = session.get('role', 'Student')
                if user_role not in allowed_roles:
                    if is_api:
                        return jsonify({"error": f"Access restricted. Role '{user_role}' cannot access this resource."}), 403
                    flash(f"Access restricted. Role '{user_role}' cannot access this portal.", "error")
                    if user_role == 'Admin':
                        return redirect(url_for('admin_dashboard'))
                    return redirect(url_for('student_dashboard'))
            return f(*args, **kwargs)
        return decorated_function
    return decorator


# ==============================================================================
# SMART PROBLEM ALLOCATION ENGINE
# ==============================================================================

def allocate_smart_worker(category):
    """
    Queries available workers from database by requested category,
    automatically picks the solver with the HIGHEST rating and tasks solved.
    """
    conn = get_db()
    cursor = conn.cursor()
    cat_lower = category.strip().lower()

    # Query matching category workers
    cursor.execute("""
        SELECT * FROM workers 
        WHERE LOWER(category) = ? OR LOWER(category) LIKE ?
        ORDER BY rating DESC, tasks_solved DESC
    """, (cat_lower, f"%{cat_lower}%"))
    candidates = cursor.fetchall()

    if not candidates:
        cursor.execute("SELECT * FROM workers ORDER BY rating DESC, tasks_solved DESC")
        candidates = cursor.fetchall()

    if not candidates:
        conn.close()
        return None

    selected = dict(candidates[0])
    
    # Increment tasks_solved count
    cursor.execute("UPDATE workers SET tasks_solved = tasks_solved + 1 WHERE id = ?", (selected["id"],))
    conn.commit()
    conn.close()
    
    selected["tasks_solved"] += 1
    return selected


# ==============================================================================
# WEB VIEWS & AUTHENTICATION ROUTES
# ==============================================================================

@app.route("/login", methods=["GET", "POST"])
def login_page():
    """Domain-restricted authentication page with strict user lookup and password hash verification."""
    if request.method == "POST":
        data = get_request_data()
        email = data.get("email", "").strip().lower()
        password = data.get("password", "").strip()
        role = data.get("role", "Student").strip()

        # 1. STRICT DOMAIN VALIDATION: Only @sst.scaler.com allowed
        if not email.endswith("@sst.scaler.com") or "@" not in email:
            error_msg = "Access restricted! Only @sst.scaler.com email addresses are authorized."
            if request.headers.get("X-Requested-With") == "XMLHttpRequest" or request.is_json:
                return jsonify({"error": error_msg}), 400
            return render_template("login.html", error=error_msg, email=email, role=role), 400

        # 2. USER LOOKUP IN DATABASE
        conn = get_db()
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM users WHERE LOWER(email) = ?", (email,))
        user_row = cursor.fetchone()
        conn.close()

        # REJECT UNREGISTERED USERS (Do NOT create fallback users)
        if not user_row:
            error_msg = "Invalid email or password."
            if request.headers.get("X-Requested-With") == "XMLHttpRequest" or request.is_json:
                return jsonify({"error": error_msg}), 401
            return render_template("login.html", error=error_msg, email=email, role=role), 401

        user = dict(user_row)

        # 3. PASSWORD VERIFICATION AGAINST STORED HASH
        if not check_password_hash(user["password_hash"], password):
            error_msg = "Invalid email or password."
            if request.headers.get("X-Requested-With") == "XMLHttpRequest" or request.is_json:
                return jsonify({"error": error_msg}), 401
            return render_template("login.html", error=error_msg, email=email, role=role), 401

        # 4. CHECK IF ACCOUNT IS ACTIVE
        if user.get("is_active", 1) == 0:
            error_msg = "Account is deactivated. Please contact campus administration."
            if request.headers.get("X-Requested-With") == "XMLHttpRequest" or request.is_json:
                return jsonify({"error": error_msg}), 403
            return render_template("login.html", error=error_msg, email=email, role=role), 403

        # 5. SUCCESSFUL AUTHENTICATION -> POPULATE SESSION
        session["user"] = user["email"]
        session["email"] = user["email"]
        session["name"] = user["name"]
        session["role"] = user["role"]
        session["student_id"] = user.get("student_id", "SST-2023-CS042")
        session["reputation"] = user.get("reputation", 4.7)
        session["reputation_points"] = user.get("reputation_points", 94)
        session["badge"] = user.get("badge", "Tech Support Pro")

        if request.headers.get("X-Requested-With") == "XMLHttpRequest" or request.is_json:
            redirect_url = url_for("admin_dashboard") if user["role"] == "Admin" else url_for("student_dashboard")
            return jsonify({"success": True, "redirect": redirect_url}), 200

        if user["role"] == "Admin":
            return redirect(url_for("admin_dashboard"))
        return redirect(url_for("student_dashboard"))

    # If already logged in, redirect to respective dashboard
    if "user" in session:
        if session.get("role") == "Admin":
            return redirect(url_for("admin_dashboard"))
        return redirect(url_for("student_dashboard"))

    return render_template("login.html")



@app.route("/logout", methods=["GET", "POST"])
def logout():
    """Clears user session and redirects to login."""
    session.clear()
    flash("You have been successfully logged out.", "info")
    return redirect(url_for("login_page"))


@app.route("/")
@login_required()
def student_dashboard():
    """Main Student Dashboard view."""
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM users WHERE LOWER(email) = ?", (session.get("email", "sameer.verma@sst.scaler.com").lower(),))
    user_row = cursor.fetchone()
    conn.close()

    if user_row:
        user = dict(user_row)
        session["reputation"] = user.get("reputation", 4.7)
        session["reputation_points"] = user.get("reputation_points", 94)
        session["badge"] = user.get("badge", "Tech Support Pro")

    return render_template("index.html", user=session)


@app.route("/admin")
@login_required(allowed_roles=["Admin"])
def admin_dashboard():
    """Admin Hub with CCTV Damage Review, Worker Management CRUD, and Review Log."""
    return render_template("admin.html", user=session)


# ==============================================================================
# REST API ENDPOINTS
# ==============================================================================

@app.route("/api/student/profile", methods=["GET"])
def get_student_profile():
    """Fetch student profile, fine amount, and standing status from Users table."""
    conn = get_db()
    cursor = conn.cursor()
    email = session.get("email", "sameer.verma@sst.scaler.com").lower()
    cursor.execute("SELECT * FROM users WHERE LOWER(email) = ? OR role = 'Student' LIMIT 1", (email,))
    row = cursor.fetchone()
    conn.close()

    if row:
        user = dict(row)
        return jsonify({
            "id": f"STU-{user['id']}",
            "name": user["name"],
            "email": user["email"],
            "roll": user.get("student_id", "SST-2023-CS042"),
            "student_id": user.get("student_id", "SST-2023-CS042"),
            "department": "Computer Science & AI",
            "room": "Hostel Block B, Room 204",
            "status": user.get("status", "Good Standing 🟢"),
            "fine_amount": user.get("fine_amount", 0),
            "reputation": user.get("reputation", 4.7),
            "reputation_points": user.get("reputation_points", 94),
            "badge": user.get("badge", "Tech Support Pro"),
            "fine_history": []
        })
    return jsonify({"error": "Student profile not found."}), 404


@app.route("/api/report-problem", methods=["POST"])
@app.route("/api/tickets", methods=["POST"])
def report_problem():
    """
    Submitting a problem runs the smart allocation engine,
    picks the solver with the highest rating for that category,
    and inserts into the Tickets table.
    """
    data = get_request_data()
    location = str(data.get("location", "Campus")).strip()
    category = str(data.get("category", "Electrical")).strip()
    description = str(data.get("description", "")).strip()
    urgency = str(data.get("urgency", "High")).strip()
    title = str(data.get("title", f"{category} Issue at {location}")).strip()
    reporter_name = session.get("name", "Sameer Verma")

    if not location or not category:
        return jsonify({"error": "Location and category are required."}), 400

    # Smart Worker Allocation
    allocated_worker = allocate_smart_worker(category)

    if allocated_worker:
        solver_id = allocated_worker["id"]
        solver_name = allocated_worker["name"]
        solver_rating = float(allocated_worker["rating"])
        solver_display = f"Assigned to: {solver_name} (⭐ {solver_rating})"
    else:
        solver_id = None
        solver_name = "Unassigned"
        solver_rating = 5.0
        solver_display = "Pending Assignment"

    conn = get_db()
    cursor = conn.cursor()
    cursor.execute("SELECT COUNT(*) FROM tickets")
    count = cursor.fetchone()[0]
    ticket_id = f"TCK-{1001 + count}"

    cursor.execute("""
        INSERT INTO tickets (id, title, category, location, urgency, description, reporter_name, reported_at, status, assigned_worker, solver_id, solver_name, solver_rating, solver_display, rated)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, 'Assigned', ?, ?, ?, ?, ?, 0)
    """, (ticket_id, title, category, location, urgency, description or f"Reported issue in {category} department.", reporter_name, "Just now", solver_name, solver_id, solver_name, solver_rating, solver_display))
    conn.commit()

    cursor.execute("SELECT * FROM tickets WHERE id = ?", (ticket_id,))
    new_ticket = dict(cursor.fetchone())
    conn.close()

    return jsonify({
        "message": f"Problem reported! {solver_display}",
        "solver_display": solver_display,
        "ticket": new_ticket
    }), 201


@app.route("/api/tickets/<ticket_id>/resolve", methods=["POST", "PUT"])
@app.route("/api/resolve-ticket", methods=["POST", "PUT"])
@login_required(allowed_roles=["Admin"])
def resolve_ticket(ticket_id=None):
    """Marks a ticket as Resolved in the Tickets table."""
    data = get_request_data()
    t_id = ticket_id or data.get("ticket_id")

    conn = get_db()
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM tickets WHERE id = ?", (t_id,))
    target = cursor.fetchone()

    if not target:
        conn.close()
        return jsonify({"error": "Ticket not found."}), 404

    cursor.execute("UPDATE tickets SET status = 'Resolved' WHERE id = ?", (t_id,))
    conn.commit()
    cursor.execute("SELECT * FROM tickets WHERE id = ?", (t_id,))
    updated = dict(cursor.fetchone())
    conn.close()

    return jsonify({
        "message": f"Ticket {t_id} marked as Resolved.",
        "ticket": updated
    }), 200


@app.route("/api/submit-rating", methods=["POST"])
def submit_rating():
    """
    POST /api/submit-rating:
    Averages score, recalculates assigned worker's cumulative rating in Workers table,
    awards +5 Reputation Points to reporting student in Users table,
    and inserts the review into the Reviews table.
    """
    data = get_request_data()
    ticket_id = str(data.get("ticket_id", "")).strip()
    response_time = float(data.get("response_time", 5))
    quality = float(data.get("quality", 5))
    behavior = float(data.get("behavior", 5))
    suggestion = str(data.get("suggestion", "")).strip()

    avg_rating = round((response_time + quality + behavior) / 3.0, 2)

    conn = get_db()
    cursor = conn.cursor()

    # Query Ticket
    cursor.execute("SELECT * FROM tickets WHERE id = ?", (ticket_id,))
    ticket_row = cursor.fetchone()
    ticket = dict(ticket_row) if ticket_row else {}

    solver_name = data.get("solver_name") or ticket.get("solver_name") or "Ravi"
    solver_id = data.get("worker_id") or ticket.get("solver_id")
    worker_category = data.get("category") or ticket.get("category") or "General"

    # Locate Worker
    cursor.execute("SELECT * FROM workers WHERE id = ? OR LOWER(name) = LOWER(?) LIMIT 1", (solver_id, solver_name))
    worker_row = cursor.fetchone()
    worker = dict(worker_row) if worker_row else None

    # Recalculate Worker Cumulative Rating
    if worker:
        tasks_count = int(worker.get("tasks_solved", 0))
        current_rating = float(worker.get("rating", 5.0))
        new_rating = round(((current_rating * max(1, tasks_count)) + avg_rating) / (max(1, tasks_count) + 1), 2)
        new_rating = min(5.0, max(1.0, new_rating))

        cursor.execute("""
            UPDATE workers SET rating = ?, tasks_solved = tasks_solved + 1 WHERE id = ?
        """, (new_rating, worker["id"]))
        worker["rating"] = new_rating
        worker["tasks_solved"] = tasks_count + 1
        solver_name = worker["name"]
        solver_id = worker["id"]
        worker_category = worker["category"]

    # Award +5 Reputation Points to student in Users table
    email = session.get("email", "sameer.verma@sst.scaler.com").lower()
    cursor.execute("""
        UPDATE users 
        SET reputation_points = reputation_points + 5,
            reputation = MIN(5.0, ROUND(reputation + 0.05, 2))
        WHERE LOWER(email) = ? OR role = 'Student'
    """, (email,))

    # Update Ticket
    if ticket:
        cursor.execute("""
            UPDATE tickets 
            SET status = 'Resolved', rated = 1, rating_score = ?
            WHERE id = ?
        """, (avg_rating, ticket_id))

    # Insert into Reviews Table
    cursor.execute("SELECT COUNT(*) FROM reviews")
    rev_count = cursor.fetchone()[0]
    rev_id = f"REV-{501 + rev_count}"

    student_name = session.get("name", "Sameer Verma")
    student_roll = session.get("student_id", "SST-2023-CS042")
    timestamp = datetime.now().strftime("%I:%M %p, %d %b %Y")

    cursor.execute("""
        INSERT INTO reviews (id, ticket_id, worker_id, rating, suggestion, student_name, student_roll, worker_name, worker_category, response_time, quality, behavior, timestamp)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
    """, (rev_id, ticket_id or "TCK-1000", solver_id or "WKR-01", avg_rating, suggestion or "No specific suggestion provided. Great service.", student_name, student_roll, solver_name, worker_category, int(response_time), int(quality), int(behavior), timestamp))

    conn.commit()

    # Query updated student data
    cursor.execute("SELECT * FROM users WHERE LOWER(email) = ? OR role = 'Student' LIMIT 1", (email,))
    updated_user = dict(cursor.fetchone())
    conn.close()

    session["reputation"] = updated_user["reputation"]
    session["reputation_points"] = updated_user["reputation_points"]

    return jsonify({
        "message": f"Review submitted! +5 Reputation Points awarded. Worker {solver_name}'s rating updated to ⭐ {worker['rating'] if worker else avg_rating}.",
        "avg_rating": avg_rating,
        "reputation_points": updated_user["reputation_points"],
        "student_reputation": updated_user["reputation"],
        "worker": worker,
        "review": {
            "id": rev_id,
            "ticket_id": ticket_id,
            "worker_id": solver_id,
            "worker_name": solver_name,
            "student_name": student_name,
            "avg_rating": avg_rating,
            "suggestion": suggestion
        }
    }), 200


@app.route("/api/reviews", methods=["GET"])
def get_worker_reviews():
    """Retrieve all student service reviews from the Reviews table."""
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM reviews ORDER BY rowid DESC")
    rows = [dict(r) for r in cursor.fetchall()]
    conn.close()
    return jsonify(rows)


@app.route("/api/issue-fine", methods=["POST"])
@app.route("/api/student/issue-fine", methods=["POST"])
@login_required(allowed_roles=["Admin"])
def issue_cctv_fine():
    """Applies ₹500 fine and updates student standing to Action Required in Users table."""
    data = get_request_data()
    amount = int(data.get("amount", 500))
    reason = str(data.get("reason", "Classroom 204 — 3:20 PM - Damaged Chair")).strip()

    conn = get_db()
    cursor = conn.cursor()
    cursor.execute("""
        UPDATE users 
        SET fine_amount = fine_amount + ?, status = 'Action Required 🔴'
        WHERE role = 'Student'
    """, (amount,))
    conn.commit()

    cursor.execute("SELECT * FROM users WHERE role = 'Student' LIMIT 1")
    user = dict(cursor.fetchone())
    conn.close()

    return jsonify({
        "message": f"₹{amount} fine successfully issued to {user['name']}! Status changed to 'Action Required 🔴'.",
        "student": {
            "name": user["name"],
            "status": user["status"],
            "fine_amount": user["fine_amount"]
        }
    }), 200


@app.route("/api/student/pay-fine", methods=["POST"])
def pay_student_fine():
    """Clears fine and restores status to Good Standing 🟢 in Users table."""
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute("""
        UPDATE users 
        SET fine_amount = 0, status = 'Good Standing 🟢'
        WHERE role = 'Student'
    """)
    conn.commit()

    cursor.execute("SELECT * FROM users WHERE role = 'Student' LIMIT 1")
    user = dict(cursor.fetchone())
    conn.close()

    return jsonify({
        "message": "Fine cleared successfully. Status updated to 'Good Standing 🟢'.",
        "student": {
            "name": user["name"],
            "status": user["status"],
            "fine_amount": user["fine_amount"]
        }
    })


@app.route("/api/events/book", methods=["POST"])
@app.route("/api/book-event", methods=["POST"])
def book_event():
    """
    Checks venue and time clash against Events table.
    If booked, returns 409: ⚠️ TIME CLASH DETECTED: [Venue] is already booked
    """
    data = get_request_data()
    name = str(data.get("name", "")).strip()
    venue = str(data.get("venue", "")).strip()
    date = str(data.get("date", "Today")).strip()
    start_time = str(data.get("start_time", "")).strip()
    end_time = str(data.get("end_time", "")).strip()
    organizer = session.get("name", "Student Council")

    if not name or not venue:
        return jsonify({"error": "Event name and venue are required."}), 400

    def parse_time_mins(t_str):
        try:
            parts = t_str.strip().split(":")
            return int(parts[0]) * 60 + int(parts[1])
        except Exception:
            return 0

    new_start = parse_time_mins(start_time) if start_time else 0
    new_end = parse_time_mins(end_time) if end_time else 1440
    venue_lower = venue.lower()

    conn = get_db()
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM events")
    all_events = [dict(e) for e in cursor.fetchall()]

    for event in all_events:
        evt_loc = event.get("venue", "").lower()

        venue_match = (
            ("auditorium" in venue_lower and "auditorium" in evt_loc) or
            ("sports" in venue_lower and "sports" in evt_loc) or
            ("seminar" in venue_lower and "seminar" in evt_loc) or
            ("exam" in venue_lower and "exam" in evt_loc) or
            (venue_lower in evt_loc) or (evt_loc in venue_lower)
        )

        date_match = (
            event.get("date", "").lower() == date.lower() or
            (event.get("date", "").lower() in ["today", "aug 22"] and date.lower() in ["today", "aug 22"])
        )

        if venue_match and date_match:
            evt_start = parse_time_mins(event.get("start_time", "00:00"))
            evt_end = parse_time_mins(event.get("end_time", "23:59"))

            if (not start_time and not end_time) or (new_start < evt_end and new_end > evt_start):
                conn.close()
                venue_display = "Auditorium" if "auditorium" in venue_lower else venue
                clash_text = f"⚠️ TIME CLASH DETECTED: {venue_display} is already booked"
                return jsonify({
                    "clash": True,
                    "error": clash_text,
                    "message": clash_text,
                    "conflicting_event": event
                }), 409

    cursor.execute("SELECT COUNT(*) FROM events")
    count = cursor.fetchone()[0]
    evt_id = f"EVT-{101 + count}"

    cursor.execute("""
        INSERT INTO events (id, name, organizer, venue, date, start_time, end_time, description)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?)
    """, (evt_id, name, organizer, venue, date, start_time or "09:00", end_time or "17:00", f"Booked by {organizer}"))
    conn.commit()

    cursor.execute("SELECT * FROM events WHERE id = ?", (evt_id,))
    new_event = dict(cursor.fetchone())
    conn.close()

    return jsonify({
        "clash": False,
        "message": f"Venue '{venue}' successfully booked for '{name}'!",
        "event": new_event
    }), 201


# ==============================================================================
# WORKER MANAGEMENT (CRUD) ENDPOINTS
# ==============================================================================

@app.route("/api/workers", methods=["GET"])
def list_workers():
    """Retrieve all workers from Workers table."""
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM workers ORDER BY rating DESC, tasks_solved DESC")
    rows = [dict(r) for r in cursor.fetchall()]
    conn.close()
    return jsonify(rows)


@app.route("/api/workers", methods=["POST"])
@login_required(allowed_roles=["Admin"])
def add_worker():
    """Adds a new worker to Workers table (defaults to ⭐ 5.0 rating, 0 solved)."""
    data = get_request_data()
    name = str(data.get("name", "")).strip()
    category = str(data.get("category", "General")).strip()

    if not name:
        return jsonify({"error": "Worker Name is required."}), 400

    conn = get_db()
    cursor = conn.cursor()
    cursor.execute("SELECT COUNT(*) FROM workers")
    count = cursor.fetchone()[0]
    worker_id = f"WKR-{str(count + 1).zfill(2)}"

    cursor.execute("""
        INSERT INTO workers (id, name, category, rating, tasks_solved, phone, email)
        VALUES (?, ?, ?, 5.0, 0, '+91 98765 00000', ?)
    """, (worker_id, name, category, f"{name.lower().replace(' ', '.')}@sst.scaler.com"))
    conn.commit()

    cursor.execute("SELECT * FROM workers WHERE id = ?", (worker_id,))
    new_worker = dict(cursor.fetchone())
    conn.close()

    return jsonify({
        "message": f"Worker '{name}' ({category}) added with ⭐ 5.0 rating!",
        "worker": new_worker
    }), 201


@app.route("/api/workers/<worker_id>", methods=["PUT", "POST"])
@login_required(allowed_roles=["Admin"])
def edit_worker(worker_id):
    """Updates an existing worker in Workers table."""
    data = get_request_data()
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM workers WHERE id = ?", (worker_id,))
    target = cursor.fetchone()

    if not target:
        conn.close()
        return jsonify({"error": "Worker not found."}), 404

    name = str(data.get("name", target["name"])).strip()
    category = str(data.get("category", target["category"])).strip()
    try:
        rating = float(data.get("rating", target["rating"]))
    except (ValueError, TypeError):
        rating = target["rating"]

    cursor.execute("""
        UPDATE workers SET name = ?, category = ?, rating = ? WHERE id = ?
    """, (name, category, rating, worker_id))
    conn.commit()

    cursor.execute("SELECT * FROM workers WHERE id = ?", (worker_id,))
    updated = dict(cursor.fetchone())
    conn.close()

    return jsonify({
        "message": f"Worker {worker_id} updated successfully!",
        "worker": updated
    }), 200


@app.route("/api/workers/<worker_id>", methods=["DELETE"])
@login_required(allowed_roles=["Admin"])
def delete_worker(worker_id):
    """Deletes a worker from Workers table."""
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute("DELETE FROM workers WHERE id = ?", (worker_id,))
    deleted_count = cursor.rowcount
    conn.commit()
    conn.close()

    if deleted_count > 0:
        return jsonify({"message": f"Worker {worker_id} deleted."}), 200
    return jsonify({"error": "Worker not found."}), 404


# ==============================================================================
# ADMIN USER MANAGEMENT ENDPOINTS
# ==============================================================================

@app.route("/api/admin/users", methods=["GET"])
@login_required(allowed_roles=["Admin"])
def list_admin_users():
    """
    List all registered campus users (excluding password hashes) for Admin Hub.
    """
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute("""
        SELECT id, name, email, role, student_id, is_active, status, fine_amount, reputation, reputation_points, badge 
        FROM users 
        ORDER BY id ASC
    """)
    rows = [dict(r) for r in cursor.fetchall()]
    conn.close()
    return jsonify(rows)


@app.route("/api/admin/users", methods=["POST"])
@login_required(allowed_roles=["Admin"])
def create_admin_user():
    """
    Administrator creates a new user:
    - Name
    - @sst.scaler.com email (strictly validated & uniqueness check)
    - Student/Staff ID
    - Role (Student or Admin)
    - Password (hashed via generate_password_hash)
    """
    data = get_request_data()
    name = str(data.get("name", "")).strip()
    email = str(data.get("email", "")).strip().lower()
    student_id = str(data.get("student_id", "")).strip()
    role = str(data.get("role", "Student")).strip()
    password = str(data.get("password", "")).strip()

    if not name or not email or not password:
        return jsonify({"error": "Name, email, and password are required."}), 400

    # Strict domain validation: strictly ends with @sst.scaler.com
    if not email.endswith("@sst.scaler.com") or "@" not in email:
        return jsonify({"error": "Access restricted! Email must strictly end with @sst.scaler.com"}), 400

    # Role validation
    if role not in ["Student", "Admin"]:
        role = "Student"

    conn = get_db()
    cursor = conn.cursor()

    # Check for duplicate email
    cursor.execute("SELECT id FROM users WHERE LOWER(email) = ?", (email,))
    if cursor.fetchone():
        conn.close()
        return jsonify({"error": "A user with this email address already exists."}), 409

    # Generate secure password hash
    pw_hash = generate_password_hash(password)
    default_badge = "Tech Support Pro" if role == "Student" else "System Overseer"
    assigned_student_id = student_id or f"SST-{datetime.now().year}-CS{str(random.randint(100, 999))}"

    cursor.execute("""
        INSERT INTO users (name, email, password_hash, role, student_id, is_active, status, fine_amount, reputation, reputation_points, badge)
        VALUES (?, ?, ?, ?, ?, 1, 'Good Standing 🟢', 0, 4.7, 94, ?)
    """, (name, email, pw_hash, role, assigned_student_id, default_badge))
    conn.commit()

    user_id = cursor.lastrowid
    cursor.execute("""
        SELECT id, name, email, role, student_id, is_active, status, fine_amount, reputation, reputation_points, badge 
        FROM users WHERE id = ?
    """, (user_id,))
    new_user = dict(cursor.fetchone())
    conn.close()

    return jsonify({
        "message": f"User '{name}' ({email}) successfully created with role '{role}'!",
        "user": new_user
    }), 201


@app.route("/api/admin/users/<int:user_id>/toggle-status", methods=["POST", "PUT"])
@login_required(allowed_roles=["Admin"])
def toggle_admin_user_status(user_id):
    """
    Activates or deactivates a user account (is_active: 1 <-> 0).
    """
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute("SELECT id, name, is_active FROM users WHERE id = ?", (user_id,))
    user = cursor.fetchone()

    if not user:
        conn.close()
        return jsonify({"error": "User not found."}), 404

    current_active = user["is_active"] if user["is_active"] is not None else 1
    new_status = 0 if current_active == 1 else 1
    cursor.execute("UPDATE users SET is_active = ? WHERE id = ?", (new_status, user_id))
    conn.commit()
    conn.close()

    status_label = "Active 🟢" if new_status == 1 else "Deactivated ⛔"
    return jsonify({
        "message": f"User {user['name']} is now {status_label}.",
        "user_id": user_id,
        "is_active": new_status
    }), 200


@app.route("/api/admin/users/<int:user_id>", methods=["DELETE"])
@login_required(allowed_roles=["Admin"])
def delete_admin_user(user_id):
    """
    Deletes a user record from the Users table.
    """
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute("SELECT id, name, email FROM users WHERE id = ?", (user_id,))
    user = cursor.fetchone()

    if not user:
        conn.close()
        return jsonify({"error": "User not found."}), 404

    # Prevent admin from deleting their own active session user
    if user["email"].lower() == session.get("email", "").lower():
        conn.close()
        return jsonify({"error": "You cannot delete your own logged-in administrator account."}), 400

    cursor.execute("DELETE FROM users WHERE id = ?", (user_id,))
    conn.commit()
    conn.close()

    return jsonify({
        "message": f"User {user['name']} ({user['email']}) has been deleted.",
        "user_id": user_id
    }), 200



# ==============================================================================
# GENERAL API ENDPOINTS
# ==============================================================================

@app.route("/api/alerts", methods=["GET"])
def get_alerts():
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM alerts WHERE active = 1")
    rows = [dict(r) for r in cursor.fetchall()]
    conn.close()
    return jsonify(rows)


@app.route("/api/announcements", methods=["GET"])
def get_announcements():
    category = request.args.get("category")
    conn = get_db()
    cursor = conn.cursor()
    if category and category.lower() != "all":
        cursor.execute("SELECT * FROM announcements WHERE LOWER(category) = ?", (category.lower(),))
    else:
        cursor.execute("SELECT * FROM announcements")
    rows = [dict(r) for r in cursor.fetchall()]
    conn.close()
    return jsonify(rows)


@app.route("/api/tickets", methods=["GET"])
def get_tickets():
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM tickets ORDER BY rowid DESC")
    rows = [dict(r) for r in cursor.fetchall()]
    conn.close()
    return jsonify(rows)


@app.route("/api/events", methods=["GET"])
def get_events():
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM events")
    rows = [dict(r) for r in cursor.fetchall()]
    conn.close()
    return jsonify(rows)


@app.route("/api/dashboard/stats", methods=["GET"])
def get_dashboard_stats():
    """Returns summarized stats for dashboard monitoring from SQLite."""
    conn = get_db()
    cursor = conn.cursor()

    cursor.execute("SELECT COUNT(*) FROM tickets")
    total_tickets = cursor.fetchone()[0]

    cursor.execute("SELECT COUNT(*) FROM tickets WHERE status = 'Resolved'")
    resolved_tickets = cursor.fetchone()[0]

    cursor.execute("SELECT COUNT(*) FROM workers")
    active_workers = cursor.fetchone()[0]

    cursor.execute("SELECT COUNT(*) FROM reviews")
    total_reviews = cursor.fetchone()[0]

    cursor.execute("SELECT status, reputation, reputation_points, fine_amount FROM users WHERE role = 'Student' LIMIT 1")
    student = cursor.fetchone()
    conn.close()

    return jsonify({
        "total_tickets": total_tickets,
        "resolved_tickets": resolved_tickets,
        "active_workers": active_workers,
        "total_reviews": total_reviews,
        "student_status": student["status"] if student else "Good Standing 🟢",
        "student_reputation": student["reputation"] if student else 4.7,
        "student_points": student["reputation_points"] if student else 94,
        "pending_fines": student["fine_amount"] if student else 0
    })


if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    print(f"[NextCamp] Production server with SQLite running on http://127.0.0.1:{port}")
    app.run(host="0.0.0.0", port=port, debug=True)
