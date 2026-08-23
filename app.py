import os
import random
import sqlite3
from datetime import datetime, timedelta
from functools import wraps
from flask import Flask, render_template, request, jsonify, redirect, url_for, session, flash
from werkzeug.security import generate_password_hash, check_password_hash

app = Flask(__name__)
app.secret_key = os.environ.get("SECRET_KEY", "nextcamp_secret_key_scaler_sst_2026_prod")
app.config["SESSION_COOKIE_HTTPONLY"] = True
app.config["SESSION_COOKIE_SAMESITE"] = "Lax"
app.config["SESSION_COOKIE_NAME"] = "nextcamp_session"
app.config["PERMANENT_SESSION_LIFETIME"] = timedelta(days=7)
DB_PATH = os.environ.get(
    "NEXTCAMP_DB",
    "/tmp/nextcamp.db" if os.environ.get("VERCEL") else os.path.join(os.path.dirname(__file__), "nextcamp.db")
)


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
            description TEXT,
            capacity INTEGER DEFAULT 100
        )
    """)

    # Ensure capacity column exists if upgrading existing DB
    cursor.execute("PRAGMA table_info(events)")
    event_cols = [col[1] for col in cursor.fetchall()]
    if "capacity" not in event_cols:
        cursor.execute("ALTER TABLE events ADD COLUMN capacity INTEGER DEFAULT 100")

    # 2b. Event Registrations (RSVP) Table
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS event_registrations (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            event_id TEXT NOT NULL,
            user_id INTEGER NOT NULL,
            student_name TEXT NOT NULL,
            student_id TEXT,
            student_email TEXT NOT NULL,
            registered_at TEXT NOT NULL,
            UNIQUE(event_id, user_id),
            FOREIGN KEY(event_id) REFERENCES events(id) ON DELETE CASCADE,
            FOREIGN KEY(user_id) REFERENCES users(id) ON DELETE CASCADE
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
            priority TEXT NOT NULL DEFAULT 'Normal',
            audience TEXT DEFAULT 'All',
            badge_color TEXT,
            date TEXT,
            time TEXT,
            venue TEXT,
            organizer TEXT,
            created_by TEXT,
            created_at TEXT
        )
    """)

    # 6. Fines & Disciplinary Tracking Table
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS fines (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL,
            student_id TEXT,
            student_name TEXT NOT NULL,
            student_email TEXT NOT NULL,
            amount INTEGER NOT NULL,
            reason TEXT NOT NULL,
            status TEXT NOT NULL DEFAULT 'Pending',
            created_at TEXT NOT NULL,
            paid_at TEXT,
            FOREIGN KEY(user_id) REFERENCES users(id) ON DELETE CASCADE
        )
    """)

    # Ensure columns exist if upgrading existing DB
    cursor.execute("PRAGMA table_info(announcements)")
    ann_cols = [col[1] for col in cursor.fetchall()]
    if "priority" not in ann_cols:
        cursor.execute("ALTER TABLE announcements ADD COLUMN priority TEXT DEFAULT 'Normal'")
    if "audience" not in ann_cols:
        cursor.execute("ALTER TABLE announcements ADD COLUMN audience TEXT DEFAULT 'All'")
    if "created_by" not in ann_cols:
        cursor.execute("ALTER TABLE announcements ADD COLUMN created_by TEXT")
    if "created_at" not in ann_cols:
        cursor.execute("ALTER TABLE announcements ADD COLUMN created_at TEXT")

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
            
            if 'user' not in session and 'user_id' not in session:
                if is_api:
                    return jsonify({"error": "Authentication required. Please log in."}), 401
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


def load_authenticated_user_session():
    """Helper that verifies and re-syncs the session against the SQLite database on every page load/refresh."""
    user_id = session.get("user_id")
    email = session.get("email")

    if not user_id and not email:
        return None

    conn = get_db()
    cursor = conn.cursor()
    if user_id:
        cursor.execute("SELECT * FROM users WHERE id = ? AND is_active = 1", (user_id,))
    else:
        cursor.execute("SELECT * FROM users WHERE LOWER(email) = ? AND is_active = 1", (str(email).lower(),))
    row = cursor.fetchone()
    conn.close()

    if not row:
        session.clear()
        return None

    user = dict(row)
    session.permanent = True
    session["user_id"] = user["id"]
    session["user"] = user["email"]
    session["email"] = user["email"]
    session["name"] = user["name"]
    session["role"] = user["role"]
    session["student_id"] = user.get("student_id", "")
    session["reputation"] = user.get("reputation", 4.7)
    session["reputation_points"] = user.get("reputation_points", 94)
    session["badge"] = user.get("badge", "Tech Support Pro")
    session["status"] = user.get("status", "Good Standing 🟢")
    session["fine_amount"] = user.get("fine_amount", 0)
    return user


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
        session.clear()
        session.permanent = True
        session["user_id"] = user["id"]
        session["user"] = user["email"]
        session["email"] = user["email"]
        session["name"] = user["name"]
        session["role"] = user["role"]
        session["student_id"] = user.get("student_id", "")
        session["reputation"] = user.get("reputation", 4.7)
        session["reputation_points"] = user.get("reputation_points", 94)
        session["badge"] = user.get("badge", "Tech Support Pro")
        session["status"] = user.get("status", "Good Standing 🟢")
        session["fine_amount"] = user.get("fine_amount", 0)

        if request.headers.get("X-Requested-With") == "XMLHttpRequest" or request.is_json:
            redirect_url = url_for("admin_dashboard") if user["role"] == "Admin" else url_for("student_dashboard")
            return jsonify({"success": True, "redirect": redirect_url}), 200

        if user["role"] == "Admin":
            return redirect(url_for("admin_dashboard"))
        return redirect(url_for("student_dashboard"))

    # If already logged in, redirect to respective dashboard
    if "user" in session or "user_id" in session:
        user = load_authenticated_user_session()
        if user:
            if user.get("role") == "Admin":
                return redirect(url_for("admin_dashboard"))
            return redirect(url_for("student_dashboard"))

    return render_template("login.html")



@app.route("/logout", methods=["GET", "POST"])
def logout():
    """Clears user session and redirects to login."""
    session.clear()
    flash("You have been successfully logged out.", "info")
    return redirect(url_for("login_page"))


@app.route("/dashboard")
@app.route("/")
@login_required()
def student_dashboard():
    """Main Student Dashboard view."""
    user = load_authenticated_user_session()
    if not user:
        return redirect(url_for("login_page"))
    if user.get("role") == "Admin":
        return redirect(url_for("admin_dashboard"))
    return render_template("index.html", user=session, active_tab="dashboard")


@app.route("/announcements")
@login_required()
def student_announcements():
    """Dedicated Student Announcements View."""
    user = load_authenticated_user_session()
    if not user:
        return redirect(url_for("login_page"))
    if user.get("role") == "Admin":
        return redirect(url_for("admin_dashboard"))
    return render_template("index.html", user=session, active_tab="announcements")


@app.route("/events")
@login_required()
def student_events():
    """Dedicated Student Events View."""
    user = load_authenticated_user_session()
    if not user:
        return redirect(url_for("login_page"))
    if user.get("role") == "Admin":
        return redirect(url_for("admin_dashboard"))
    return render_template("index.html", user=session, active_tab="events")


@app.route("/registrations")
@login_required()
def student_registrations():
    """Dedicated Student Event Registrations View."""
    user = load_authenticated_user_session()
    if not user:
        return redirect(url_for("login_page"))
    if user.get("role") == "Admin":
        return redirect(url_for("admin_dashboard"))
    return render_template("index.html", user=session, active_tab="registrations")


@app.route("/tickets")
@login_required()
def student_tickets():
    """Dedicated Student Problem Tickets View."""
    user = load_authenticated_user_session()
    if not user:
        return redirect(url_for("login_page"))
    if user.get("role") == "Admin":
        return redirect(url_for("admin_dashboard"))
    return render_template("index.html", user=session, active_tab="tickets")


@app.route("/profile")
@login_required()
def student_profile():
    """Dedicated Student Profile View."""
    user = load_authenticated_user_session()
    if not user:
        return redirect(url_for("login_page"))
    if user.get("role") == "Admin":
        return redirect(url_for("admin_dashboard"))
    return render_template("index.html", user=session, active_tab="profile")


@app.route("/admin/dashboard")
@app.route("/admin")
@login_required(allowed_roles=["Admin"])
def admin_dashboard():
    """Admin Hub with CCTV Damage Review, Worker Management CRUD, and Review Log."""
    user = load_authenticated_user_session()
    if not user or user.get("role") != "Admin":
        return redirect(url_for("login_page"))
    return render_template("admin.html", user=session, active_tab="dashboard")


@app.route("/admin/announcements")
@login_required(allowed_roles=["Admin"])
def admin_announcements():
    """Dedicated Admin Announcements & Broadcast View."""
    user = load_authenticated_user_session()
    if not user or user.get("role") != "Admin":
        return redirect(url_for("login_page"))
    return render_template("admin.html", user=session, active_tab="announcements")


@app.route("/admin/events")
@login_required(allowed_roles=["Admin"])
def admin_events():
    """Dedicated Admin Events & RSVP Roster View."""
    user = load_authenticated_user_session()
    if not user or user.get("role") != "Admin":
        return redirect(url_for("login_page"))
    return render_template("admin.html", user=session, active_tab="events")


@app.route("/admin/users")
@login_required(allowed_roles=["Admin"])
def admin_users():
    """Dedicated Admin User Management View."""
    user = load_authenticated_user_session()
    if not user or user.get("role") != "Admin":
        return redirect(url_for("login_page"))
    return render_template("admin.html", user=session, active_tab="users")


@app.route("/admin/tickets")
@login_required(allowed_roles=["Admin"])
def admin_tickets():
    """Dedicated Admin Problem Tickets & Worker Directory View."""
    user = load_authenticated_user_session()
    if not user or user.get("role") != "Admin":
        return redirect(url_for("login_page"))
    return render_template("admin.html", user=session, active_tab="tickets")


@app.route("/admin/profile")
@login_required(allowed_roles=["Admin"])
def admin_profile():
    """Dedicated Admin Profile & Permissions View."""
    user = load_authenticated_user_session()
    if not user or user.get("role") != "Admin":
        return redirect(url_for("login_page"))
    return render_template("admin.html", user=session, active_tab="profile")


# ==============================================================================
# REST API ENDPOINTS
# ==============================================================================

@app.route("/api/student/profile", methods=["GET"])
@login_required()
def get_student_profile():
    """Fetch student profile, fine amount, standing status, and fine history from SQLite."""
    conn = get_db()
    cursor = conn.cursor()
    user_id = session.get("user_id")
    role = session.get("role")
    email = session.get("email")

    target_user_id = request.args.get("user_id")
    if role == "Admin" and target_user_id:
        cursor.execute("SELECT * FROM users WHERE id = ?", (target_user_id,))
    elif role == "Admin":
        cursor.execute("SELECT * FROM users WHERE role = 'Student' ORDER BY id ASC LIMIT 1")
    elif role == "Student" and user_id:
        cursor.execute("SELECT * FROM users WHERE id = ?", (user_id,))
    elif role == "Student" and email:
        cursor.execute("SELECT * FROM users WHERE LOWER(email) = ?", (str(email).lower(),))
    elif user_id:
        cursor.execute("SELECT * FROM users WHERE id = ?", (user_id,))
    elif email:
        cursor.execute("SELECT * FROM users WHERE LOWER(email) = ?", (str(email).lower(),))
    else:
        conn.close()
        return jsonify({"error": "Authentication required. Please log in."}), 401

    row = cursor.fetchone()

    if not row:
        conn.close()
        return jsonify({"error": "Student profile not found."}), 404

    user = dict(row)
    # Fetch real fines from fines table for this student
    cursor.execute("SELECT * FROM fines WHERE user_id = ? ORDER BY id DESC", (user["id"],))
    fine_rows = [dict(r) for r in cursor.fetchall()]
    conn.close()

    fines = []
    for f in fine_rows:
        f_copy = dict(f)
        f_copy["fine_id"] = f"FINE-{f['id']:03d}"
        f_copy["date_assigned"] = f.get("created_at")
        fines.append(f_copy)

    pending_fines = [f for f in fines if f.get("status") == "Pending"]
    latest_pending = pending_fines[0] if pending_fines else None

    return jsonify({
        "id": f"STU-{user['id']}",
        "user_id": user["id"],
        "name": user["name"],
        "email": user["email"],
        "roll": user.get("student_id", ""),
        "student_id": user.get("student_id", ""),
        "department": "Computer Science & AI",
        "room": "Hostel Block B, Room 204",
        "status": user.get("status", "Good Standing 🟢"),
        "fine_amount": user.get("fine_amount", 0),
        "reputation": user.get("reputation", 4.7),
        "reputation_points": user.get("reputation_points", 94),
        "badge": user.get("badge", "Tech Support Pro"),
        "fine_history": fines,
        "current_pending_fine": latest_pending,
        "total_fines": len(fines),
        "total_pending_amount": sum(f["amount"] for f in pending_fines),
        "total_paid_amount": sum(f["amount"] for f in fines if f.get("status") == "Paid")
    })


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

    reporter_name = session.get("name")
    if not reporter_name and session.get("user_id"):
        conn = get_db()
        cursor = conn.cursor()
        cursor.execute("SELECT name FROM users WHERE id = ?", (session["user_id"],))
        u = cursor.fetchone()
        conn.close()
        if u:
            reporter_name = u["name"]
    if not reporter_name:
        reporter_name = "Student User"

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

    # Award +5 Reputation Points to authenticated student in Users table
    user_id = session.get("user_id")
    email = session.get("email")

    if user_id:
        cursor.execute("""
            UPDATE users 
            SET reputation_points = reputation_points + 5,
                reputation = MIN(5.0, ROUND(reputation + 0.05, 2))
            WHERE id = ?
        """, (user_id,))
    elif email:
        cursor.execute("""
            UPDATE users 
            SET reputation_points = reputation_points + 5,
                reputation = MIN(5.0, ROUND(reputation + 0.05, 2))
            WHERE LOWER(email) = ?
        """, (str(email).lower(),))
    else:
        cursor.execute("""
            UPDATE users 
            SET reputation_points = reputation_points + 5,
                reputation = MIN(5.0, ROUND(reputation + 0.05, 2))
            WHERE role = 'Student'
        """)

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

    student_name = session.get("name")
    student_roll = session.get("student_id")
    timestamp = datetime.now().strftime("%I:%M %p, %d %b %Y")

    # Fetch user if name or roll missing in session
    if user_id:
        cursor.execute("SELECT * FROM users WHERE id = ?", (user_id,))
    elif email:
        cursor.execute("SELECT * FROM users WHERE LOWER(email) = ?", (str(email).lower(),))
    else:
        cursor.execute("SELECT * FROM users WHERE role = 'Student' ORDER BY id ASC LIMIT 1")
    updated_user_row = cursor.fetchone()
    updated_user = dict(updated_user_row) if updated_user_row else {"reputation": 4.75, "reputation_points": 99}

    if not student_name:
        student_name = updated_user.get("name", "Student User")
    if not student_roll:
        student_roll = updated_user.get("student_id", "")

    cursor.execute("""
        INSERT INTO reviews (id, ticket_id, worker_id, rating, suggestion, student_name, student_roll, worker_name, worker_category, response_time, quality, behavior, timestamp)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
    """, (rev_id, ticket_id or "TCK-1000", solver_id or "WKR-01", avg_rating, suggestion or "No specific suggestion provided. Great service.", student_name, student_roll, solver_name, worker_category, int(response_time), int(quality), int(behavior), timestamp))

    conn.commit()
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


# ==============================================================================
# FINE MANAGEMENT & FINE HISTORY ENDPOINTS (ADMIN & STUDENT)
# ==============================================================================

@app.route("/api/admin/students", methods=["GET"])
@login_required(allowed_roles=["Admin"])
def get_admin_students():
    """Returns list of student users for fine assignment and history selection."""
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute("""
        SELECT id, name, email, student_id, is_active, status, fine_amount, reputation, reputation_points, badge
        FROM users
        WHERE role = 'Student'
        ORDER BY name ASC
    """)
    students = [dict(r) for r in cursor.fetchall()]
    conn.close()
    return jsonify(students), 200


@app.route("/api/admin/fines", methods=["POST"])
@app.route("/api/issue-fine", methods=["POST"])
@app.route("/api/student/issue-fine", methods=["POST"])
@login_required(allowed_roles=["Admin"])
def issue_fine():
    """
    Admin assigns a fine to a selected student.
    Stores fine in SQLite fines table, updates student's fine_amount and sets status to 'Action Required 🔴'.
    """
    data = get_request_data()
    try:
        amount = int(data.get("amount", 500))
    except (ValueError, TypeError):
        return jsonify({"error": "Fine amount must be a valid positive integer."}), 400

    if amount <= 0:
        return jsonify({"error": "Fine amount must be greater than zero."}), 400

    reason = str(data.get("reason", "Classroom 204 — 3:20 PM - Damaged Chair")).strip()
    if not reason:
        reason = "Administrative campus disciplinary fine"

    conn = get_db()
    cursor = conn.cursor()

    # Look up target student
    user_row = None
    target_user_id = data.get("user_id")
    target_student_id = data.get("student_id")
    target_email = data.get("email")

    if target_user_id:
        cursor.execute("SELECT * FROM users WHERE id = ?", (target_user_id,))
        user_row = cursor.fetchone()
    elif target_student_id:
        cursor.execute("SELECT * FROM users WHERE student_id = ?", (target_student_id,))
        user_row = cursor.fetchone()
    elif target_email:
        cursor.execute("SELECT * FROM users WHERE LOWER(email) = ?", (str(target_email).lower(),))
        user_row = cursor.fetchone()

    if not user_row:
        # Fallback to first student in database
        cursor.execute("SELECT * FROM users WHERE role = 'Student' LIMIT 1")
        user_row = cursor.fetchone()

    if not user_row:
        conn.close()
        return jsonify({"error": "Target student not found in campus database."}), 404

    user = dict(user_row)
    now_str = datetime.now().strftime("%Y-%m-%d %H:%M")

    # Insert into fines table
    cursor.execute("""
        INSERT INTO fines (user_id, student_id, student_name, student_email, amount, reason, status, created_at, paid_at)
        VALUES (?, ?, ?, ?, ?, ?, 'Pending', ?, NULL)
    """, (
        user["id"],
        user.get("student_id", "SST-2023-CS042"),
        user["name"],
        user["email"],
        amount,
        reason,
        now_str
    ))
    fine_id = cursor.lastrowid

    # Update student's fine amount and standing
    cursor.execute("""
        UPDATE users 
        SET fine_amount = fine_amount + ?, status = 'Action Required 🔴'
        WHERE id = ?
    """, (amount, user["id"]))
    conn.commit()

    cursor.execute("SELECT * FROM users WHERE id = ?", (user["id"],))
    updated_user = dict(cursor.fetchone())
    conn.close()

    fine_dict = {
        "id": fine_id,
        "fine_id": f"FINE-{fine_id:03d}",
        "user_id": user["id"],
        "student_id": user.get("student_id", "SST-2023-CS042"),
        "student_name": user["name"],
        "student_email": user["email"],
        "amount": amount,
        "reason": reason,
        "status": "Pending",
        "created_at": now_str,
        "date_assigned": now_str,
        "paid_at": None
    }

    return jsonify({
        "success": True,
        "message": f"₹{amount} fine successfully issued to {updated_user['name']}! Status changed to 'Action Required 🔴'.",
        "fine": fine_dict,
        "student": {
            "id": updated_user["id"],
            "name": updated_user["name"],
            "email": updated_user["email"],
            "student_id": updated_user.get("student_id", "SST-2023-CS042"),
            "status": updated_user["status"],
            "fine_amount": updated_user["fine_amount"]
        }
    }), 200


@app.route("/api/admin/fines", methods=["GET"])
@login_required(allowed_roles=["Admin"])
def get_admin_all_fines():
    """
    Admin retrieves all assigned fines campus-wide, or filters by student user_id / student_id.
    Returns fine records along with summary statistics.
    """
    user_id = request.args.get("user_id")
    student_id = request.args.get("student_id")

    conn = get_db()
    cursor = conn.cursor()

    if user_id:
        cursor.execute("SELECT * FROM fines WHERE user_id = ? ORDER BY id DESC", (user_id,))
    elif student_id:
        cursor.execute("SELECT * FROM fines WHERE student_id = ? ORDER BY id DESC", (student_id,))
    else:
        cursor.execute("SELECT * FROM fines ORDER BY id DESC")

    raw_fines = [dict(r) for r in cursor.fetchall()]
    conn.close()

    fines = []
    for f in raw_fines:
        f_copy = dict(f)
        f_copy["fine_id"] = f"FINE-{f['id']:03d}"
        f_copy["date_assigned"] = f.get("created_at")
        fines.append(f_copy)

    total_fines = len(fines)
    total_pending_amount = sum(f["amount"] for f in fines if f.get("status") == "Pending")
    total_paid_amount = sum(f["amount"] for f in fines if f.get("status") == "Paid")

    return jsonify({
        "fines": fines,
        "total_fines": total_fines,
        "total_pending_amount": total_pending_amount,
        "total_paid_amount": total_paid_amount
    }), 200


@app.route("/api/admin/students/<int:user_id>/fines", methods=["GET"])
@login_required(allowed_roles=["Admin"])
def get_admin_student_fine_history(user_id):
    """Admin retrieves complete fine history and summary metrics for a specific student."""
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute("SELECT id, name, email, student_id, status, fine_amount FROM users WHERE id = ?", (user_id,))
    student_row = cursor.fetchone()
    if not student_row:
        conn.close()
        return jsonify({"error": "Student not found."}), 404

    student = dict(student_row)
    cursor.execute("SELECT * FROM fines WHERE user_id = ? ORDER BY id DESC", (user_id,))
    raw_fines = [dict(r) for r in cursor.fetchall()]
    conn.close()

    fines = []
    for f in raw_fines:
        f_copy = dict(f)
        f_copy["fine_id"] = f"FINE-{f['id']:03d}"
        f_copy["date_assigned"] = f.get("created_at")
        fines.append(f_copy)

    total_fines = len(fines)
    total_pending_amount = sum(f["amount"] for f in fines if f.get("status") == "Pending")
    total_paid_amount = sum(f["amount"] for f in fines if f.get("status") == "Paid")

    return jsonify({
        "student": student,
        "fines": fines,
        "total_fines": total_fines,
        "total_pending_amount": total_pending_amount,
        "total_paid_amount": total_paid_amount
    }), 200


@app.route("/api/student/fines", methods=["GET"])
@app.route("/api/student/fine-history", methods=["GET"])
@login_required()
def get_student_fine_history():
    """
    Student retrieves their own complete fine history.
    Strictly scoped to session user_id to prevent accessing other students' records.
    """
    conn = get_db()
    cursor = conn.cursor()

    user_id = session.get("user_id")
    email = session.get("email")
    if user_id:
        cursor.execute("SELECT * FROM users WHERE id = ?", (user_id,))
    elif email:
        cursor.execute("SELECT * FROM users WHERE LOWER(email) = ?", (str(email).lower(),))
    else:
        conn.close()
        return jsonify({"error": "Authentication required. Please log in."}), 401
    user_row = cursor.fetchone()

    if not user_row:
        conn.close()
        return jsonify({"error": "Student not found."}), 404

    user = dict(user_row)
    user_id = user["id"]

    cursor.execute("SELECT * FROM fines WHERE user_id = ? ORDER BY id DESC", (user_id,))
    raw_fines = [dict(r) for r in cursor.fetchall()]
    conn.close()

    fines = []
    for f in raw_fines:
        f_copy = dict(f)
        f_copy["fine_id"] = f"FINE-{f['id']:03d}"
        f_copy["date_assigned"] = f.get("created_at")
        fines.append(f_copy)

    total_fines = len(fines)
    total_pending_amount = sum(f["amount"] for f in fines if f.get("status") == "Pending")
    total_paid_amount = sum(f["amount"] for f in fines if f.get("status") == "Paid")

    pending_fines = [f for f in fines if f.get("status") == "Pending"]
    current_pending_fine = pending_fines[0] if pending_fines else None

    return jsonify({
        "fines": fines,
        "total_fines": total_fines,
        "total_pending_amount": total_pending_amount,
        "total_paid_amount": total_paid_amount,
        "current_pending_fine": current_pending_fine,
        "has_fines": total_fines > 0
    }), 200


@app.route("/api/student/pay-fine", methods=["POST"])
@app.route("/api/student/fines/pay", methods=["POST"])
@login_required()
def pay_student_fine():
    """
    Clears / pays pending fine(s) and restores status to Good Standing 🟢 in SQLite.
    Marks all pending fines for the logged-in student as Paid and records paid_at timestamp.
    """
    conn = get_db()
    cursor = conn.cursor()

    user_id = session.get("user_id")
    email = session.get("email")
    if user_id:
        cursor.execute("SELECT * FROM users WHERE id = ?", (user_id,))
    elif email:
        cursor.execute("SELECT * FROM users WHERE LOWER(email) = ?", (str(email).lower(),))
    else:
        conn.close()
        return jsonify({"error": "Authentication required. Please log in."}), 401
    user_row = cursor.fetchone()

    if not user_row:
        conn.close()
        return jsonify({"error": "Student not found."}), 404

    user = dict(user_row)
    user_id = user["id"]
    now_str = datetime.now().strftime("%Y-%m-%d %H:%M")

    # Mark all pending fines for this student as Paid
    cursor.execute("""
        UPDATE fines 
        SET status = 'Paid', paid_at = ?
        WHERE user_id = ? AND status = 'Pending'
    """, (now_str, user_id))

    # Clear fine_amount on users table
    cursor.execute("""
        UPDATE users 
        SET fine_amount = 0, status = 'Good Standing 🟢'
        WHERE id = ?
    """, (user_id,))
    conn.commit()

    cursor.execute("SELECT * FROM users WHERE id = ?", (user_id,))
    updated_user = dict(cursor.fetchone())
    conn.close()

    return jsonify({
        "success": True,
        "message": "Fine cleared successfully. Status updated to 'Good Standing 🟢'.",
        "student": {
            "name": updated_user["name"],
            "status": updated_user["status"],
            "fine_amount": updated_user["fine_amount"]
        }
    }), 200


@app.route("/api/student/fines/<int:fine_id>/pay", methods=["POST"])
@login_required()
def pay_single_fine(fine_id):
    """Pays a single specific fine by fine_id."""
    conn = get_db()
    cursor = conn.cursor()

    cursor.execute("SELECT * FROM fines WHERE id = ?", (fine_id,))
    fine_row = cursor.fetchone()
    if not fine_row:
        conn.close()
        return jsonify({"error": "Fine not found."}), 404

    fine = dict(fine_row)
    now_str = datetime.now().strftime("%Y-%m-%d %H:%M")

    # Security check: if role is Student, must own the fine
    if session.get("role") == "Student":
        current_email = session.get("email", "").lower()
        cursor.execute("SELECT id FROM users WHERE LOWER(email) = ?", (current_email,))
        cur_u = cursor.fetchone()
        if cur_u and fine["user_id"] != cur_u["id"]:
            conn.close()
            return jsonify({"error": "Forbidden: You cannot pay someone else's fine."}), 403

    cursor.execute("UPDATE fines SET status = 'Paid', paid_at = ? WHERE id = ?", (now_str, fine_id))

    # Recalculate remaining pending fines for this user
    cursor.execute("SELECT SUM(amount) FROM fines WHERE user_id = ? AND status = 'Pending'", (fine["user_id"],))
    remaining = cursor.fetchone()[0] or 0

    if remaining == 0:
        cursor.execute("UPDATE users SET fine_amount = 0, status = 'Good Standing 🟢' WHERE id = ?", (fine["user_id"],))
    else:
        cursor.execute("UPDATE users SET fine_amount = ?, status = 'Action Required 🔴' WHERE id = ?", (remaining, fine["user_id"]))
    conn.commit()

    cursor.execute("SELECT * FROM users WHERE id = ?", (fine["user_id"],))
    updated_user = dict(cursor.fetchone())
    conn.close()

    return jsonify({
        "success": True,
        "message": f"Fine #{fine_id} paid successfully.",
        "student": {
            "name": updated_user["name"],
            "status": updated_user["status"],
            "fine_amount": updated_user["fine_amount"]
        }
    }), 200


@app.route("/api/events/book", methods=["POST"])
@app.route("/api/book-event", methods=["POST"])
@login_required()
def book_event():
    """
    Database-backed Event & Venue Booking with real time interval conflict detection.
    Validates time ranges (end > start) and checks SQLite events table.
    Returns HTTP 409 with conflicting_event details on clash.
    """
    data = get_request_data()
    name = str(data.get("name", "")).strip()
    venue = str(data.get("venue", "")).strip()
    date = str(data.get("date", "Today")).strip()
    start_time = str(data.get("start_time", "")).strip()
    end_time = str(data.get("end_time", "")).strip()
    organizer = str(data.get("organizer", "")).strip() or session.get("name", "Student Council")

    # 1. Required fields validation
    if not name or not venue or not date:
        return jsonify({"error": "Event name, venue, and date are required."}), 400

    def parse_time_mins(t_str):
        try:
            parts = t_str.strip().split(":")
            if len(parts) != 2:
                return None
            hrs, mins = int(parts[0]), int(parts[1])
            if 0 <= hrs <= 23 and 0 <= mins <= 59:
                return hrs * 60 + mins
            return None
        except Exception:
            return None

    # 2. Time range validation
    if start_time or end_time:
        new_start = parse_time_mins(start_time)
        new_end = parse_time_mins(end_time)

        if new_start is None or new_end is None:
            return jsonify({"error": "Invalid time format. Please use HH:MM format (e.g., 09:00, 14:30)."}), 400

        if new_end <= new_start:
            return jsonify({"error": "Invalid time range: End time must be strictly after start time."}), 400
    else:
        new_start = 9 * 60
        new_end = 17 * 60
        start_time = "09:00"
        end_time = "17:00"

    venue_lower = venue.lower()

    # 3. Conflict Detection against SQLite Events Table
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM events")
    all_events = [dict(e) for e in cursor.fetchall()]

    for event in all_events:
        evt_loc = event.get("venue", "").lower()

        # Venue matching (exact or recognized campus venue keyword)
        venue_match = (
            (venue_lower == evt_loc) or
            ("auditorium" in venue_lower and "auditorium" in evt_loc) or
            ("sports" in venue_lower and "sports" in evt_loc) or
            ("seminar" in venue_lower and "seminar" in evt_loc) or
            ("exam" in venue_lower and "exam" in evt_loc) or
            ("innovation" in venue_lower and "innovation" in evt_loc) or
            (venue_lower in evt_loc) or (evt_loc in venue_lower)
        )

        # Date matching
        date_match = (
            event.get("date", "").lower() == date.lower() or
            (event.get("date", "").lower() in ["today", "aug 22", "aug 23"] and date.lower() in ["today", "aug 22", "aug 23"])
        )

        if venue_match and date_match:
            evt_start = parse_time_mins(event.get("start_time", "00:00")) or 0
            evt_end = parse_time_mins(event.get("end_time", "23:59")) or 1440

            # Overlap condition: existing_start < requested_end AND existing_end > requested_start
            if new_start < evt_end and new_end > evt_start:
                conn.close()
                conflict_msg = (
                    f"⚠️ Schedule Conflict: \"{event['name']}\" conducted by \"{event['organizer']}\" "
                    f"is already scheduled in \"{event['venue']}\" from {event['start_time']} to {event['end_time']} "
                    f"on {event['date']}. Please choose another area or time."
                )
                return jsonify({
                    "error": "schedule_conflict",
                    "clash": True,
                    "message": conflict_msg,
                    "conflicting_event": {
                        "name": event["name"],
                        "organizer": event["organizer"],
                        "venue": event["venue"],
                        "date": event["date"],
                        "start_time": event["start_time"],
                        "end_time": event["end_time"]
                    }
                }), 409

    # 4. Insert Confirmed Event into Database
    capacity = int(data.get("capacity", 100)) if str(data.get("capacity", "")).isdigit() and int(data.get("capacity", 100)) > 0 else 100
    cursor.execute("SELECT COUNT(*) FROM events")
    count = cursor.fetchone()[0]
    evt_id = f"EVT-{101 + count}"

    cursor.execute("""
        INSERT INTO events (id, name, organizer, venue, date, start_time, end_time, description, capacity)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
    """, (evt_id, name, organizer, venue, date, start_time, end_time, f"Booked by {organizer}", capacity))
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
# EVENT REGISTRATION / RSVP ENDPOINTS
# ==============================================================================

@app.route("/api/events/<event_id>/register", methods=["POST"])
@app.route("/api/events/register", methods=["POST"])
@login_required(allowed_roles=["Student"])
def register_event(event_id=None):
    """
    Registers the authenticated Student for an event in SQLite event_registrations.
    Checks:
    - User is logged in as Student
    - Event exists in database
    - Student is not already registered (prevents duplicates)
    - Event has not reached full capacity
    """
    data = get_request_data()
    if not event_id:
        event_id = data.get("event_id")
    if not event_id:
        return jsonify({"error": "Event ID is required."}), 400

    user_id = session.get("user_id")
    user_name = session.get("name", "Student User")
    user_email = session.get("email", "")
    user_student_id = session.get("student_id", "")

    conn = get_db()
    cursor = conn.cursor()

    if not user_id and user_email:
        cursor.execute("SELECT id, name, student_id FROM users WHERE LOWER(email) = LOWER(?)", (user_email,))
        u = cursor.fetchone()
        if u:
            user_id = u["id"]
            if not user_name or user_name == "Student User":
                user_name = u["name"]
            if not user_student_id:
                user_student_id = u["student_id"]

    # 1. Verify event exists
    cursor.execute("SELECT * FROM events WHERE id = ?", (event_id,))
    event = cursor.fetchone()
    if not event:
        conn.close()
        return jsonify({"error": "Event not found."}), 404
    event = dict(event)

    # 2. Check if already registered
    cursor.execute("SELECT * FROM event_registrations WHERE event_id = ? AND user_id = ?", (event_id, user_id))
    existing_reg = cursor.fetchone()
    if existing_reg:
        conn.close()
        return jsonify({
            "error": "already_registered",
            "message": f"You are already registered for '{event['name']}'."
        }), 409

    # 3. Check capacity
    cursor.execute("SELECT COUNT(*) FROM event_registrations WHERE event_id = ?", (event_id,))
    reg_count = cursor.fetchone()[0]
    capacity = event.get("capacity") if event.get("capacity") is not None else 100
    if reg_count >= capacity:
        conn.close()
        return jsonify({
            "error": "event_full",
            "message": f"Registration closed: '{event['name']}' has reached full capacity ({reg_count}/{capacity})."
        }), 409

    # 4. Insert registration
    from datetime import datetime
    reg_timestamp = datetime.now().strftime("%b %d, %I:%M %p")
    cursor.execute("""
        INSERT INTO event_registrations (event_id, user_id, student_name, student_id, student_email, registered_at)
        VALUES (?, ?, ?, ?, ?, ?)
    """, (event_id, user_id, user_name, user_student_id, user_email, reg_timestamp))
    conn.commit()

    reg_id = cursor.lastrowid
    cursor.execute("SELECT COUNT(*) FROM event_registrations WHERE event_id = ?", (event_id,))
    new_count = cursor.fetchone()[0]
    conn.close()

    return jsonify({
        "success": True,
        "message": f"🎉 Successfully registered for '{event['name']}'!",
        "registration": {
            "id": reg_id,
            "event_id": event_id,
            "event_name": event["name"],
            "registered_at": reg_timestamp,
            "registered_count": new_count,
            "capacity": capacity
        }
    }), 201


@app.route("/api/student/my-registrations", methods=["GET"])
@app.route("/api/events/my-registrations", methods=["GET"])
@login_required(allowed_roles=["Student"])
def get_my_registrations():
    """
    Returns all event registrations for the currently authenticated student.
    """
    user_id = session.get("user_id")
    user_email = session.get("email", "")
    conn = get_db()
    cursor = conn.cursor()

    if not user_id and user_email:
        cursor.execute("SELECT id FROM users WHERE LOWER(email) = LOWER(?)", (user_email,))
        u = cursor.fetchone()
        if u:
            user_id = u["id"]

    cursor.execute("""
        SELECT r.id AS registration_id, r.registered_at,
               e.id AS event_id, e.name AS event_name, e.organizer, e.venue,
               e.date, e.start_time, e.end_time, e.description, COALESCE(e.capacity, 100) AS capacity,
               'Confirmed 🟢' AS status
        FROM event_registrations r
        JOIN events e ON r.event_id = e.id
        WHERE r.user_id = ?
        ORDER BY r.id DESC
    """, (user_id,))
    rows = [dict(r) for r in cursor.fetchall()]
    conn.close()
    return jsonify(rows)


@app.route("/api/admin/events/<event_id>/registrations", methods=["GET"])
@login_required(allowed_roles=["Admin"])
def get_event_registrations_admin(event_id):
    """
    Admin-only endpoint to view full registered student roster for a given event.
    """
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM events WHERE id = ?", (event_id,))
    event = cursor.fetchone()
    if not event:
        conn.close()
        return jsonify({"error": "Event not found."}), 404
    event = dict(event)

    cursor.execute("""
        SELECT r.id, r.user_id, r.student_name, r.student_id, r.student_email, r.registered_at
        FROM event_registrations r
        WHERE r.event_id = ?
        ORDER BY r.id ASC
    """, (event_id,))
    registrations = [dict(r) for r in cursor.fetchall()]
    conn.close()

    return jsonify({
        "event": {
            "id": event["id"],
            "name": event["name"],
            "venue": event["venue"],
            "date": event["date"],
            "start_time": event["start_time"],
            "end_time": event["end_time"],
            "capacity": event.get("capacity", 100),
            "registered_count": len(registrations)
        },
        "registrations": registrations
    }), 200


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
@login_required()
def get_alerts():
    """
    Returns urgent/important campus announcements formatted for alert display.
    """
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute("""
        SELECT id, title, content AS message,
               CASE LOWER(priority)
                   WHEN 'urgent' THEN 'danger'
                   WHEN 'important' THEN 'warning'
                   ELSE 'info'
               END AS level,
               COALESCE(venue, 'Campus-wide') AS location,
               COALESCE(time, date, created_at, 'Just now') AS timestamp,
               1 AS active,
               priority
        FROM announcements
        WHERE LOWER(priority) IN ('urgent', 'important')
        ORDER BY
            CASE LOWER(priority)
                WHEN 'urgent' THEN 1
                ELSE 2
            END,
            rowid DESC
    """)
    rows = [dict(r) for r in cursor.fetchall()]
    conn.close()
    return jsonify(rows)


@app.route("/api/announcements", methods=["GET"])
@login_required()
def get_announcements():
    """
    Returns active campus announcements from SQLite database.
    Supports filtering by category and priority.
    Ordered with Urgent first, Important second, Normal third, then newest.
    """
    category = request.args.get("category")
    priority = request.args.get("priority")
    conn = get_db()
    cursor = conn.cursor()

    query = """
        SELECT id, title, content, category,
               COALESCE(priority, 'Normal') AS priority,
               COALESCE(audience, 'All') AS audience,
               COALESCE(badge_color, 'teal') AS badge_color,
               COALESCE(date, created_at, 'Today') AS date,
               COALESCE(time, '') AS time,
               COALESCE(venue, 'Campus') AS venue,
               COALESCE(organizer, created_by, 'Campus Administration') AS organizer,
               COALESCE(created_by, 'Campus Administrator') AS created_by,
               COALESCE(created_at, date) AS created_at
        FROM announcements
    """
    params = []
    conditions = []
    if category and category.lower() != "all":
        conditions.append("LOWER(category) = ?")
        params.append(category.lower())
    if priority and priority.lower() != "all":
        conditions.append("LOWER(priority) = ?")
        params.append(priority.lower())

    if conditions:
        query += " WHERE " + " AND ".join(conditions)

    query += """
        ORDER BY
            CASE LOWER(COALESCE(priority, 'Normal'))
                WHEN 'urgent' THEN 1
                WHEN 'important' THEN 2
                ELSE 3
            END,
            rowid DESC
    """
    cursor.execute(query, tuple(params))
    rows = [dict(r) for r in cursor.fetchall()]
    conn.close()
    return jsonify(rows)


@app.route("/api/admin/announcements", methods=["GET"])
@login_required(allowed_roles=["Admin"])
def get_admin_announcements():
    """
    Admin-only retrieval of all announcements with management metadata.
    """
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute("""
        SELECT id, title, content, category,
               COALESCE(priority, 'Normal') AS priority,
               COALESCE(audience, 'All') AS audience,
               COALESCE(date, created_at, 'Today') AS date,
               COALESCE(time, '') AS time,
               COALESCE(venue, 'Campus') AS venue,
               COALESCE(organizer, created_by, 'Campus Administration') AS organizer,
               COALESCE(created_by, 'Campus Administrator') AS created_by,
               COALESCE(created_at, date) AS created_at
        FROM announcements
        ORDER BY rowid DESC
    """)
    rows = [dict(r) for r in cursor.fetchall()]
    conn.close()
    return jsonify(rows)


@app.route("/api/admin/announcements", methods=["POST"])
@app.route("/api/announcements", methods=["POST"])
@login_required(allowed_roles=["Admin"])
def create_announcement():
    """
    Admin-only endpoint to create and publish a new campus announcement in SQLite.
    """
    data = get_request_data()
    title = str(data.get("title", "")).strip()
    content = str(data.get("content") or data.get("message") or "").strip()
    category = str(data.get("category", "General")).strip()
    priority = str(data.get("priority", "Normal")).strip()
    audience = str(data.get("audience", "All")).strip()
    venue = str(data.get("venue", "Campus-wide")).strip()

    if not title or not content:
        return jsonify({"error": "Title and Announcement Message are required."}), 400

    if category not in ["Academic", "Hostel", "Events", "General"]:
        category = "General"

    if priority not in ["Normal", "Important", "Urgent"]:
        priority = "Normal"

    badge_color = "rose" if priority == "Urgent" else ("amber" if priority == "Important" else "teal")

    from datetime import datetime
    now = datetime.now()
    created_at = now.strftime("%b %d, %Y, %I:%M %p")
    date_str = now.strftime("Today, %b %d")
    time_str = now.strftime("%I:%M %p")
    admin_name = session.get("name", "Campus Administrator")

    conn = get_db()
    cursor = conn.cursor()
    cursor.execute("SELECT COUNT(*) FROM announcements")
    count = cursor.fetchone()[0]
    ann_id = f"ANN-{str(count + 1).zfill(2)}"

    cursor.execute("""
        INSERT INTO announcements (id, title, content, category, priority, audience, badge_color, date, time, venue, organizer, created_by, created_at)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
    """, (ann_id, title, content, category, priority, audience, badge_color, date_str, time_str, venue, admin_name, admin_name, created_at))
    conn.commit()

    cursor.execute("SELECT * FROM announcements WHERE id = ?", (ann_id,))
    new_ann = dict(cursor.fetchone())
    conn.close()

    return jsonify({
        "success": True,
        "message": f"📢 Announcement '{title}' published successfully!",
        "announcement": new_ann
    }), 201


@app.route("/api/admin/announcements/<ann_id>", methods=["DELETE"])
@app.route("/api/announcements/<ann_id>", methods=["DELETE"])
@login_required(allowed_roles=["Admin"])
def delete_announcement(ann_id):
    """
    Admin-only endpoint to delete an announcement from SQLite.
    """
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM announcements WHERE id = ?", (ann_id,))
    ann = cursor.fetchone()
    if not ann:
        conn.close()
        return jsonify({"error": "Announcement not found."}), 404

    cursor.execute("DELETE FROM announcements WHERE id = ?", (ann_id,))
    conn.commit()
    conn.close()

    return jsonify({
        "success": True,
        "message": f"Announcement '{ann['title']}' deleted successfully."
    }), 200


@app.route("/api/tickets", methods=["GET"])
def get_tickets():
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM tickets ORDER BY rowid DESC")
    rows = [dict(r) for r in cursor.fetchall()]
    conn.close()
    return jsonify(rows)


@app.route("/api/events", methods=["GET"])
@login_required()
def get_events():
    """
    Returns live scheduled campus events from SQLite database.
    Includes capacity, registered count, and whether current student is registered.
    Ordered chronologically by date and start_time.
    """
    user_id = session.get("user_id")
    user_role = session.get("role")
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute("""
        SELECT e.id, e.name, e.organizer, e.venue, e.date, e.start_time, e.end_time, e.description,
               COALESCE(e.capacity, 100) AS capacity,
               'Confirmed 🟢' AS status,
               (SELECT COUNT(*) FROM event_registrations r WHERE r.event_id = e.id) AS registered_count
        FROM events e
        ORDER BY
            CASE
                WHEN LOWER(e.date) = 'today' THEN 1
                WHEN LOWER(e.date) = 'tomorrow' THEN 2
                ELSE 3
            END,
            e.date ASC,
            e.start_time ASC
    """)
    rows = [dict(r) for r in cursor.fetchall()]

    if user_role == "Student" and user_id:
        cursor.execute("SELECT event_id FROM event_registrations WHERE user_id = ?", (user_id,))
        registered_set = {r[0] for r in cursor.fetchall()}
        for row in rows:
            row["is_registered"] = row["id"] in registered_set
    else:
        for row in rows:
            row["is_registered"] = False

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
