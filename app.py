import os
import random
import re
from datetime import datetime
from functools import wraps
from flask import Flask, render_template, request, jsonify, redirect, url_for, session, flash

app = Flask(__name__)
app.secret_key = os.environ.get("SECRET_KEY", "nextcamp_secret_key_scaler_sst_2026_prod")

# ==============================================================================
# AUTHENTICATION & ROUTE PROTECTION HELPERS
# ==============================================================================

def login_required(allowed_roles=None):
    """Decorator ensuring user is authenticated and matches required role."""
    def decorator(f):
        @wraps(f)
        def decorated_function(*args, **kwargs):
            if 'user' not in session:
                return redirect(url_for('login_page', next=request.path))
            
            if allowed_roles:
                user_role = session.get('role', 'Student')
                if user_role not in allowed_roles:
                    flash(f"Access restricted. Role '{user_role}' cannot access this portal.", "error")
                    if user_role == 'Admin':
                        return redirect(url_for('admin_dashboard'))
                    return redirect(url_for('student_dashboard'))
            return f(*args, **kwargs)
        return decorated_function
    return decorator


# ==============================================================================
# IN-MEMORY DATA STORES
# ==============================================================================

# Student Profile & Standing
STUDENT_PROFILE = {
    "id": "STU-1001",
    "name": "Sameer Verma",
    "email": "sameer.verma@sst.scaler.com",
    "roll": "SST-2023-CS042",
    "department": "Computer Science & AI",
    "room": "Hostel Block B, Room 204",
    "status": "Good Standing 🟢",
    "fine_amount": 0,
    "reputation": 4.7,
    "reputation_points": 94,
    "badge": "Tech Support Pro",
    "fine_history": []
}

# Important Campus Alerts (High-priority RED notice)
ALERTS = [
    {
        "id": "ALT-01",
        "title": "URGENT: Class Rescheduled - CS302 Advanced Algorithms",
        "message": "CS302 class scheduled for 2:00 PM in Classroom 204 has been moved to Innovation Lab 4 due to emergency AC maintenance. Attendance is mandatory.",
        "level": "danger",
        "location": "Classroom 204 &rarr; Innovation Lab 4",
        "timestamp": "Today, 1:45 PM",
        "active": True
    },
    {
        "id": "ALT-02",
        "title": "Hostel Water Valve Maintenance Notice",
        "message": "Secondary pump line maintenance in Hostel Block B from 4:30 PM to 6:00 PM. Reserve tanks are online.",
        "level": "warning",
        "location": "Hostel Block B",
        "timestamp": "Today, 11:20 AM",
        "active": True
    }
]

# Campus Announcements (Filterable by Academic, Hostel, Events)
ANNOUNCEMENTS = [
    {
        "id": "ANN-01",
        "title": "SST Hackathon 2026: Registrations Open",
        "content": "Join 400+ student builders for a 36-hour sprint on Smart Campus AI & Distributed Systems. Cash pool ₹2,00,000.",
        "category": "Events",
        "badge_color": "emerald",
        "date": "Aug 28 - Aug 30",
        "time": "09:00 AM",
        "venue": "Main Auditorium & Innovation Hub",
        "organizer": "SST Tech Society"
    },
    {
        "id": "ANN-02",
        "title": "Mid-Semester Examination Hall Allotment Released",
        "content": "Check your seating plan on the examination sub-portal. Carry your physical SST student ID badge.",
        "category": "Academic",
        "badge_color": "indigo",
        "date": "Aug 25 - Sep 04",
        "time": "Morning Sessions",
        "venue": "Block C & Exam Halls",
        "organizer": "Academic Office"
    },
    {
        "id": "ANN-03",
        "title": "Hostel Premier League (HPL) Cricket Knockouts",
        "content": "Block B Titans vs Block A Warriors in the evening quarter-finals under floodlights. Refreshments provided!",
        "category": "Hostel",
        "badge_color": "amber",
        "date": "Today, Aug 22",
        "time": "05:30 PM",
        "venue": "Campus Sports Complex",
        "organizer": "Hostel Council"
    },
    {
        "id": "ANN-04",
        "title": "Guest Keynote: Generative AI & Autonomous Agents",
        "content": "Dr. A. Sharma from Google DeepMind sharing insights on production agent workflows.",
        "category": "Academic",
        "badge_color": "purple",
        "date": "Tomorrow, Aug 23",
        "time": "11:00 AM",
        "venue": "Seminar Hall 1",
        "organizer": "Dept. of Computer Science"
    },
    {
        "id": "ANN-05",
        "title": "Night Canteen Extended Operating Hours",
        "content": "Hostel canteen will remain operational until 3:00 AM during mid-term examination week.",
        "category": "Hostel",
        "badge_color": "rose",
        "date": "Aug 22 - Sep 05",
        "time": "10:00 PM - 03:00 AM",
        "venue": "Central Cafeteria",
        "organizer": "Campus Services"
    }
]

# Workers / Solvers Directory with CRUD support
WORKERS = [
    {
        "id": "WKR-01",
        "name": "Ravi",
        "category": "Electrical",
        "rating": 4.9,
        "tasks_solved": 84,
        "active_tickets": 0,
        "phone": "+91 98765 43210",
        "email": "ravi.tech@sst.scaler.com"
    },
    {
        "id": "WKR-02",
        "name": "Amit Singh",
        "category": "Hardware",
        "rating": 4.8,
        "tasks_solved": 62,
        "active_tickets": 0,
        "phone": "+91 98765 43211",
        "email": "amit.hw@sst.scaler.com"
    },
    {
        "id": "WKR-03",
        "name": "Priya Verma",
        "category": "IT",
        "rating": 4.95,
        "tasks_solved": 112,
        "active_tickets": 0,
        "phone": "+91 98765 43212",
        "email": "priya.it@sst.scaler.com"
    },
    {
        "id": "WKR-04",
        "name": "Manoj Kumar",
        "category": "Electrical",
        "rating": 4.6,
        "tasks_solved": 45,
        "active_tickets": 0,
        "phone": "+91 98765 43213",
        "email": "manoj.k@sst.scaler.com"
    },
    {
        "id": "WKR-05",
        "name": "Vikram Rao",
        "category": "IT",
        "rating": 4.55,
        "tasks_solved": 38,
        "active_tickets": 0,
        "phone": "+91 98765 43214",
        "email": "vikram.r@sst.scaler.com"
    },
    {
        "id": "WKR-06",
        "name": "Suresh Nair",
        "category": "Hardware",
        "rating": 4.7,
        "tasks_solved": 51,
        "active_tickets": 0,
        "phone": "+91 98765 43215",
        "email": "suresh.n@sst.scaler.com"
    }
]

# CCTV Damage Incident Review Record
CCTV_DAMAGE_INCIDENT = {
    "id": "CCTV-204",
    "camera_id": "CAM-09 (High-Res Optical)",
    "location": "Classroom 204",
    "timestamp": "3:20 PM - Damaged Chair",
    "incident_label": "Classroom 204 — 3:20 PM - Damaged Chair",
    "student_name": "Sameer Verma",
    "student_roll": "SST-2023-CS042",
    "confidence": 98.2,
    "fine_amount": 500,
    "status": "Pending Review",
    "description": "Visual anomaly detection in Classroom 204: Fractured wooden backrest and severed metal bracket on student chair row 3."
}

# Campus Events (Used for Venue & Time Clash Detection)
CAMPUS_EVENTS = [
    {
        "id": "EVT-101",
        "name": "Annual Tech Symposium 2026",
        "location": "Main Auditorium",
        "date": "Today",
        "start_time": "09:00",
        "end_time": "18:00",
        "organizer": "SST Tech Society",
        "description": "Keynotes, project demos and industry panel discussions in the Auditorium."
    },
    {
        "id": "EVT-102",
        "name": "Placement Coding Sprint",
        "location": "Block C Exam Hall",
        "date": "Today",
        "start_time": "10:00",
        "end_time": "17:00",
        "organizer": "Career Advancement Cell",
        "description": "Online coding round for hiring partner assessments."
    },
    {
        "id": "EVT-103",
        "name": "HPL Quarter-Final Match",
        "location": "Sports Complex",
        "date": "Today",
        "start_time": "15:00",
        "end_time": "20:00",
        "organizer": "Sports Council",
        "description": "Hostel cricket tournament finals."
    }
]

# Active Tickets
TICKETS = [
    {
        "id": "TCK-1001",
        "title": "Lab 3 High-Voltage Switchboard Sparking",
        "category": "Electrical",
        "location": "Innovation Lab 3, Rack A2",
        "urgency": "Critical",
        "description": "Feeder breaker sparking on load activation. Circuit isolated.",
        "reporter_name": "Sameer Verma",
        "reported_at": "1 hour ago",
        "status": "Assigned",
        "solver_id": "WKR-01",
        "solver_name": "Ravi",
        "solver_rating": 4.9,
        "solver_display": "Assigned to: Ravi (⭐ 4.9)",
        "rated": False
    },
    {
        "id": "TCK-1002",
        "title": "Corridor Wi-Fi AP Dropping Connections",
        "category": "IT",
        "location": "Hostel Block B, 2nd Floor",
        "urgency": "Medium",
        "description": "AP-B-201 authentication timeout for student laptops.",
        "reporter_name": "Sameer Verma",
        "reported_at": "2 hours ago",
        "status": "In Progress",
        "solver_id": "WKR-03",
        "solver_name": "Priya Verma",
        "solver_rating": 4.95,
        "solver_display": "Assigned to: Priya Verma (⭐ 4.95)",
        "rated": False
    },
    {
        "id": "TCK-1000",
        "title": "Hostel Water Purifier Flow Sensor Glitch",
        "category": "Hardware",
        "location": "Hostel Block B, Mess Hall",
        "urgency": "High",
        "description": "Dispenser flow meter calibrated and filtration unit serviced.",
        "reporter_name": "Sameer Verma",
        "reported_at": "3 hours ago",
        "status": "Resolved",
        "solver_id": "WKR-02",
        "solver_name": "Amit Singh",
        "solver_rating": 4.8,
        "solver_display": "Assigned to: Amit Singh (⭐ 4.8)",
        "rated": False
    }
]

# Worker Reviews Log
WORKER_REVIEWS = [
    {
        "id": "REV-501",
        "ticket_id": "TCK-0998",
        "worker_id": "WKR-01",
        "worker_name": "Ravi",
        "worker_category": "Electrical",
        "student_name": "Sameer Verma",
        "student_roll": "SST-2023-CS042",
        "response_time": 5,
        "quality": 5,
        "behavior": 5,
        "avg_rating": 5.0,
        "suggestion": "Arrived within 10 minutes and completely fixed the tripped circuit breaker. Excellent work!",
        "timestamp": "Today, 10:15 AM"
    },
    {
        "id": "REV-502",
        "ticket_id": "TCK-0999",
        "worker_id": "WKR-03",
        "worker_name": "Priya Verma",
        "worker_category": "IT",
        "student_name": "Aarav Sharma",
        "student_roll": "SST-2023-CS015",
        "response_time": 5,
        "quality": 5,
        "behavior": 4,
        "avg_rating": 4.67,
        "suggestion": "Wi-Fi access point firmware upgrade resolved the latency issues in the library.",
        "timestamp": "Yesterday, 4:45 PM"
    }
]

ticket_counter = 1004
worker_counter = 7
event_counter = 104
review_counter = 503


def get_request_data():
    """Helper to safely extract JSON or form data without raising 415."""
    try:
        if request.is_json:
            return request.get_json(silent=True) or {}
    except Exception:
        pass
    return request.form.to_dict() if request.form else {}


# ==============================================================================
# SMART PROBLEM ALLOCATION ENGINE
# ==============================================================================

def allocate_smart_worker(category):
    """
    Filters available workers by requested category,
    automatically picks the solver with the HIGHEST rating and tasks solved,
    and returns the worker object.
    """
    cat_lower = category.strip().lower()
    
    # Matching category workers
    matching = [
        w for w in WORKERS 
        if w["category"].strip().lower() == cat_lower or 
           cat_lower in w["category"].strip().lower() or 
           w["category"].strip().lower() in cat_lower
    ]

    # Fallback to all workers if no exact category match
    candidates = matching if matching else WORKERS

    if not candidates:
        return None

    # Sort primarily by highest rating (descending), then highest tasks solved (descending)
    candidates.sort(key=lambda w: (float(w.get("rating", 0.0)), int(w.get("tasks_solved", 0))), reverse=True)
    
    selected_worker = candidates[0]
    selected_worker["active_tickets"] = selected_worker.get("active_tickets", 0) + 1
    selected_worker["tasks_solved"] = selected_worker.get("tasks_solved", 0) + 1
    
    return selected_worker


# ==============================================================================
# WEB VIEWS & AUTHENTICATION ROUTES
# ==============================================================================

@app.route("/login", methods=["GET", "POST"])
def login_page():
    """Domain-restricted login page for @sst.scaler.com accounts."""
    if request.method == "POST":
        data = get_request_data()
        email = data.get("email", "").strip().lower()
        password = data.get("password", "").strip()
        role = data.get("role", "Student").strip()

        # STRICT DOMAIN VALIDATION: Only @sst.scaler.com allowed
        if not email.endswith("@sst.scaler.com") or "@" not in email:
            error_msg = "Access restricted! Only @sst.scaler.com email addresses are authorized."
            if request.headers.get("X-Requested-With") == "XMLHttpRequest" or request.is_json:
                return jsonify({"error": error_msg}), 400
            return render_template("login.html", error=error_msg, email=email, role=role)

        # Authentication success -> populate session
        user_handle = email.split("@")[0].replace(".", " ").title()
        session["user"] = email
        session["email"] = email
        session["name"] = user_handle if user_handle else "Sameer Verma"
        session["role"] = role
        session["reputation"] = STUDENT_PROFILE.get("reputation", 4.7)
        session["reputation_points"] = STUDENT_PROFILE.get("reputation_points", 94)
        session["badge"] = STUDENT_PROFILE.get("badge", "Tech Support Pro")

        if role == "Admin":
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
    session["reputation"] = STUDENT_PROFILE.get("reputation", 4.7)
    session["reputation_points"] = STUDENT_PROFILE.get("reputation_points", 94)
    session["badge"] = STUDENT_PROFILE.get("badge", "Tech Support Pro")
    return render_template("index.html", user=session)

@app.route("/admin")
@login_required()
def admin_dashboard():
    """Admin Hub with CCTV Damage Review, Worker Management CRUD, and Review Log."""
    return render_template("admin.html", user=session)


# ==============================================================================
# REST API ENDPOINTS
# ==============================================================================

@app.route("/api/student/profile", methods=["GET"])
def get_student_profile():
    """Fetch current student profile, fine amount, and standing status."""
    return jsonify(STUDENT_PROFILE)

@app.route("/api/report-problem", methods=["POST"])
@app.route("/api/tickets", methods=["POST"])
def report_problem():
    """
    Submitting a problem runs the smart allocation engine,
    picks the solver with the highest rating & solved count for that category,
    and returns 'Assigned to: [Worker Name] (⭐ [Rating])'.
    """
    global ticket_counter
    data = get_request_data()

    location = data.get("location", "Campus").strip()
    category = data.get("category", "Electrical").strip()
    description = data.get("description", "").strip()
    urgency = data.get("urgency", "High").strip()
    title = data.get("title", f"{category} Issue at {location}").strip()
    reporter_name = session.get("name", STUDENT_PROFILE["name"])

    if not location or not category:
        return jsonify({"error": "Location and category are required."}), 400

    # Run Smart Problem Allocation
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

    ticket_id = f"TCK-{ticket_counter}"
    ticket_counter += 1

    new_ticket = {
        "id": ticket_id,
        "title": title,
        "category": category,
        "location": location,
        "urgency": urgency,
        "description": description or f"Reported issue in {category} department.",
        "reporter_name": reporter_name,
        "reported_at": "Just now",
        "status": "Assigned",
        "solver_id": solver_id,
        "solver_name": solver_name,
        "solver_rating": solver_rating,
        "solver_display": solver_display,
        "rated": False
    }

    TICKETS.insert(0, new_ticket)

    return jsonify({
        "message": f"Problem reported! {solver_display}",
        "solver_display": solver_display,
        "ticket": new_ticket
    }), 201

@app.route("/api/tickets/<ticket_id>/resolve", methods=["POST", "PUT"])
@app.route("/api/resolve-ticket", methods=["POST", "PUT"])
def resolve_ticket(ticket_id=None):
    """Marks a ticket as Resolved so it can be rated by the student."""
    data = get_request_data()
    t_id = ticket_id or data.get("ticket_id")
    target = next((t for t in TICKETS if t["id"] == t_id), None)
    if not target:
        return jsonify({"error": "Ticket not found."}), 404
    
    target["status"] = "Resolved"
    target["resolved_at"] = datetime.now().strftime("%I:%M %p, %d %b %Y")
    return jsonify({
        "message": f"Ticket {t_id} marked as Resolved.",
        "ticket": target
    }), 200

@app.route("/api/submit-rating", methods=["POST"])
def submit_rating():
    """
    POST /api/submit-rating:
    1. Response Time (1 to 5 Stars)
    2. Quality of Solution (1 to 5 Stars)
    3. Behavior & Helpfulness (1 to 5 Stars)
    4. Improvement Suggestion (Text box: "What could have been done better?")
    Averages score, recalculates assigned worker's cumulative rating,
    awards +5 Reputation Points to the reporting student,
    and appends the review to the Admin Review Log.
    """
    global review_counter
    data = get_request_data()

    ticket_id = str(data.get("ticket_id", "")).strip()
    response_time = float(data.get("response_time", 5))
    quality = float(data.get("quality", 5))
    behavior = float(data.get("behavior", 5))
    suggestion = str(data.get("suggestion", "")).strip()

    # Calculate 3-dimensional average rating
    avg_rating = round((response_time + quality + behavior) / 3.0, 2)

    # Locate ticket
    ticket = next((t for t in TICKETS if t["id"] == ticket_id), None)
    solver_name = data.get("solver_name") or (ticket.get("solver_name") if ticket else "Ravi")
    solver_id = data.get("worker_id") or (ticket.get("solver_id") if ticket else None)
    worker_category = data.get("category") or (ticket.get("category") if ticket else "General")

    # Locate worker
    worker = None
    if solver_id:
        worker = next((w for w in WORKERS if w["id"] == solver_id), None)
    if not worker and solver_name:
        worker = next((w for w in WORKERS if w["name"].lower() == solver_name.lower()), None)
    if not worker and WORKERS:
        worker = WORKERS[0]

    # Recalculate worker's cumulative rating (⭐ Rating)
    if worker:
        tasks_count = worker.get("tasks_solved", 0)
        current_rating = float(worker.get("rating", 5.0))
        # Cumulative average formula
        new_worker_rating = round(((current_rating * max(1, tasks_count)) + avg_rating) / (max(1, tasks_count) + 1), 2)
        worker["rating"] = min(5.0, max(1.0, new_worker_rating))
        worker["tasks_solved"] = tasks_count + 1
        solver_name = worker["name"]
        solver_id = worker["id"]
        worker_category = worker["category"]

    # Award +5 Reputation Points to reporting student
    STUDENT_PROFILE["reputation_points"] = STUDENT_PROFILE.get("reputation_points", 94) + 5
    STUDENT_PROFILE["reputation"] = round(min(5.0, STUDENT_PROFILE.get("reputation", 4.7) + 0.05), 2)
    session["reputation"] = STUDENT_PROFILE["reputation"]
    session["reputation_points"] = STUDENT_PROFILE["reputation_points"]

    # Mark ticket as resolved & rated
    if ticket:
        ticket["status"] = "Resolved"
        ticket["rated"] = True
        ticket["rating_score"] = avg_rating
        ticket["rating_details"] = {
            "response_time": response_time,
            "quality": quality,
            "behavior": behavior,
            "avg_rating": avg_rating,
            "suggestion": suggestion
        }

    # Append to Admin Review Log
    rev_id = f"REV-{review_counter}"
    review_counter += 1

    review_obj = {
        "id": rev_id,
        "ticket_id": ticket_id or "TCK-1000",
        "worker_id": solver_id or "WKR-01",
        "worker_name": solver_name,
        "worker_category": worker_category,
        "student_name": session.get("name", STUDENT_PROFILE["name"]),
        "student_roll": STUDENT_PROFILE.get("roll", "SST-2023-CS042"),
        "response_time": int(response_time),
        "quality": int(quality),
        "behavior": int(behavior),
        "avg_rating": avg_rating,
        "suggestion": suggestion or "No specific suggestion provided. Great service.",
        "timestamp": datetime.now().strftime("%I:%M %p, %d %b %Y")
    }
    WORKER_REVIEWS.insert(0, review_obj)

    return jsonify({
        "message": f"Review submitted! +5 Reputation Points awarded. Worker {solver_name}'s rating updated to ⭐ {worker['rating'] if worker else avg_rating}.",
        "avg_rating": avg_rating,
        "reputation_points": STUDENT_PROFILE["reputation_points"],
        "student_reputation": STUDENT_PROFILE["reputation"],
        "worker": worker,
        "review": review_obj,
        "ticket": ticket
    }), 200

@app.route("/api/reviews", methods=["GET"])
def get_worker_reviews():
    """Retrieve all student service reviews for the Admin Reviews Log."""
    return jsonify(WORKER_REVIEWS)

@app.route("/api/issue-fine", methods=["POST"])
@app.route("/api/student/issue-fine", methods=["POST"])
def issue_cctv_fine():
    """
    Clicking [Review & Issue Fine ₹500] updates student profile status
    from Good Standing 🟢 to Action Required 🔴 and applies a ₹500 Fine.
    """
    data = get_request_data()
    amount = data.get("amount", 500)
    reason = str(data.get("reason", "Classroom 204 — 3:20 PM - Damaged Chair")).strip()

    STUDENT_PROFILE["fine_amount"] += amount
    STUDENT_PROFILE["status"] = "Action Required 🔴"
    STUDENT_PROFILE["fine_reason"] = reason
    STUDENT_PROFILE["fine_history"].append({
        "amount": amount,
        "reason": reason,
        "timestamp": datetime.now().strftime("%I:%M %p, %d %b %Y"),
        "issued_by": "CCTV Vision Reviewer"
    })

    CCTV_DAMAGE_INCIDENT["status"] = f"Fine Issued (₹{amount})"

    return jsonify({
        "message": f"₹{amount} fine successfully issued to {STUDENT_PROFILE['name']}! Status changed to 'Action Required 🔴'.",
        "student": STUDENT_PROFILE,
        "incident": CCTV_DAMAGE_INCIDENT
    }), 200

@app.route("/api/student/pay-fine", methods=["POST"])
def pay_student_fine():
    """Clear student fine and restore status to Good Standing 🟢."""
    STUDENT_PROFILE["fine_amount"] = 0
    STUDENT_PROFILE["status"] = "Good Standing 🟢"
    STUDENT_PROFILE["fine_reason"] = None
    return jsonify({
        "message": "Fine cleared successfully. Status updated to 'Good Standing 🟢'.",
        "student": STUDENT_PROFILE
    })

@app.route("/api/events/book", methods=["POST"])
@app.route("/api/book-event", methods=["POST"])
def book_event():
    """
    Checks if venue and time are already booked.
    If booked, returns: ⚠️ TIME CLASH DETECTED: [Venue] is already booked
    """
    global event_counter
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

    # Check clash against existing campus events
    for event in CAMPUS_EVENTS:
        evt_loc = event.get("location", "").lower()

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

            # Overlap check
            if (not start_time and not end_time) or (new_start < evt_end and new_end > evt_start):
                venue_display = "Auditorium" if "auditorium" in venue_lower else venue
                clash_text = f"⚠️ TIME CLASH DETECTED: {venue_display} is already booked"
                return jsonify({
                    "clash": True,
                    "error": clash_text,
                    "message": clash_text,
                    "conflicting_event": event
                }), 409

    # No clash -> Book event
    evt_id = f"EVT-{event_counter}"
    event_counter += 1

    new_event = {
        "id": evt_id,
        "name": name,
        "location": venue,
        "date": date,
        "start_time": start_time or "09:00",
        "end_time": end_time or "17:00",
        "organizer": organizer,
        "description": f"Booked by {organizer}"
    }
    CAMPUS_EVENTS.append(new_event)

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
    """Retrieve all campus workers/solvers."""
    return jsonify(WORKERS)

@app.route("/api/workers", methods=["POST"])
def add_worker():
    """
    ➕ Add New Worker: Form specifying Name and Category
    (defaults to ⭐ 5.0 rating, 0 tasks solved).
    """
    global worker_counter
    data = get_request_data()

    name = str(data.get("name", "")).strip()
    category = str(data.get("category", "General")).strip()

    if not name:
        return jsonify({"error": "Worker Name is required."}), 400

    worker_id = f"WKR-{str(worker_counter).zfill(2)}"
    worker_counter += 1

    new_worker = {
        "id": worker_id,
        "name": name,
        "category": category,
        "rating": 5.0,        # Defaults to ⭐ 5.0
        "tasks_solved": 0,    # Defaults to 0 solved
        "active_tickets": 0,
        "phone": "+91 98765 00000",
        "email": f"{name.lower().replace(' ', '.')}@sst.scaler.com"
    }

    WORKERS.append(new_worker)

    return jsonify({
        "message": f"Worker '{name}' ({category}) added with ⭐ 5.0 rating!",
        "worker": new_worker
    }), 201

@app.route("/api/workers/<worker_id>", methods=["PUT", "POST"])
def edit_worker(worker_id):
    """
    ✏️ Edit Worker: Update an existing worker's Name or Category.
    """
    data = get_request_data()

    target = next((w for w in WORKERS if w["id"] == worker_id), None)
    if not target:
        return jsonify({"error": "Worker not found."}), 404

    if "name" in data and str(data["name"]).strip():
        target["name"] = str(data["name"]).strip()
    if "category" in data and str(data["category"]).strip():
        target["category"] = str(data["category"]).strip()
    if "rating" in data:
        try:
            target["rating"] = float(data["rating"])
        except ValueError:
            pass

    return jsonify({
        "message": f"Worker {worker_id} updated successfully!",
        "worker": target
    }), 200

@app.route("/api/workers/<worker_id>", methods=["DELETE"])
def delete_worker(worker_id):
    """Delete a worker."""
    global WORKERS
    initial_len = len(WORKERS)
    WORKERS = [w for w in WORKERS if w["id"] != worker_id]
    
    if len(WORKERS) < initial_len:
        return jsonify({"message": f"Worker {worker_id} deleted."}), 200
    return jsonify({"error": "Worker not found."}), 404


# ==============================================================================
# GENERAL API ENDPOINTS
# ==============================================================================

@app.route("/api/alerts", methods=["GET"])
def get_alerts():
    return jsonify(ALERTS)

@app.route("/api/announcements", methods=["GET"])
def get_announcements():
    category = request.args.get("category")
    if category and category.lower() != "all":
        return jsonify([a for a in ANNOUNCEMENTS if a["category"].lower() == category.lower()])
    return jsonify(ANNOUNCEMENTS)

@app.route("/api/tickets", methods=["GET"])
def get_tickets():
    return jsonify(TICKETS)

@app.route("/api/cctv/incident", methods=["GET"])
def get_cctv_incident():
    return jsonify(CCTV_DAMAGE_INCIDENT)

@app.route("/api/events", methods=["GET"])
def get_events():
    return jsonify(CAMPUS_EVENTS)


if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    print(f"[NextCamp] Production server running on http://127.0.0.1:{port}")
    app.run(host="0.0.0.0", port=port, debug=True)
