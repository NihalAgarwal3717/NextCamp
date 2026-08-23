"""
NextCamp Comprehensive Test Suite with SQLite Database Persistence & Role-Based Access Control (RBAC)
Validates:
1. SQLite Schema Integrity (Users, Events, Workers, Tickets, Reviews)
2. Domain-restricted authentication (@sst.scaler.com) & route protection
3. Exact Authentication Requirements (Test A, Test B, Test C)
4. Role-Based Access Control (RBAC) - Strict Server-Side Authorization:
   - TEST 1: Unauthenticated user -> /admin -> rejected (302 to /login)
   - TEST 2: Student -> /admin -> rejected (safe redirect / HTTP 403, never renders admin page)
   - TEST 3: Admin -> /admin -> HTTP 200
   - TEST 4: Student -> GET /api/admin/users -> rejected (HTTP 403)
   - TEST 5: Student -> POST /api/admin/users -> rejected (HTTP 403)
   - TEST 6: Admin -> GET /api/admin/users -> allowed (HTTP 200)
   - TEST 7: Admin -> POST /api/admin/users -> allowed (HTTP 201)
   - TEST 8: Manipulating frontend role parameter on login cannot grant Student admin privileges
   - TEST 9: Student accessing Admin APIs (workers CRUD, issue fine, resolve ticket) -> rejected (HTTP 403)
5. Admin User Management CRUD & Security:
   - Admin listing users (ensuring passwords are not exposed)
   - Admin creating user with @sst.scaler.com email and hashed password
   - Rejecting duplicate email addresses (409 Conflict)
   - Rejecting non-@sst.scaler.com email addresses (400 Bad Request)
   - Verifying newly created user login: incorrect password rejected (401)
   - Verifying newly created user login: correct password succeeds (200)
   - Toggling user activation: deactivated accounts blocked from login (403)
   - Deleting a user from the Users table
6. Student problem reporting with smart solver allocation (highest rating & solved count)
7. CCTV Damage fine issuance (₹500 & 'Action Required 🔴' status)
8. Worker Management CRUD (Add, Edit, Delete) and dynamic smart allocation integration
9. Event booking venue & time clash detection
10. Post-Resolution Rating System (3-dimensional star ratings, worker cumulative score recalculation, +5 student reputation points, review log)
"""
import unittest
import json
import os
import sqlite3

# Set test database path before importing app
os.environ["NEXTCAMP_DB"] = os.path.join(os.path.dirname(__file__), "test_nextcamp.db")

from app import app, init_db, get_db, allocate_smart_worker

class NextCampComprehensiveTestCase(unittest.TestCase):
    def setUp(self):
        self.app = app.test_client()
        self.app.testing = True

        # Re-initialize test database with clean seed data
        if os.path.exists(os.environ["NEXTCAMP_DB"]):
            try:
                os.remove(os.environ["NEXTCAMP_DB"])
            except Exception:
                try:
                    conn = get_db()
                    cursor = conn.cursor()
                    cursor.execute("SELECT name FROM sqlite_master WHERE type='table'")
                    for (tbl,) in cursor.fetchall():
                        if not tbl.startswith("sqlite_"):
                            cursor.execute(f"DROP TABLE IF EXISTS {tbl}")
                    conn.commit()
                    conn.close()
                except Exception:
                    pass
        init_db()

    def tearDown(self):
        if os.path.exists(os.environ["NEXTCAMP_DB"]):
            try:
                os.remove(os.environ["NEXTCAMP_DB"])
            except Exception:
                pass

    # =========================================================================
    # 1. DATABASE SCHEMA & INTEGRITY TESTS
    # =========================================================================

    def test_database_tables_exist(self):
        """
        Verify all 5 required tables (Users, Events, Workers, Tickets, Reviews)
        are created in SQLite with the required columns.
        """
        conn = get_db()
        cursor = conn.cursor()
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table'")
        tables = [row[0] for row in cursor.fetchall()]
        
        self.assertIn("users", tables)
        self.assertIn("events", tables)
        self.assertIn("workers", tables)
        self.assertIn("tickets", tables)
        self.assertIn("reviews", tables)

        # Check Users columns
        cursor.execute("PRAGMA table_info(users)")
        user_cols = [row[1] for row in cursor.fetchall()]
        for col in ["id", "name", "email", "password_hash", "role", "student_id", "is_active"]:
            self.assertIn(col, user_cols)

        conn.close()

    # =========================================================================
    # 2. EXACT AUTHENTICATION & LOGIN FLOW TESTS (TESTS A, B, C)
    # =========================================================================

    def test_a_unregistered_sst_email_rejected(self):
        """
        Test A:
        Unregistered @sst.scaler.com + random password -> 401 -> login rejected.
        User must NOT be created and login must fail with 'Invalid email or password.'
        """
        res = self.app.post('/login', data={
            'email': 'unregistered.random@sst.scaler.com',
            'password': 'randompassword123',
            'role': 'Student'
        })
        self.assertEqual(res.status_code, 401)
        self.assertIn(b"Invalid email or password.", res.data)

        # Verify in SQLite database that NO user was created
        conn = get_db()
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM users WHERE LOWER(email) = 'unregistered.random@sst.scaler.com'")
        self.assertIsNone(cursor.fetchone())
        conn.close()

    def test_b_registered_sst_email_wrong_password_rejected(self):
        """
        Test B:
        Registered @sst.scaler.com + wrong password -> 401 -> login rejected.
        Login must fail with 'Invalid email or password.' and session must not be established.
        """
        res = self.app.post('/login', data={
            'email': 'sameer.verma@sst.scaler.com',
            'password': 'incorrect_password_999',
            'role': 'Student'
        })
        self.assertEqual(res.status_code, 401)
        self.assertIn(b"Invalid email or password.", res.data)

    def test_c_registered_sst_email_correct_password_succeeds(self):
        """
        Test C:
        Registered @sst.scaler.com + correct password -> successful login (302 redirect / session established).
        """
        with self.app as client:
            res = client.post('/login', data={
                'email': 'sameer.verma@sst.scaler.com',
                'password': 'scaler123',
                'role': 'Student'
            }, follow_redirects=True)
            self.assertEqual(res.status_code, 200)
            self.assertIn(b"NextCamp", res.data)
            self.assertIn(b"The Campus That Fixes Itself", res.data)

    def test_login_rejects_non_sst_domain(self):
        """
        Verify that attempting to log in with an unauthorized email domain
        (e.g., @gmail.com or @other.edu) is rejected with domain error message.
        """
        res = self.app.post('/login', data={
            'email': 'student@gmail.com',
            'password': 'password123',
            'role': 'Student'
        })
        self.assertEqual(res.status_code, 400)
        self.assertIn(b"Access restricted! Only @sst.scaler.com email addresses are authorized.", res.data)

    def test_protected_routes_redirect_unauthenticated_users(self):
        """
        Verify that unauthenticated access to / or /admin redirects to /login.
        """
        res_student = self.app.get('/', follow_redirects=False)
        self.assertEqual(res_student.status_code, 302)
        self.assertIn('/login', res_student.headers['Location'])

        res_admin = self.app.get('/admin', follow_redirects=False)
        self.assertEqual(res_admin.status_code, 302)
        self.assertIn('/login', res_admin.headers['Location'])

    def test_logout_clears_session(self):
        """
        Verify that logging out clears user session and redirects to /login.
        """
        with self.app as client:
            client.post('/login', data={
                'email': 'sameer.verma@sst.scaler.com',
                'password': 'scaler123',
                'role': 'Student'
            })
            logout_res = client.get('/logout', follow_redirects=False)
            self.assertEqual(logout_res.status_code, 302)
            self.assertIn('/login', logout_res.headers['Location'])

    def test_multiple_independent_sessions_and_isolated_logout(self):
        """
        Verify independent multi-account authentication:
        1. Client 1 (Student A - Sameer) logs in.
        2. Client 2 (Admin) logs in.
        3. Client 3 (Student B - Pooja) logs in.
        4. Each client queries their profile / dashboard and receives their own data.
        5. Client 1 logs out.
        6. Client 1 is now logged out (401), while Client 2 (Admin) and Client 3 (Student B) remain logged in.
        7. Client 2 and Client 3 continue to access their respective routes without interference.
        """
        client1 = app.test_client()
        client2 = app.test_client()
        client3 = app.test_client()

        # Create Student B via Admin
        client2.post('/login', data={'email': 'admin@sst.scaler.com', 'password': 'admin123', 'role': 'Admin'})
        u_res = client2.post('/api/admin/users',
                             data=json.dumps({
                                 'name': 'Pooja Hegde',
                                 'email': 'pooja.hegde@sst.scaler.com',
                                 'password': 'scalerpassword123',
                                 'role': 'Student',
                                 'student_id': 'SST-2024-CS081'
                             }),
                             content_type='application/json')
        self.assertEqual(u_res.status_code, 201)

        # 1. Login Client 1 as Student A (Sameer)
        r1 = client1.post('/login', data={'email': 'sameer.verma@sst.scaler.com', 'password': 'scaler123', 'role': 'Student'})
        self.assertEqual(r1.status_code, 302)

        # 2. Login Client 3 as Student B (Pooja)
        r3 = client3.post('/login', data={'email': 'pooja.hegde@sst.scaler.com', 'password': 'scalerpassword123', 'role': 'Student'})
        self.assertEqual(r3.status_code, 302)

        # 3. Verify Client 1 sees Student A profile
        p1 = json.loads(client1.get('/api/student/profile').data)
        self.assertEqual(p1['name'], 'Sameer Verma')
        self.assertEqual(p1['email'], 'sameer.verma@sst.scaler.com')

        # 4. Verify Client 2 sees Admin users API
        a2 = json.loads(client2.get('/api/admin/users').data)
        self.assertIsInstance(a2, list)

        # 5. Verify Client 3 sees Student B profile
        p3 = json.loads(client3.get('/api/student/profile').data)
        self.assertEqual(p3['name'], 'Pooja Hegde')
        self.assertEqual(p3['email'], 'pooja.hegde@sst.scaler.com')

        # 6. Logout Client 1 (Student A)
        logout_res = client1.get('/logout')
        self.assertEqual(logout_res.status_code, 302)

        # 7. Verify Client 1 is logged out
        c1_after = client1.get('/api/student/profile')
        self.assertEqual(c1_after.status_code, 401)

        # 8. Verify Client 2 (Admin) and Client 3 (Student B) remain completely active
        a2_after = json.loads(client2.get('/api/admin/users').data)
        self.assertIsInstance(a2_after, list)

        p3_after = json.loads(client3.get('/api/student/profile').data)
        self.assertEqual(p3_after['name'], 'Pooja Hegde')
        self.assertEqual(p3_after['email'], 'pooja.hegde@sst.scaler.com')

    def test_session_persistence_across_multiple_refreshes(self):
        """
        Verify that:
        1. Student remains logged in across multiple simulated page refreshes (/dashboard, /, /events, /profile).
        2. Admin remains logged in across multiple simulated page refreshes (/admin, /admin/dashboard, /admin/users).
        3. Logout immediately destroys session and refresh redirects to /login.
        """
        student_client = app.test_client()
        admin_client = app.test_client()

        # 1. Student Login
        log_res = student_client.post('/login', data={'email': 'sameer.verma@sst.scaler.com', 'password': 'scaler123', 'role': 'Student'})
        self.assertEqual(log_res.status_code, 302)

        # 2. Simulate 5 consecutive page refreshes on different student routes
        for path in ['/', '/dashboard', '/announcements', '/events', '/registrations', '/tickets', '/profile', '/dashboard']:
            res = student_client.get(path, follow_redirects=False)
            self.assertEqual(res.status_code, 200, f"Failed on path {path} - expected 200 OK")
            self.assertIn(b"NextCamp", res.data)
            self.assertIn(b"Sameer Verma", res.data)

        # 3. Admin Login
        admin_log = admin_client.post('/login', data={'email': 'admin@sst.scaler.com', 'password': 'admin123', 'role': 'Admin'})
        self.assertEqual(admin_log.status_code, 302)

        # 4. Simulate consecutive page refreshes on admin routes
        for path in ['/admin', '/admin/dashboard', '/admin/announcements', '/admin/events', '/admin/users', '/admin/tickets', '/admin/profile']:
            res = admin_client.get(path, follow_redirects=False)
            self.assertEqual(res.status_code, 200, f"Failed on admin path {path} - expected 200 OK")
            self.assertIn(b"Campus Administrator", res.data)

        # 5. Logout Student
        student_client.get('/logout')
        # Subsequent refreshes MUST redirect to /login
        for path in ['/', '/dashboard', '/profile']:
            res = student_client.get(path, follow_redirects=False)
            self.assertEqual(res.status_code, 302)
            self.assertIn('/login', res.headers['Location'])

    def test_custom_student_renders_correct_details_on_refresh(self):
        """
        Verify that a newly registered/created student account:
        1. Logs in successfully.
        2. Renders their own dynamic name, roll number, and avatar initials upon initial load and refreshes.
        3. Does not display hardcoded fallback values.
        """
        admin_client = app.test_client()
        admin_client.post('/login', data={'email': 'admin@sst.scaler.com', 'password': 'admin123', 'role': 'Admin'})
        
        # Create student 'Aarav Sharma'
        admin_client.post('/api/admin/users',
                          data=json.dumps({
                              'name': 'Aarav Sharma',
                              'email': 'aarav.sharma@sst.scaler.com',
                              'password': 'scalerpassword123',
                              'role': 'Student',
                              'student_id': 'SST-2024-CS099'
                          }),
                          content_type='application/json')

        student_client = app.test_client()
        log_res = student_client.post('/login', data={'email': 'aarav.sharma@sst.scaler.com', 'password': 'scalerpassword123', 'role': 'Student'})
        self.assertEqual(log_res.status_code, 302)

        # First load & refresh
        for path in ['/', '/dashboard', '/profile']:
            res = student_client.get(path)
            self.assertEqual(res.status_code, 200)
            self.assertIn(b"Aarav Sharma", res.data)
            self.assertIn(b"SST-2024-CS099", res.data)
            self.assertIn(b"AS", res.data)  # Initials

    def test_baseline_students_nihal_and_sid_exist_and_persist_on_refresh(self):
        """
        Verify that pre-existing student accounts (Nihal Agarwal, sid) seeded in SQLite:
        1. Can log in with their credentials.
        2. Persist across page refreshes.
        3. Do not get overwritten by Admin or Sameer.
        """
        nihal_client = app.test_client()
        res_nihal = nihal_client.post('/login', data={'email': 'nihal@sst.scaler.com', 'password': 'scaler123', 'role': 'Student'})
        self.assertEqual(res_nihal.status_code, 302)

        # Refresh check
        dash_res = nihal_client.get('/dashboard')
        self.assertEqual(dash_res.status_code, 200)
        self.assertIn(b"Nihal Agarwal", dash_res.data)

        sid_client = app.test_client()
        res_sid = sid_client.post('/login', data={'email': 'sid@sst.scaler.com', 'password': 'scaler123', 'role': 'Student'})
        self.assertEqual(res_sid.status_code, 302)

        # Refresh check
        dash_sid = sid_client.get('/dashboard')
        self.assertEqual(dash_sid.status_code, 200)
        self.assertIn(b"sid", dash_sid.data)

    def test_unauthenticated_ticket_and_rating_endpoints_rejected(self):
        """
        Verify that POST /api/tickets and POST /api/submit-rating reject unauthenticated callers (401).
        """
        unauth_client = app.test_client()
        res_ticket = unauth_client.post('/api/tickets', data=json.dumps({"location": "Lab", "category": "IT"}), content_type='application/json')
        self.assertEqual(res_ticket.status_code, 401)

        res_rating = unauth_client.post('/api/submit-rating', data=json.dumps({"ticket_id": "TCK-1001", "quality": 5}), content_type='application/json')
        self.assertEqual(res_rating.status_code, 401)

    # =========================================================================
    # 3. ROLE-BASED ACCESS CONTROL (RBAC) & AUTHORIZATION TESTS
    # =========================================================================

    def test_rbac_1_unauthenticated_user_admin_page_rejected(self):
        """
        TEST 1: Unauthenticated user -> /admin -> rejected (302 redirect to /login)
        """
        res = self.app.get('/admin', follow_redirects=False)
        self.assertEqual(res.status_code, 302)
        self.assertIn('/login', res.headers['Location'])

    def test_rbac_2_student_admin_page_rejected(self):
        """
        TEST 2: Student -> /admin -> rejected (safe redirect to Student Dashboard, never renders admin page)
        """
        with self.app as client:
            client.post('/login', data={'email': 'sameer.verma@sst.scaler.com', 'password': 'scaler123', 'role': 'Student'})
            res = client.get('/admin', follow_redirects=False)
            # Must NOT be 200 (must be 302 redirect or 403 forbidden)
            self.assertIn(res.status_code, [302, 403])
            if res.status_code == 302:
                self.assertEqual(res.headers['Location'], '/')
            
            # If following redirect, verify user landed on Student Dashboard, NOT Admin Hub
            followed = client.get('/admin', follow_redirects=True)
            self.assertNotIn(b"Worker Management Directory", followed.data)
            self.assertNotIn(b"Campus User Management", followed.data)

    def test_rbac_3_admin_admin_page_allowed(self):
        """
        TEST 3: Admin -> /admin -> HTTP 200 (renders Admin Hub)
        """
        with self.app as client:
            client.post('/login', data={'email': 'admin@sst.scaler.com', 'password': 'admin123', 'role': 'Admin'})
            res = client.get('/admin', follow_redirects=False)
            self.assertEqual(res.status_code, 200)
            self.assertIn(b"Admin Hub", res.data)
            self.assertIn(b"Campus User Management", res.data)

    def test_rbac_4_student_get_admin_users_rejected(self):
        """
        TEST 4: Student -> GET /api/admin/users -> rejected (HTTP 403 Forbidden)
        """
        with self.app as client:
            client.post('/login', data={'email': 'sameer.verma@sst.scaler.com', 'password': 'scaler123', 'role': 'Student'})
            res = client.get('/api/admin/users')
            self.assertEqual(res.status_code, 403)
            data = json.loads(res.data)
            self.assertIn("Access restricted", data["error"])

    def test_rbac_5_student_post_admin_users_rejected(self):
        """
        TEST 5: Student -> POST /api/admin/users -> rejected (HTTP 403 Forbidden)
        """
        with self.app as client:
            client.post('/login', data={'email': 'sameer.verma@sst.scaler.com', 'password': 'scaler123', 'role': 'Student'})
            res = client.post('/api/admin/users', data=json.dumps({
                "name": "Hacker User",
                "email": "hacker.user@sst.scaler.com",
                "role": "Admin",
                "password": "pass"
            }), content_type='application/json')
            self.assertEqual(res.status_code, 403)
            data = json.loads(res.data)
            self.assertIn("Access restricted", data["error"])

    def test_rbac_6_admin_get_admin_users_allowed(self):
        """
        TEST 6: Admin -> GET /api/admin/users -> allowed (HTTP 200 OK)
        """
        with self.app as client:
            client.post('/login', data={'email': 'admin@sst.scaler.com', 'password': 'admin123', 'role': 'Admin'})
            res = client.get('/api/admin/users')
            self.assertEqual(res.status_code, 200)
            users = json.loads(res.data)
            self.assertIsInstance(users, list)

    def test_rbac_7_admin_post_admin_users_allowed(self):
        """
        TEST 7: Admin -> POST /api/admin/users -> allowed (HTTP 201 Created)
        """
        with self.app as client:
            client.post('/login', data={'email': 'admin@sst.scaler.com', 'password': 'admin123', 'role': 'Admin'})
            res = client.post('/api/admin/users', data=json.dumps({
                "name": "Authorized Student",
                "email": "auth.student@sst.scaler.com",
                "student_id": "SST-2024-AUTH",
                "role": "Student",
                "password": "validPassword123!"
            }), content_type='application/json')
            self.assertEqual(res.status_code, 201)

    def test_rbac_8_manipulated_login_role_cannot_grant_admin_access(self):
        """
        TEST 8: Manipulating the frontend role value (e.g. sending role='Admin' with Student credentials)
        MUST NOT grant admin access because the backend queries the user's true role from the database.
        """
        with self.app as client:
            # Sameer Verma is a Student in database, but sends role='Admin' in form
            res = client.post('/login', data={
                'email': 'sameer.verma@sst.scaler.com',
                'password': 'scaler123',
                'role': 'Admin' # <-- Attempted privilege escalation in request
            }, follow_redirects=False)
            
            # The backend must have set session['role'] to 'Student' from SQLite
            # Attempting to access /admin must be rejected
            admin_res = client.get('/admin', follow_redirects=False)
            self.assertIn(admin_res.status_code, [302, 403])
            
            api_res = client.get('/api/admin/users')
            self.assertEqual(api_res.status_code, 403)

    def test_rbac_9_student_access_to_all_admin_apis_rejected(self):
        """
        TEST 9: Student attempting to invoke any administrator-only API is rejected (HTTP 403).
        - Worker creation / edit / delete
        - CCTV Fine issuance
        - Ticket resolution by solver
        - User status toggle / delete
        """
        with self.app as client:
            client.post('/login', data={'email': 'sameer.verma@sst.scaler.com', 'password': 'scaler123', 'role': 'Student'})
            
            # 1. Worker Add
            res = client.post('/api/workers', data=json.dumps({"name": "Fake Worker", "category": "IT"}), content_type='application/json')
            self.assertEqual(res.status_code, 403)

            # 2. Worker Edit
            res = client.put('/api/workers/WKR-01', data=json.dumps({"name": "Hacked"}), content_type='application/json')
            self.assertEqual(res.status_code, 403)

            # 3. Worker Delete
            res = client.delete('/api/workers/WKR-01')
            self.assertEqual(res.status_code, 403)

            # 4. Issue Fine
            res = client.post('/api/issue-fine', data=json.dumps({"amount": 500}), content_type='application/json')
            self.assertEqual(res.status_code, 403)

            # 5. Resolve Ticket
            res = client.post('/api/tickets/TCK-1001/resolve')
            self.assertEqual(res.status_code, 403)

            # 6. User Status Toggle
            res = client.post('/api/admin/users/1/toggle-status')
            self.assertEqual(res.status_code, 403)

            # 7. User Delete
            res = client.delete('/api/admin/users/1')
            self.assertEqual(res.status_code, 403)

    def test_rbac_10_student_navigation_ui_elements(self):
        """
        Verify that when a Student is logged in:
        - Navigation renders: 'Student Portal' and 'Logout'
        - Navigation COMPLETELY HIDES: 'Admin Hub & CCTV', and links to '/admin'
        """
        with self.app as client:
            client.post('/login', data={'email': 'sameer.verma@sst.scaler.com', 'password': 'scaler123', 'role': 'Student'})
            res = client.get('/')
            self.assertEqual(res.status_code, 200)
            html = res.data.decode('utf-8')
            
            # Should be present
            self.assertIn("Student Portal", html)
            self.assertIn("Logout", html)
            self.assertIn("Tech Support Pro", html)
            
            # Should be completely hidden
            self.assertNotIn("Admin Hub & CCTV", html)
            self.assertNotIn('href="/admin"', html)

    def test_rbac_11_admin_navigation_ui_elements(self):
        """
        Verify that when an Admin is logged in:
        - Navigation renders: 'Admin Hub & CCTV' and 'Logout'
        - Navigation COMPLETELY HIDES: 'Student Portal'
        """
        with self.app as client:
            client.post('/login', data={'email': 'admin@sst.scaler.com', 'password': 'admin123', 'role': 'Admin'})
            res = client.get('/admin')
            self.assertEqual(res.status_code, 200)
            html = res.data.decode('utf-8')
            
            # Should be present
            self.assertIn("Admin Hub & CCTV", html)
            self.assertIn("Logout", html)
            self.assertIn("Campus Admin", html)
            
            # Should be completely hidden
            self.assertNotIn("Student Portal", html)

    # =========================================================================
    # 4. ADMIN USER MANAGEMENT CRUD TESTS
    # =========================================================================

    def test_admin_get_users_returns_list_without_passwords(self):
        """
        Verify that GET /api/admin/users returns the list of users and never exposes password_hash.
        """
        with self.app as client:
            client.post('/login', data={'email': 'admin@sst.scaler.com', 'password': 'admin123', 'role': 'Admin'})
            res = client.get('/api/admin/users')
            self.assertEqual(res.status_code, 200)
            users = json.loads(res.data)
            self.assertIsInstance(users, list)
            self.assertGreater(len(users), 0)
            for u in users:
                self.assertNotIn("password_hash", u)
                self.assertIn("email", u)
                self.assertIn("name", u)
                self.assertIn("role", u)

    def test_admin_create_user_success(self):
        """
        Verify that an Admin can create a new student account:
        - Email strictly ending with @sst.scaler.com
        - Stored in SQLite with password_hash (not plaintext)
        """
        with self.app as client:
            client.post('/login', data={'email': 'admin@sst.scaler.com', 'password': 'admin123', 'role': 'Admin'})
            new_user_payload = {
                "name": "Priya Sharma",
                "email": "priya.sharma@sst.scaler.com",
                "student_id": "SST-2024-CS088",
                "role": "Student",
                "password": "priyaSecurePass123!"
            }
            res = client.post('/api/admin/users',
                              data=json.dumps(new_user_payload),
                              content_type='application/json')
            self.assertEqual(res.status_code, 201)
            data = json.loads(res.data)
            self.assertEqual(data["user"]["name"], "Priya Sharma")
            self.assertEqual(data["user"]["email"], "priya.sharma@sst.scaler.com")
            self.assertNotIn("password_hash", data["user"])

            # Verify in SQLite database that password was hashed
            conn = get_db()
            cursor = conn.cursor()
            cursor.execute("SELECT password_hash FROM users WHERE email = 'priya.sharma@sst.scaler.com'")
            stored_hash = cursor.fetchone()[0]
            self.assertNotEqual(stored_hash, "priyaSecurePass123!")
            self.assertTrue(stored_hash.startswith("scrypt:") or stored_hash.startswith("pbkdf2:"))
            conn.close()

    def test_admin_create_user_duplicate_email_rejected(self):
        """
        Verify that attempting to create a user with an already existing email is rejected (409).
        """
        with self.app as client:
            client.post('/login', data={'email': 'admin@sst.scaler.com', 'password': 'admin123', 'role': 'Admin'})
            duplicate_payload = {
                "name": "Duplicate Sameer",
                "email": "sameer.verma@sst.scaler.com",
                "student_id": "SST-2024-CS999",
                "role": "Student",
                "password": "anyPassword123"
            }
            res = client.post('/api/admin/users',
                              data=json.dumps(duplicate_payload),
                              content_type='application/json')
            self.assertEqual(res.status_code, 409)
            data = json.loads(res.data)
            self.assertIn("already exists", data["error"])

    def test_admin_create_user_invalid_domain_rejected(self):
        """
        Verify that attempting to create a user with a non-@sst.scaler.com email is rejected (400).
        """
        with self.app as client:
            client.post('/login', data={'email': 'admin@sst.scaler.com', 'password': 'admin123', 'role': 'Admin'})
            invalid_domain_payload = {
                "name": "External User",
                "email": "external.user@gmail.com",
                "student_id": "EXT-01",
                "role": "Student",
                "password": "anyPassword123"
            }
            res = client.post('/api/admin/users',
                              data=json.dumps(invalid_domain_payload),
                              content_type='application/json')
            self.assertEqual(res.status_code, 400)
            data = json.loads(res.data)
            self.assertIn("strictly end with @sst.scaler.com", data["error"])

    def test_newly_created_user_incorrect_password_rejected(self):
        """
        Verify that a newly created user cannot log in with an incorrect password (401).
        """
        with self.app as client:
            # 1. Admin creates user
            client.post('/login', data={'email': 'admin@sst.scaler.com', 'password': 'admin123', 'role': 'Admin'})
            client.post('/api/admin/users', data=json.dumps({
                "name": "Ananya Roy",
                "email": "ananya.roy@sst.scaler.com",
                "student_id": "SST-2024-CS055",
                "role": "Student",
                "password": "correctSecretPassword123"
            }), content_type='application/json')
            client.get('/logout')

            # 2. Try logging in with wrong password
            login_res = client.post('/login', data={
                'email': 'ananya.roy@sst.scaler.com',
                'password': 'wrongWrongPassword999',
                'role': 'Student'
            })
            self.assertEqual(login_res.status_code, 401)
            self.assertIn(b"Invalid email or password.", login_res.data)

    def test_newly_created_user_can_login_with_correct_password(self):
        """
        Verify that a newly created user can successfully log in with their correct password (200).
        """
        with self.app as client:
            # 1. Admin creates user
            client.post('/login', data={'email': 'admin@sst.scaler.com', 'password': 'admin123', 'role': 'Admin'})
            client.post('/api/admin/users', data=json.dumps({
                "name": "Karan Malhotra",
                "email": "karan.malhotra@sst.scaler.com",
                "student_id": "SST-2024-CS077",
                "role": "Student",
                "password": "karanPassword2026!"
            }), content_type='application/json')
            client.get('/logout')

            # 2. Log in with correct password
            login_res = client.post('/login', data={
                'email': 'karan.malhotra@sst.scaler.com',
                'password': 'karanPassword2026!',
                'role': 'Student'
            }, follow_redirects=True)
            self.assertEqual(login_res.status_code, 200)
            self.assertIn(b"NextCamp", login_res.data)
            self.assertIn(b"Karan Malhotra", login_res.data)

    def test_admin_toggle_user_active_and_deactivated_login_blocked(self):
        """
        Verify that:
        1. Admin can toggle user active status (Active -> Deactivated).
        2. Deactivated user login is rejected with HTTP 403.
        3. Re-activating user allows login to succeed.
        """
        with self.app as client:
            # 1. Admin creates user
            client.post('/login', data={'email': 'admin@sst.scaler.com', 'password': 'admin123', 'role': 'Admin'})
            create_res = client.post('/api/admin/users', data=json.dumps({
                "name": "Rohan Gupta",
                "email": "rohan.gupta@sst.scaler.com",
                "student_id": "SST-2024-CS033",
                "role": "Student",
                "password": "rohanPassword123"
            }), content_type='application/json')
            user_id = json.loads(create_res.data)["user"]["id"]

            # 2. Deactivate user
            toggle_res = client.post(f'/api/admin/users/{user_id}/toggle-status')
            self.assertEqual(toggle_res.status_code, 200)
            self.assertEqual(json.loads(toggle_res.data)["is_active"], 0)
            client.get('/logout')

            # 3. Deactivated login attempt -> 403
            deactivated_login = client.post('/login', data={
                'email': 'rohan.gupta@sst.scaler.com',
                'password': 'rohanPassword123',
                'role': 'Student'
            })
            self.assertEqual(deactivated_login.status_code, 403)
            self.assertIn(b"Account is deactivated.", deactivated_login.data)

            # 4. Re-activate user
            client.post('/login', data={'email': 'admin@sst.scaler.com', 'password': 'admin123', 'role': 'Admin'})
            client.post(f'/api/admin/users/{user_id}/toggle-status')
            client.get('/logout')

            # 5. Active login attempt -> 200
            active_login = client.post('/login', data={
                'email': 'rohan.gupta@sst.scaler.com',
                'password': 'rohanPassword123',
                'role': 'Student'
            }, follow_redirects=True)
            self.assertEqual(active_login.status_code, 200)

    def test_admin_delete_user(self):
        """
        Verify that Admin can delete a user record from SQLite.
        """
        with self.app as client:
            # 1. Admin creates user
            client.post('/login', data={'email': 'admin@sst.scaler.com', 'password': 'admin123', 'role': 'Admin'})
            create_res = client.post('/api/admin/users', data=json.dumps({
                "name": "Temp User",
                "email": "temp.user@sst.scaler.com",
                "student_id": "SST-TEMP-01",
                "role": "Student",
                "password": "tempPassword123"
            }), content_type='application/json')
            user_id = json.loads(create_res.data)["user"]["id"]

            # 2. Delete user
            del_res = client.delete(f'/api/admin/users/{user_id}')
            self.assertEqual(del_res.status_code, 200)

            # 3. Verify user removed from SQLite
            conn = get_db()
            cursor = conn.cursor()
            cursor.execute("SELECT * FROM users WHERE id = ?", (user_id,))
            self.assertIsNone(cursor.fetchone())
            conn.close()

    # =========================================================================
    # 5. SMART PROBLEM ALLOCATION TESTS
    # =========================================================================

    def test_smart_allocation_electrical_picks_ravi(self):
        """
        Verify that submitting an Electrical issue allocates Ravi (rating ⭐ 4.9).
        """
        worker = allocate_smart_worker("Electrical")
        self.assertIsNotNone(worker)
        self.assertEqual(worker["name"], "Ravi")
        self.assertEqual(worker["rating"], 4.9)

    def test_report_problem_endpoint_returns_formatted_solver_display(self):
        """
        Verify that POST /api/report-problem runs allocation and returns
        'Assigned to: Ravi (⭐ 4.9)' and stores in database.
        """
        with self.app as client:
            client.post('/login', data={
                'email': 'sameer.verma@sst.scaler.com',
                'password': 'scaler123',
                'role': 'Student'
            })
            payload = {
                "location": "Hostel Block B, Room 204",
                "category": "Electrical",
                "urgency": "High",
                "description": "Switchboard sparks when fan is switched on"
            }
            res = client.post('/api/report-problem',
                              data=json.dumps(payload),
                              content_type='application/json')
            self.assertEqual(res.status_code, 201)
            data = json.loads(res.data)
            self.assertIn("Assigned to: Ravi (⭐ 4.9)", data["solver_display"])
            self.assertEqual(data["ticket"]["solver_name"], "Ravi")
            self.assertEqual(data["ticket"]["assigned_worker"], "Ravi")

    # =========================================================================
    # 6. CCTV DAMAGE REVIEW & FINE ISSUANCE TESTS
    # =========================================================================

    def test_cctv_issue_fine_updates_student_status_and_applies_fine(self):
        """
        Verify that clicking [Review & Issue Fine ₹500] (/api/issue-fine) as Admin
        updates student status from 'Good Standing 🟢' to 'Action Required 🔴'
        and applies a ₹500 fine in SQLite.
        """
        with self.app as client:
            client.post('/login', data={'email': 'admin@sst.scaler.com', 'password': 'admin123', 'role': 'Admin'})
            res = client.post('/api/issue-fine',
                              data=json.dumps({"amount": 500, "reason": "Classroom 204 — 3:20 PM - Damaged Chair"}),
                              content_type='application/json')
            self.assertEqual(res.status_code, 200)
            data = json.loads(res.data)
            self.assertEqual(data["student"]["fine_amount"], 500)
            self.assertEqual(data["student"]["status"], "Action Required 🔴")

            # Verify via profile endpoint
            prof_res = client.get('/api/student/profile')
            prof_data = json.loads(prof_res.data)
            self.assertEqual(prof_data["status"], "Action Required 🔴")
            self.assertEqual(prof_data["fine_amount"], 500)

    def test_cctv_issue_fine_dynamic_student_and_amount(self):
        """
        Verify the dynamic Damage Review & Penalty flow:
        1. Admin selects a specific student from the database (Student A).
        2. Admin enters dynamic amount (e.g. ₹300).
        3. Penalty is issued and saved to the SQLite database.
        4. Student A sees ₹300 pending fine on dashboard and in Fine History.
        5. Admin Fine Management master ledger and student inspector show the fine.
        6. Student B does NOT see Student A's fine.
        7. Student A pays fine -> marked as Paid, recorded in history.
        """
        with self.app as client:
            # 1. Admin login & create two students
            client.post('/login', data={'email': 'admin@sst.scaler.com', 'password': 'admin123', 'role': 'Admin'})
            u1_res = client.post('/api/admin/users',
                                 data=json.dumps({
                                     'name': 'Pooja Hegde',
                                     'email': 'pooja.hegde@sst.scaler.com',
                                     'password': 'scalerpassword123',
                                     'role': 'Student',
                                     'student_id': 'SST-2024-CS081'
                                 }),
                                 content_type='application/json')
            pooja_id = json.loads(u1_res.data)['user']['id']

            u2_res = client.post('/api/admin/users',
                                 data=json.dumps({
                                     'name': 'Karan Singh',
                                     'email': 'karan.singh@sst.scaler.com',
                                     'password': 'scalerpassword123',
                                     'role': 'Student',
                                     'student_id': 'SST-2024-CS082'
                                 }),
                                 content_type='application/json')
            karan_id = json.loads(u2_res.data)['user']['id']

            # 2. Admin issues dynamic fine of ₹300 to Pooja (Student A) via CCTV endpoint
            issue_res = client.post('/api/issue-fine',
                                    data=json.dumps({
                                        'user_id': pooja_id,
                                        'amount': 300,
                                        'reason': 'Classroom 204 — 3:20 PM - Damaged Chair'
                                    }),
                                    content_type='application/json')
            self.assertEqual(issue_res.status_code, 200)
            issue_data = json.loads(issue_res.data)
            self.assertEqual(issue_data['fine']['amount'], 300)
            self.assertEqual(issue_data['fine']['student_name'], 'Pooja Hegde')
            self.assertEqual(issue_data['fine']['status'], 'Pending')

            # 3. Student A (Pooja) logs in -> sees ₹300 pending fine in profile & fine history
            client.post('/login', data={'email': 'pooja.hegde@sst.scaler.com', 'password': 'scalerpassword123', 'role': 'Student'})
            pooja_prof = json.loads(client.get('/api/student/profile').data)
            self.assertEqual(pooja_prof['fine_amount'], 300)
            self.assertEqual(pooja_prof['status'], 'Action Required 🔴')

            pooja_fines = json.loads(client.get('/api/student/fines').data)
            self.assertEqual(pooja_fines['total_fines'], 1)
            self.assertEqual(pooja_fines['total_pending_amount'], 300)
            self.assertEqual(pooja_fines['fines'][0]['amount'], 300)

            # 4. Student B (Karan) logs in -> has 0 fines
            client.post('/login', data={'email': 'karan.singh@sst.scaler.com', 'password': 'scalerpassword123', 'role': 'Student'})
            karan_fines = json.loads(client.get('/api/student/fines').data)
            self.assertEqual(karan_fines['total_fines'], 0)
            self.assertEqual(karan_fines['total_pending_amount'], 0)

            # 5. Admin master ledger & student inspector show the fine
            client.post('/login', data={'email': 'admin@sst.scaler.com', 'password': 'admin123', 'role': 'Admin'})
            admin_master = json.loads(client.get('/api/admin/fines').data)
            pooja_in_master = next(f for f in admin_master['fines'] if f['user_id'] == pooja_id)
            self.assertEqual(pooja_in_master['amount'], 300)
            self.assertEqual(pooja_in_master['status'], 'Pending')

            # 6. Student A pays fine -> status transitions to Paid
            client.post('/login', data={'email': 'pooja.hegde@sst.scaler.com', 'password': 'scalerpassword123', 'role': 'Student'})
            pay_res = client.post('/api/student/pay-fine')
            self.assertEqual(pay_res.status_code, 200)

            pooja_after_pay = json.loads(client.get('/api/student/fines').data)
            self.assertEqual(pooja_after_pay['total_pending_amount'], 0)
            self.assertEqual(pooja_after_pay['total_paid_amount'], 300)
            self.assertEqual(pooja_after_pay['fines'][0]['status'], 'Paid')
            self.assertIsNotNone(pooja_after_pay['fines'][0]['paid_at'])

    # =========================================================================
    # 7. WORKER MANAGEMENT (CRUD) TESTS
    # =========================================================================

    def test_worker_crud_and_dynamic_smart_allocation(self):
        """
        Verify:
        1. ➕ Adding a new worker as Admin defaults to rating ⭐ 5.0 and tasks solved 0.
        2. Newly added worker with ⭐ 5.0 is picked by smart allocation for their category!
        3. ✏️ Editing worker name / category works.
        4. 🗑️ Deleting worker works.
        """
        with self.app as client:
            client.post('/login', data={'email': 'admin@sst.scaler.com', 'password': 'admin123', 'role': 'Admin'})
            
            # 1. Add New Worker
            add_res = client.post('/api/workers',
                                  data=json.dumps({"name": "Dev Sharma", "category": "Hardware"}),
                                  content_type='application/json')
            self.assertEqual(add_res.status_code, 201)
            add_data = json.loads(add_res.data)
            new_worker_id = add_data["worker"]["id"]
            self.assertEqual(add_data["worker"]["rating"], 5.0)
            self.assertEqual(add_data["worker"]["tasks_solved"], 0)

            # 2. Smart allocation for Hardware should now pick Dev Sharma (⭐ 5.0 > Amit Singh ⭐ 4.8)
            selected = allocate_smart_worker("Hardware")
            self.assertEqual(selected["name"], "Dev Sharma")
            self.assertEqual(selected["rating"], 5.0)

            # 3. Edit Worker
            edit_res = client.put(f'/api/workers/{new_worker_id}',
                                  data=json.dumps({"name": "Devendra Sharma", "category": "Hardware"}),
                                  content_type='application/json')
            self.assertEqual(edit_res.status_code, 200)
            edit_data = json.loads(edit_res.data)
            self.assertEqual(edit_data["worker"]["name"], "Devendra Sharma")

            # 4. Delete Worker
            del_res = client.delete(f'/api/workers/{new_worker_id}')
            self.assertEqual(del_res.status_code, 200)

    # =========================================================================
    # 8. EVENT BOOKING & TIME CLASH DETECTION TESTS
    # =========================================================================

    def test_event_booking_no_conflict_success_and_sqlite_persistence(self):
        """
        1. Event can be created when there is no conflict.
        2. Event is saved in SQLite database.
        """
        with self.app as client:
            client.post('/login', data={'email': 'sameer.verma@sst.scaler.com', 'password': 'scaler123', 'role': 'Student'})
            payload = {
                "name": "Design Sprint 2026",
                "venue": "Innovation Hub",
                "date": "Tomorrow",
                "start_time": "10:00",
                "end_time": "13:00",
                "organizer": "Student Council"
            }
            res = client.post('/api/events/book', data=json.dumps(payload), content_type='application/json')
            self.assertEqual(res.status_code, 201)
            data = json.loads(res.data)
            self.assertFalse(data["clash"])
            self.assertEqual(data["event"]["name"], "Design Sprint 2026")
            
            # Verify in SQLite database
            conn = get_db()
            cursor = conn.cursor()
            cursor.execute("SELECT * FROM events WHERE name = 'Design Sprint 2026'")
            row = cursor.fetchone()
            self.assertIsNotNone(row)
            self.assertEqual(row["venue"], "Innovation Hub")
            self.assertEqual(row["start_time"], "10:00")
            self.assertEqual(row["end_time"], "13:00")
            conn.close()

    def test_event_booking_same_venue_overlapping_time_rejected(self):
        """
        3. Same venue + overlapping time is rejected with HTTP 409.
        7. Conflict returns HTTP 409.
        8. Conflict response contains the actual existing event information.
        """
        with self.app as client:
            client.post('/login', data={'email': 'sameer.verma@sst.scaler.com', 'password': 'scaler123', 'role': 'Student'})
            # Existing seed event in Main Auditorium on Today is 09:00 - 18:00 (Annual Tech Symposium 2026)
            payload = {
                "name": "SST AI Demo Day",
                "venue": "Main Auditorium",
                "date": "Today",
                "start_time": "11:00",
                "end_time": "14:00"
            }
            res = client.post('/api/events/book', data=json.dumps(payload), content_type='application/json')
            self.assertEqual(res.status_code, 409)
            data = json.loads(res.data)
            self.assertEqual(data["error"], "schedule_conflict")
            self.assertTrue(data["clash"])
            self.assertIn("Annual Tech Symposium 2026", data["message"])
            self.assertIn("Main Auditorium", data["message"])
            
            # Check structured conflicting_event object
            conflicting = data["conflicting_event"]
            self.assertEqual(conflicting["name"], "Annual Tech Symposium 2026")
            self.assertEqual(conflicting["organizer"], "SST Tech Society")
            self.assertEqual(conflicting["venue"], "Main Auditorium")
            self.assertEqual(conflicting["start_time"], "09:00")
            self.assertEqual(conflicting["end_time"], "18:00")

    def test_event_booking_same_venue_non_overlapping_time_allowed(self):
        """
        4. Same venue + non-overlapping time is allowed (HTTP 201).
        """
        with self.app as client:
            client.post('/login', data={'email': 'sameer.verma@sst.scaler.com', 'password': 'scaler123', 'role': 'Student'})
            # Existing seed event in Block C Exam Hall on Today is 10:00 - 17:00
            # Booking 17:30 - 20:00 (after existing event) should succeed
            payload = {
                "name": "Evening Study Circle",
                "venue": "Block C Exam Hall",
                "date": "Today",
                "start_time": "17:30",
                "end_time": "20:00"
            }
            res = client.post('/api/events/book', data=json.dumps(payload), content_type='application/json')
            self.assertEqual(res.status_code, 201)
            data = json.loads(res.data)
            self.assertFalse(data["clash"])

    def test_event_booking_different_venue_same_time_allowed(self):
        """
        5. Different venue + same time is allowed (HTTP 201).
        """
        with self.app as client:
            client.post('/login', data={'email': 'sameer.verma@sst.scaler.com', 'password': 'scaler123', 'role': 'Student'})
            # Existing event is in Main Auditorium 09:00 - 18:00 on Today
            # Booking Innovation Hub 09:00 - 18:00 on Today should succeed
            payload = {
                "name": "Parallel Innovation Workshop",
                "venue": "Innovation Hub",
                "date": "Today",
                "start_time": "09:00",
                "end_time": "18:00"
            }
            res = client.post('/api/events/book', data=json.dumps(payload), content_type='application/json')
            self.assertEqual(res.status_code, 201)
            data = json.loads(res.data)
            self.assertFalse(data["clash"])

    def test_event_booking_different_date_same_venue_and_time_allowed(self):
        """
        6. Different date + same venue/time is allowed (HTTP 201).
        """
        with self.app as client:
            client.post('/login', data={'email': 'sameer.verma@sst.scaler.com', 'password': 'scaler123', 'role': 'Student'})
            # Existing event is in Main Auditorium 09:00 - 18:00 on Today
            # Booking Main Auditorium 09:00 - 18:00 on Next Week Monday should succeed
            payload = {
                "name": "Next Week Auditorium Keynote",
                "venue": "Main Auditorium",
                "date": "2026-09-01",
                "start_time": "09:00",
                "end_time": "18:00"
            }
            res = client.post('/api/events/book', data=json.dumps(payload), content_type='application/json')
            self.assertEqual(res.status_code, 201)
            data = json.loads(res.data)
            self.assertFalse(data["clash"])

    def test_event_booking_invalid_time_range_rejected(self):
        """
        9. Invalid time range (end time before or equal to start time) is rejected with HTTP 400.
        """
        with self.app as client:
            client.post('/login', data={'email': 'sameer.verma@sst.scaler.com', 'password': 'scaler123', 'role': 'Student'})
            # End time (10:00) is before start time (14:00)
            payload = {
                "name": "Time Traveler Meetup",
                "venue": "Innovation Hub",
                "date": "Tomorrow",
                "start_time": "14:00",
                "end_time": "10:00"
            }
            res = client.post('/api/events/book', data=json.dumps(payload), content_type='application/json')
            self.assertEqual(res.status_code, 400)
            data = json.loads(res.data)
            self.assertIn("Invalid time range", data["error"])

    def test_event_booking_unauthenticated_user_rejected(self):
        """
        10. Unauthenticated user cannot perform event booking.
        """
        payload = {
            "name": "Unauthorized Event",
            "venue": "Main Auditorium",
            "date": "Tomorrow",
            "start_time": "10:00",
            "end_time": "12:00"
        }
        res = self.app.post('/api/events/book', data=json.dumps(payload), content_type='application/json')
        self.assertIn(res.status_code, [401, 302])

    def test_get_events_returns_database_events_with_all_fields(self):
        """
        Verify that GET /api/events returns actual SQLite events with all expected fields:
        id, name, organizer, venue, date, start_time, end_time, status.
        """
        with self.app as client:
            client.post('/login', data={'email': 'sameer.verma@sst.scaler.com', 'password': 'scaler123', 'role': 'Student'})
            res = client.get('/api/events')
            self.assertEqual(res.status_code, 200)
            events = json.loads(res.data)
            self.assertIsInstance(events, list)
            self.assertGreaterEqual(len(events), 3)
            
            # Check fields on first event
            first = events[0]
            for field in ["id", "name", "organizer", "venue", "date", "start_time", "end_time", "status"]:
                self.assertIn(field, first)

    def test_newly_created_event_immediately_reflected_in_get_events(self):
        """
        Verify that creating a new event immediately appears in GET /api/events
        without needing server restart.
        """
        with self.app as client:
            client.post('/login', data={'email': 'sameer.verma@sst.scaler.com', 'password': 'scaler123', 'role': 'Student'})
            
            # 1. Create new event
            new_event_payload = {
                "name": "SST Autonomous Robotics Demo",
                "venue": "Innovation Hub",
                "date": "Tomorrow",
                "start_time": "11:00",
                "end_time": "14:00"
            }
            book_res = client.post('/api/events/book', data=json.dumps(new_event_payload), content_type='application/json')
            self.assertEqual(book_res.status_code, 201)
            
            # 2. Retrieve all events
            list_res = client.get('/api/events')
            self.assertEqual(list_res.status_code, 200)
            events = json.loads(list_res.data)
            
            # 3. Verify newly created event is in list
            found = [e for e in events if e["name"] == "SST Autonomous Robotics Demo"]
            self.assertEqual(len(found), 1)
            self.assertEqual(found[0]["venue"], "Innovation Hub")
            self.assertEqual(found[0]["start_time"], "11:00")
            self.assertEqual(found[0]["end_time"], "14:00")

    def test_get_events_empty_database_returns_empty_list(self):
        """
        Verify that if the events table is empty, GET /api/events returns an empty array []
        and never returns mock/fake events.
        """
        with self.app as client:
            client.post('/login', data={'email': 'sameer.verma@sst.scaler.com', 'password': 'scaler123', 'role': 'Student'})
            
            # Clear events table in SQLite
            conn = get_db()
            cursor = conn.cursor()
            cursor.execute("DELETE FROM events")
            conn.commit()
            conn.close()
            
            res = client.get('/api/events')
            self.assertEqual(res.status_code, 200)
            events = json.loads(res.data)
            self.assertEqual(events, [])

    def test_get_events_unauthenticated_rejected(self):
        """
        Verify that unauthenticated access to GET /api/events is rejected (401 or 302).
        """
        res = self.app.get('/api/events')
        self.assertIn(res.status_code, [401, 302])

    # =========================================================================
    # 8b. EVENT REGISTRATION / RSVP TESTS
    # =========================================================================

    def test_rsvp_1_student_can_register_for_event_and_persisted(self):
        """
        1. Student can register for an existing event.
        2. Registration is stored in SQLite event_registrations table.
        """
        with self.app as client:
            client.post('/login', data={'email': 'sameer.verma@sst.scaler.com', 'password': 'scaler123', 'role': 'Student'})
            res = client.post('/api/events/EVT-101/register', content_type='application/json')
            self.assertEqual(res.status_code, 201)
            data = json.loads(res.data)
            self.assertTrue(data["success"])
            self.assertEqual(data["registration"]["event_id"], "EVT-101")

            # Verify in SQLite
            conn = get_db()
            cursor = conn.cursor()
            cursor.execute("SELECT * FROM event_registrations WHERE event_id = 'EVT-101' AND student_email = 'sameer.verma@sst.scaler.com'")
            row = cursor.fetchone()
            self.assertIsNotNone(row)
            self.assertEqual(row["student_name"], "Sameer Verma")
            conn.close()

    def test_rsvp_2_duplicate_registration_rejected(self):
        """
        3. Student cannot register for the same event twice (HTTP 409 already_registered).
        """
        with self.app as client:
            client.post('/login', data={'email': 'sameer.verma@sst.scaler.com', 'password': 'scaler123', 'role': 'Student'})
            # First registration
            res1 = client.post('/api/events/EVT-102/register', content_type='application/json')
            self.assertEqual(res1.status_code, 201)

            # Duplicate registration attempt
            res2 = client.post('/api/events/EVT-102/register', content_type='application/json')
            self.assertEqual(res2.status_code, 409)
            data = json.loads(res2.data)
            self.assertEqual(data["error"], "already_registered")

    def test_rsvp_3_two_different_students_can_register(self):
        """
        4. Two different students can register for the same event.
        """
        with self.app as client:
            # 1. Admin creates a second student
            client.post('/login', data={'email': 'admin@sst.scaler.com', 'password': 'admin123', 'role': 'Admin'})
            client.post('/api/admin/users', data=json.dumps({
                "name": "Rohan Gupta",
                "email": "rohan.gupta@sst.scaler.com",
                "student_id": "SST-2024-CS088",
                "role": "Student",
                "password": "rohanPassword123"
            }), content_type='application/json')
            client.get('/logout')

            # 2. Student 1 (Sameer) registers
            client.post('/login', data={'email': 'sameer.verma@sst.scaler.com', 'password': 'scaler123', 'role': 'Student'})
            res1 = client.post('/api/events/EVT-103/register', content_type='application/json')
            self.assertEqual(res1.status_code, 201)
            client.get('/logout')

            # 3. Student 2 (Rohan) registers
            client.post('/login', data={'email': 'rohan.gupta@sst.scaler.com', 'password': 'rohanPassword123', 'role': 'Student'})
            res2 = client.post('/api/events/EVT-103/register', content_type='application/json')
            self.assertEqual(res2.status_code, 201)

            # Verify SQLite has both records
            conn = get_db()
            cursor = conn.cursor()
            cursor.execute("SELECT COUNT(*) FROM event_registrations WHERE event_id = 'EVT-103'")
            count = cursor.fetchone()[0]
            self.assertEqual(count, 2)
            conn.close()

    def test_rsvp_4_nonexistent_event_rejected(self):
        """
        5. Nonexistent event registration is rejected (HTTP 404).
        """
        with self.app as client:
            client.post('/login', data={'email': 'sameer.verma@sst.scaler.com', 'password': 'scaler123', 'role': 'Student'})
            res = client.post('/api/events/EVT-999999/register', content_type='application/json')
            self.assertEqual(res.status_code, 404)

    def test_rsvp_5_unauthenticated_registration_rejected(self):
        """
        6. Unauthenticated registration is rejected (HTTP 401 or 302).
        """
        res = self.app.post('/api/events/EVT-101/register', content_type='application/json')
        self.assertIn(res.status_code, [401, 302])

    def test_rsvp_6_admin_cannot_register_as_student(self):
        """
        Admin attempting to register for an event is rejected with HTTP 403.
        """
        with self.app as client:
            client.post('/login', data={'email': 'admin@sst.scaler.com', 'password': 'admin123', 'role': 'Admin'})
            res = client.post('/api/events/EVT-101/register', content_type='application/json')
            self.assertEqual(res.status_code, 403)

    def test_rsvp_7_admin_can_view_event_registrations(self):
        """
        7. Admin can view event registrations roster.
        """
        with self.app as client:
            # Student registers for EVT-101
            client.post('/login', data={'email': 'sameer.verma@sst.scaler.com', 'password': 'scaler123', 'role': 'Student'})
            client.post('/api/events/EVT-101/register', content_type='application/json')
            client.get('/logout')

            # Admin inspects registrations
            client.post('/login', data={'email': 'admin@sst.scaler.com', 'password': 'admin123', 'role': 'Admin'})
            res = client.get('/api/admin/events/EVT-101/registrations')
            self.assertEqual(res.status_code, 200)
            data = json.loads(res.data)
            self.assertEqual(data["event"]["id"], "EVT-101")
            self.assertGreaterEqual(len(data["registrations"]), 1)
            self.assertEqual(data["registrations"][0]["student_name"], "Sameer Verma")
            self.assertEqual(data["registrations"][0]["student_email"], "sameer.verma@sst.scaler.com")

    def test_rsvp_8_student_cannot_access_admin_registration_roster(self):
        """
        8. Student cannot access the Admin registration list (HTTP 403).
        """
        with self.app as client:
            client.post('/login', data={'email': 'sameer.verma@sst.scaler.com', 'password': 'scaler123', 'role': 'Student'})
            res = client.get('/api/admin/events/EVT-101/registrations')
            self.assertEqual(res.status_code, 403)

    def test_rsvp_9_student_can_retrieve_own_registered_events(self):
        """
        9. Student can retrieve their own registered events (GET /api/student/my-registrations).
        """
        with self.app as client:
            client.post('/login', data={'email': 'sameer.verma@sst.scaler.com', 'password': 'scaler123', 'role': 'Student'})
            client.post('/api/events/EVT-101/register', content_type='application/json')
            
            res = client.get('/api/student/my-registrations')
            self.assertEqual(res.status_code, 200)
            registrations = json.loads(res.data)
            self.assertIsInstance(registrations, list)
            self.assertGreaterEqual(len(registrations), 1)
            self.assertEqual(registrations[0]["event_id"], "EVT-101")
            self.assertEqual(registrations[0]["event_name"], "Annual Tech Symposium 2026")

    def test_rsvp_10_capacity_limits_registration_when_full(self):
        """
        10. Capacity limits prevent registration when the event is full (HTTP 409 event_full).
        """
        with self.app as client:
            # 1. Admin creates an event with capacity = 1
            client.post('/login', data={'email': 'admin@sst.scaler.com', 'password': 'admin123', 'role': 'Admin'})
            evt_payload = {
                "name": "VIP Round Table 2026",
                "venue": "Innovation Hub",
                "date": "2026-09-10",
                "start_time": "14:00",
                "end_time": "16:00",
                "capacity": 1
            }
            create_res = client.post('/api/events/book', data=json.dumps(evt_payload), content_type='application/json')
            self.assertEqual(create_res.status_code, 201)
            event_id = json.loads(create_res.data)["event"]["id"]
            
            # Create a second student
            client.post('/api/admin/users', data=json.dumps({
                "name": "Student Two",
                "email": "student.two@sst.scaler.com",
                "student_id": "SST-2024-CS099",
                "role": "Student",
                "password": "studentTwoPassword!"
            }), content_type='application/json')
            client.get('/logout')

            # 2. Student 1 registers (fills the 1 available seat)
            client.post('/login', data={'email': 'sameer.verma@sst.scaler.com', 'password': 'scaler123', 'role': 'Student'})
            reg1 = client.post(f'/api/events/{event_id}/register', content_type='application/json')
            self.assertEqual(reg1.status_code, 201)
            client.get('/logout')

            # 3. Student 2 attempts to register (event is full -> HTTP 409)
            client.post('/login', data={'email': 'student.two@sst.scaler.com', 'password': 'studentTwoPassword!', 'role': 'Student'})
            reg2 = client.post(f'/api/events/{event_id}/register', content_type='application/json')
            self.assertEqual(reg2.status_code, 409)
            data = json.loads(reg2.data)
            self.assertEqual(data["error"], "event_full")

    # =========================================================================
    # 9. POST-RESOLUTION RATING SYSTEM & REVIEWS LOG TESTS
    # =========================================================================

    def test_ticket_resolution_workflow(self):
        """
        Verify that marking a ticket as Resolved via POST /api/tickets/<id>/resolve as Admin
        updates ticket status to 'Resolved' in SQLite.
        """
        with self.app as client:
            client.post('/login', data={'email': 'admin@sst.scaler.com', 'password': 'admin123', 'role': 'Admin'})
            res = client.post('/api/tickets/TCK-1001/resolve')
            self.assertEqual(res.status_code, 200)
            data = json.loads(res.data)
            self.assertEqual(data["ticket"]["status"], "Resolved")

    def test_submit_rating_awards_reputation_and_recalculates_worker_rating(self):
        """
        Verify that submitting a 3-dimensional rating (Response Time: 5, Quality: 4, Behavior: 5):
        1. Calculates average score (4.67)
        2. Recalculates worker cumulative rating in SQLite
        3. Awards +5 Reputation Points to reporting student in SQLite
        4. Appends review to Reviews table
        """
        with self.app as client:
            client.post('/login', data={
                'email': 'sameer.verma@sst.scaler.com',
                'password': 'scaler123',
                'role': 'Student'
            })

            rating_payload = {
                "ticket_id": "TCK-1001",
                "solver_name": "Ravi",
                "worker_id": "WKR-01",
                "category": "Electrical",
                "response_time": 5,
                "quality": 4,
                "behavior": 5,
                "suggestion": "Arrived promptly and replaced the faulty breaker safely."
            }

            res = client.post('/api/submit-rating',
                              data=json.dumps(rating_payload),
                              content_type='application/json')
            self.assertEqual(res.status_code, 200)
            data = json.loads(res.data)

            # 1. Average score check: (5 + 4 + 5) / 3 = 4.67
            self.assertEqual(data["avg_rating"], 4.67)

            # 2. Student reputation awarded check (+5 points: 94 + 5 = 99)
            self.assertEqual(data["reputation_points"], 99)

            # 3. Worker cumulative tasks count incremented (84 + 1 = 85)
            self.assertEqual(data["worker"]["tasks_solved"], 85)

            # 4. Review object appended to Reviews table
            self.assertEqual(data["review"]["student_name"], "Sameer Verma")
            self.assertEqual(data["review"]["worker_name"], "Ravi")
            self.assertEqual(data["review"]["avg_rating"], 4.67)

    def test_reviews_endpoint_returns_review_log(self):
        """
        Verify that GET /api/reviews returns the log of student submitted reviews from SQLite.
        """
        with self.app as client:
            client.post('/login', data={'email': 'sameer.verma@sst.scaler.com', 'password': 'scaler123', 'role': 'Student'})
            res = client.get('/api/reviews')
            self.assertEqual(res.status_code, 200)
            reviews = json.loads(res.data)
            self.assertIsInstance(reviews, list)
            self.assertGreater(len(reviews), 0)
            self.assertIn("worker_name", reviews[0])
            self.assertIn("rating", reviews[0])
            self.assertIn("suggestion", reviews[0])

    # =========================================================================
    # 10. CAMPUS ANNOUNCEMENTS & BROADCAST CONTROL TESTS
    # =========================================================================

    def test_announcements_1_admin_can_create_and_persisted_in_sqlite(self):
        """
        1. Admin can create an announcement.
        2. Stored in SQLite announcements table.
        """
        with self.app as client:
            client.post('/login', data={'email': 'admin@sst.scaler.com', 'password': 'admin123', 'role': 'Admin'})
            payload = {
                "title": "Hackathon 2026 Registration Open",
                "content": "Join 400+ student builders for a 36-hour sprint.",
                "category": "Events",
                "priority": "Important",
                "audience": "All",
                "venue": "Main Auditorium"
            }
            res = client.post('/api/admin/announcements', data=json.dumps(payload), content_type='application/json')
            self.assertEqual(res.status_code, 201)
            data = json.loads(res.data)
            self.assertTrue(data["success"])
            self.assertEqual(data["announcement"]["title"], "Hackathon 2026 Registration Open")

            # Verify in SQLite
            conn = get_db()
            cursor = conn.cursor()
            cursor.execute("SELECT * FROM announcements WHERE title = 'Hackathon 2026 Registration Open'")
            row = cursor.fetchone()
            self.assertIsNotNone(row)
            self.assertEqual(row["category"], "Events")
            self.assertEqual(row["priority"], "Important")
            conn.close()

    def test_announcements_2_student_cannot_create_announcement(self):
        """
        2. Student cannot create an announcement (HTTP 403 Forbidden).
        """
        with self.app as client:
            client.post('/login', data={'email': 'sameer.verma@sst.scaler.com', 'password': 'scaler123', 'role': 'Student'})
            payload = {
                "title": "Unauthorized Student Broadcast",
                "content": "This should be blocked.",
                "category": "General"
            }
            res = client.post('/api/admin/announcements', data=json.dumps(payload), content_type='application/json')
            self.assertEqual(res.status_code, 403)

    def test_announcements_3_admin_can_view_announcements(self):
        """
        3. Admin can view announcements list via GET /api/admin/announcements.
        """
        with self.app as client:
            client.post('/login', data={'email': 'admin@sst.scaler.com', 'password': 'admin123', 'role': 'Admin'})
            # Create one
            client.post('/api/admin/announcements', data=json.dumps({
                "title": "Semester Registration",
                "content": "Deadline is Friday.",
                "category": "Academic"
            }), content_type='application/json')

            res = client.get('/api/admin/announcements')
            self.assertEqual(res.status_code, 200)
            items = json.loads(res.data)
            self.assertIsInstance(items, list)
            self.assertGreaterEqual(len(items), 1)
            self.assertEqual(items[0]["title"], "Semester Registration")

    def test_announcements_4_student_can_fetch_published_announcements(self):
        """
        4. Student can fetch published announcements via GET /api/announcements.
        """
        with self.app as client:
            # 1. Admin creates announcement
            client.post('/login', data={'email': 'admin@sst.scaler.com', 'password': 'admin123', 'role': 'Admin'})
            client.post('/api/admin/announcements', data=json.dumps({
                "title": "Library Extended Hours",
                "content": "Open 24/7 during exams.",
                "category": "Academic",
                "priority": "Normal"
            }), content_type='application/json')
            client.get('/logout')

            # 2. Student fetches announcements
            client.post('/login', data={'email': 'sameer.verma@sst.scaler.com', 'password': 'scaler123', 'role': 'Student'})
            res = client.get('/api/announcements')
            self.assertEqual(res.status_code, 200)
            items = json.loads(res.data)
            self.assertIsInstance(items, list)
            self.assertGreaterEqual(len(items), 1)
            self.assertEqual(items[0]["title"], "Library Extended Hours")

    def test_announcements_5_admin_can_delete_announcement(self):
        """
        5. Admin can delete an announcement via DELETE /api/admin/announcements/<id>.
        6. Deleted announcement no longer appears for students.
        """
        with self.app as client:
            # 1. Admin creates announcement
            client.post('/login', data={'email': 'admin@sst.scaler.com', 'password': 'admin123', 'role': 'Admin'})
            create_res = client.post('/api/admin/announcements', data=json.dumps({
                "title": "Temporary Power Cut Notice",
                "content": "Power cut in Block A from 2 PM to 3 PM.",
                "category": "Hostel"
            }), content_type='application/json')
            ann_id = json.loads(create_res.data)["announcement"]["id"]

            # 2. Admin deletes announcement
            del_res = client.delete(f'/api/admin/announcements/{ann_id}')
            self.assertEqual(del_res.status_code, 200)
            client.get('/logout')

            # 3. Student fetches announcements -> deleted announcement is gone
            client.post('/login', data={'email': 'sameer.verma@sst.scaler.com', 'password': 'scaler123', 'role': 'Student'})
            fetch_res = client.get('/api/announcements')
            self.assertEqual(fetch_res.status_code, 200)
            items = json.loads(fetch_res.data)
            found = [a for a in items if a["id"] == ann_id]
            self.assertEqual(len(found), 0)

    def test_announcements_6_student_cannot_delete_announcement(self):
        """
        Student attempting to delete an announcement receives HTTP 403 Forbidden.
        """
        with self.app as client:
            # 1. Admin creates
            client.post('/login', data={'email': 'admin@sst.scaler.com', 'password': 'admin123', 'role': 'Admin'})
            create_res = client.post('/api/admin/announcements', data=json.dumps({
                "title": "Official Admin Memo",
                "content": "Confidential notice.",
                "category": "General"
            }), content_type='application/json')
            ann_id = json.loads(create_res.data)["announcement"]["id"]
            client.get('/logout')

            # 2. Student tries to delete -> 403
            client.post('/login', data={'email': 'sameer.verma@sst.scaler.com', 'password': 'scaler123', 'role': 'Student'})
            del_res = client.delete(f'/api/admin/announcements/{ann_id}')
            self.assertEqual(del_res.status_code, 403)

    def test_announcements_7_urgent_announcements_appear_in_critical_alerts(self):
        """
        7. Urgent announcements are returned by GET /api/alerts as critical alerts.
        """
        with self.app as client:
            client.post('/login', data={'email': 'admin@sst.scaler.com', 'password': 'admin123', 'role': 'Admin'})
            client.post('/api/admin/announcements', data=json.dumps({
                "title": "Emergency AC Maintenance",
                "content": "Lab 3 relocated to Innovation Lab 4.",
                "category": "Academic",
                "priority": "Urgent",
                "venue": "Innovation Lab 4"
            }), content_type='application/json')
            client.get('/logout')

            client.post('/login', data={'email': 'sameer.verma@sst.scaler.com', 'password': 'scaler123', 'role': 'Student'})
            alerts_res = client.get('/api/alerts')
            self.assertEqual(alerts_res.status_code, 200)
            alerts = json.loads(alerts_res.data)
            self.assertGreaterEqual(len(alerts), 1)
            self.assertEqual(alerts[0]["title"], "Emergency AC Maintenance")
            self.assertEqual(alerts[0]["level"], "danger")

    def test_announcements_8_invalid_data_rejected(self):
        """
        8. Creating announcement with missing title or content is rejected (HTTP 400).
        """
        with self.app as client:
            client.post('/login', data={'email': 'admin@sst.scaler.com', 'password': 'admin123', 'role': 'Admin'})
            
            # Missing content
            res1 = client.post('/api/admin/announcements', data=json.dumps({"title": "Only Title"}), content_type='application/json')
            self.assertEqual(res1.status_code, 400)

            # Missing title
            res2 = client.post('/api/admin/announcements', data=json.dumps({"content": "Only Content"}), content_type='application/json')
            self.assertEqual(res2.status_code, 400)

    def test_announcements_9_unauthenticated_access_rejected(self):
        """
        9. Unauthenticated access to announcement APIs is rejected (HTTP 401 or 302).
        """
        self.assertIn(self.app.get('/api/announcements').status_code, [401, 302])
        self.assertIn(self.app.get('/api/admin/announcements').status_code, [401, 302])
        self.assertIn(self.app.post('/api/admin/announcements', data=json.dumps({"title": "Test"}), content_type='application/json').status_code, [401, 302])

    # =========================================================================
    # 13. TOP NAVIGATION & SUBROUTE RBAC TESTS
    # =========================================================================

    def test_navigation_1_student_top_navigation_elements(self):
        """
        Verify that a logged-in Student sees all required Top Navigation buttons:
        - Dashboard
        - Announcements
        - Events
        - My Registrations
        - Problem Tickets
        - Profile
        - Student Portal Branding & Logout
        And Admin Navigation is completely hidden.
        """
        with self.app as client:
            client.post('/login', data={'email': 'sameer.verma@sst.scaler.com', 'password': 'scaler123', 'role': 'Student'})
            res = client.get('/')
            self.assertEqual(res.status_code, 200)
            html = res.data.decode('utf-8')

            # Verify student navigation buttons
            self.assertIn('data-student-tab="dashboard"', html)
            self.assertIn('data-student-tab="announcements"', html)
            self.assertIn('data-student-tab="events"', html)
            self.assertIn('data-student-tab="registrations"', html)
            self.assertIn('data-student-tab="tickets"', html)
            self.assertIn('data-student-tab="profile"', html)

            # Verify Student Portal badge and logout
            self.assertIn('Student Portal', html)
            self.assertIn('/logout', html)

            # Verify Admin Navigation & CCTV are NOT visible to student
            self.assertNotIn('Admin Hub & CCTV', html)
            self.assertNotIn('data-admin-tab="dashboard"', html)

    def test_navigation_2_admin_top_navigation_elements(self):
        """
        Verify that a logged-in Admin sees all required Admin Top Navigation buttons:
        - Dashboard
        - Announcements
        - Events
        - Users
        - Problem Tickets
        - Profile
        - Admin Hub & CCTV Branding & Logout
        And Student Navigation is completely hidden.
        """
        with self.app as client:
            client.post('/login', data={'email': 'admin@sst.scaler.com', 'password': 'admin123', 'role': 'Admin'})
            res = client.get('/admin')
            self.assertEqual(res.status_code, 200)
            html = res.data.decode('utf-8')

            # Verify admin navigation buttons
            self.assertIn('data-admin-tab="dashboard"', html)
            self.assertIn('data-admin-tab="announcements"', html)
            self.assertIn('data-admin-tab="events"', html)
            self.assertIn('data-admin-tab="users"', html)
            self.assertIn('data-admin-tab="tickets"', html)
            self.assertIn('data-admin-tab="profile"', html)

            # Verify Admin Hub badge and logout
            self.assertIn('Admin Hub & CCTV', html)
            self.assertIn('/logout', html)

            # Verify Student Navigation is NOT visible
            self.assertNotIn('data-student-tab="dashboard"', html)

    def test_navigation_3_student_subroutes_return_200(self):
        """
        Verify that student subroutes (/dashboard, /announcements, /events, /registrations, /tickets, /profile)
        all render successfully for a logged-in student.
        """
        with self.app as client:
            client.post('/login', data={'email': 'sameer.verma@sst.scaler.com', 'password': 'scaler123', 'role': 'Student'})
            subroutes = ['/dashboard', '/announcements', '/events', '/registrations', '/tickets', '/profile']
            for route in subroutes:
                res = client.get(route)
                self.assertEqual(res.status_code, 200, f"Route {route} failed with {res.status_code}")

    def test_navigation_4_admin_subroutes_return_200(self):
        """
        Verify that admin subroutes (/admin/dashboard, /admin/announcements, /admin/events, /admin/users, /admin/tickets, /admin/profile)
        all render successfully for a logged-in admin.
        """
        with self.app as client:
            client.post('/login', data={'email': 'admin@sst.scaler.com', 'password': 'admin123', 'role': 'Admin'})
            subroutes = ['/admin/dashboard', '/admin/announcements', '/admin/events', '/admin/users', '/admin/tickets', '/admin/profile']
            for route in subroutes:
                res = client.get(route)
                self.assertEqual(res.status_code, 200, f"Route {route} failed with {res.status_code}")

    def test_navigation_5_student_cannot_access_admin_subroutes(self):
        """
        Verify that a student accessing any admin subroute is rejected and redirected.
        """
        with self.app as client:
            client.post('/login', data={'email': 'sameer.verma@sst.scaler.com', 'password': 'scaler123', 'role': 'Student'})
            admin_subroutes = ['/admin', '/admin/dashboard', '/admin/announcements', '/admin/events', '/admin/users', '/admin/tickets', '/admin/profile']
            for route in admin_subroutes:
                res = client.get(route, follow_redirects=False)
                # Must be a redirect (302) to safe student dashboard, never 200 admin page
                self.assertIn(res.status_code, [302, 403], f"Student accessed admin route {route}!")

    def test_navigation_6_unauthenticated_cannot_access_subroutes(self):
        """
        Verify unauthenticated users cannot access any student or admin subroutes.
        """
        routes = [
            '/dashboard', '/announcements', '/events', '/registrations', '/tickets', '/profile',
            '/admin', '/admin/dashboard', '/admin/announcements', '/admin/events', '/admin/users', '/admin/tickets', '/admin/profile'
        ]
        for route in routes:
            res = self.app.get(route, follow_redirects=False)
            self.assertIn(res.status_code, [302, 401], f"Unauthenticated accessed {route}!")

    # =========================================================================
    # 14. COMPLETE FINE MANAGEMENT & FINE HISTORY TESTS (14 SCENARIOS)
    # =========================================================================

    def test_fine_1_admin_assigns_fine_to_student_a(self):
        """
        Scenario 1 & 6: Admin selects Student A from database, enters amount and reason,
        and assigns fine. Verifies fine record is created in SQLite with 'Pending' status.
        """
        with self.app as client:
            # 1. Admin login
            client.post('/login', data={'email': 'admin@sst.scaler.com', 'password': 'admin123', 'role': 'Admin'})

            # 2. Get students dropdown
            stu_res = client.get('/api/admin/students')
            self.assertEqual(stu_res.status_code, 200)
            students = json.loads(stu_res.data)
            self.assertTrue(len(students) > 0)
            student_a = students[0]

            # 3. Assign fine of ₹400 for library late fee
            assign_res = client.post('/api/admin/fines',
                                     data=json.dumps({
                                         'user_id': student_a['id'],
                                         'amount': 400,
                                         'reason': 'Overdue Library Textbook - Advanced Algorithms'
                                     }),
                                     content_type='application/json')
            self.assertEqual(assign_res.status_code, 200)
            assign_data = json.loads(assign_res.data)
            self.assertTrue(assign_data['success'])
            self.assertEqual(assign_data['fine']['amount'], 400)
            self.assertEqual(assign_data['fine']['status'], 'Pending')
            self.assertEqual(assign_data['fine']['reason'], 'Overdue Library Textbook - Advanced Algorithms')
            self.assertIn('FINE-', assign_data['fine']['fine_id'])
            self.assertEqual(assign_data['student']['status'], 'Action Required 🔴')

    def test_fine_2_and_3_student_a_sees_fine_student_b_does_not(self):
        """
        Scenario 2 & 3: Student A can see their assigned fine.
        Student B cannot see Student A's fine.
        """
        with self.app as client:
            # 1. Admin creates a second student (Student B)
            client.post('/login', data={'email': 'admin@sst.scaler.com', 'password': 'admin123', 'role': 'Admin'})
            client.post('/api/admin/users',
                        data=json.dumps({
                            'name': 'Rahul Sharma',
                            'email': 'rahul.sharma@sst.scaler.com',
                            'password': 'scalerpassword123',
                            'role': 'Student',
                            'student_id': 'SST-2023-CS099'
                        }),
                        content_type='application/json')

            # 2. Admin assigns fine only to Student A (Sameer)
            client.post('/api/admin/fines',
                        data=json.dumps({
                            'email': 'sameer.verma@sst.scaler.com',
                            'amount': 300,
                            'reason': 'Hostel quiet hours violation'
                        }),
                        content_type='application/json')

            # 3. Student A logs in -> must see the fine
            client.post('/login', data={'email': 'sameer.verma@sst.scaler.com', 'password': 'scaler123', 'role': 'Student'})
            res_a = client.get('/api/student/fines')
            self.assertEqual(res_a.status_code, 200)
            data_a = json.loads(res_a.data)
            self.assertTrue(data_a['total_fines'] >= 1)
            self.assertTrue(data_a['total_pending_amount'] >= 300)
            reasons_a = [f['reason'] for f in data_a['fines']]
            self.assertIn('Hostel quiet hours violation', reasons_a)

            # 4. Student B logs in -> must NOT see Student A's fine (clean record)
            client.post('/login', data={'email': 'rahul.sharma@sst.scaler.com', 'password': 'scalerpassword123', 'role': 'Student'})
            res_b = client.get('/api/student/fines')
            self.assertEqual(res_b.status_code, 200)
            data_b = json.loads(res_b.data)
            self.assertEqual(data_b['total_fines'], 0)
            self.assertEqual(data_b['total_pending_amount'], 0)
            self.assertEqual(len(data_b['fines']), 0)
            self.assertFalse(data_b['has_fines'])

    def test_fine_4_and_5_admin_views_master_ledger_and_student_history(self):
        """
        Scenario 4 & 5: Admin can see Student A's fine in master ledger and in Student Fine History inspector.
        """
        with self.app as client:
            client.post('/login', data={'email': 'admin@sst.scaler.com', 'password': 'admin123', 'role': 'Admin'})

            # Assign fine to Sameer
            client.post('/api/admin/fines',
                        data=json.dumps({
                            'email': 'sameer.verma@sst.scaler.com',
                            'amount': 250,
                            'reason': 'Lab equipment late return'
                        }),
                        content_type='application/json')

            # Master Ledger (GET /api/admin/fines)
            master_res = client.get('/api/admin/fines')
            self.assertEqual(master_res.status_code, 200)
            master_data = json.loads(master_res.data)
            fines = master_data['fines']
            self.assertTrue(len(fines) >= 1)
            fine_reasons = [f['reason'] for f in fines]
            self.assertIn('Lab equipment late return', fine_reasons)

            # Specific Student History (GET /api/admin/students/<id>/fines)
            # Find Sameer's user_id
            students_res = client.get('/api/admin/students')
            students = json.loads(students_res.data)
            sameer = next(s for s in students if 'sameer' in s['email'].lower())

            hist_res = client.get(f"/api/admin/students/{sameer['id']}/fines")
            self.assertEqual(hist_res.status_code, 200)
            hist_data = json.loads(hist_res.data)
            self.assertEqual(hist_data['student']['name'], sameer['name'])
            self.assertTrue(hist_data['total_fines'] >= 1)
            self.assertTrue(hist_data['total_pending_amount'] >= 250)

    def test_fine_7_8_9_10_fine_payment_workflow(self):
        """
        Scenario 7, 8, 9, 10: Fine is marked as Paid.
        Admin and Student interfaces both reflect 'Paid' status and payment date timestamp is recorded.
        """
        with self.app as client:
            # 1. Admin assigns fine
            client.post('/login', data={'email': 'admin@sst.scaler.com', 'password': 'admin123', 'role': 'Admin'})
            assign_res = client.post('/api/admin/fines',
                                     data=json.dumps({
                                         'email': 'sameer.verma@sst.scaler.com',
                                         'amount': 500,
                                         'reason': 'Classroom furniture damage'
                                     }),
                                     content_type='application/json')
            assign_data = json.loads(assign_res.data)
            fine_id = assign_data['fine']['id']

            # 2. Student A logs in and pays fine
            client.post('/login', data={'email': 'sameer.verma@sst.scaler.com', 'password': 'scaler123', 'role': 'Student'})
            pay_res = client.post('/api/student/pay-fine')
            self.assertEqual(pay_res.status_code, 200)
            pay_data = json.loads(pay_res.data)
            self.assertTrue(pay_data['success'])
            self.assertEqual(pay_data['student']['fine_amount'], 0)
            self.assertEqual(pay_data['student']['status'], 'Good Standing 🟢')

            # 3. Student verifies fine history shows Paid and non-empty paid_at
            stu_fines_res = client.get('/api/student/fines')
            stu_fines = json.loads(stu_fines_res.data)
            paid_fine = next(f for f in stu_fines['fines'] if f['id'] == fine_id)
            self.assertEqual(paid_fine['status'], 'Paid')
            self.assertIsNotNone(paid_fine['paid_at'])
            self.assertTrue(len(paid_fine['paid_at']) > 0)
            self.assertEqual(stu_fines['total_pending_amount'], 0)
            self.assertTrue(stu_fines['total_paid_amount'] >= 500)

            # 4. Admin verifies student fine history also shows Paid and non-empty paid_at
            client.post('/login', data={'email': 'admin@sst.scaler.com', 'password': 'admin123', 'role': 'Admin'})
            admin_hist_res = client.get('/api/admin/fines')
            admin_fines = json.loads(admin_hist_res.data)['fines']
            admin_paid_fine = next(f for f in admin_fines if f['id'] == fine_id)
            self.assertEqual(admin_paid_fine['status'], 'Paid')
            self.assertIsNotNone(admin_paid_fine['paid_at'])

    def test_fine_11_multiple_fines_same_student_totals(self):
        """
        Scenario 11: Multiple fines for the same student appear correctly in history,
        and pending vs paid sums calculate accurately.
        """
        with self.app as client:
            client.post('/login', data={'email': 'admin@sst.scaler.com', 'password': 'admin123', 'role': 'Admin'})

            # Assign 2 distinct fines to Sameer: ₹200 and ₹600
            res1 = client.post('/api/admin/fines',
                               data=json.dumps({'email': 'sameer.verma@sst.scaler.com', 'amount': 200, 'reason': 'Fine 1'}),
                               content_type='application/json')
            f1_id = json.loads(res1.data)['fine']['id']

            res2 = client.post('/api/admin/fines',
                               data=json.dumps({'email': 'sameer.verma@sst.scaler.com', 'amount': 600, 'reason': 'Fine 2'}),
                               content_type='application/json')
            f2_id = json.loads(res2.data)['fine']['id']

            # Student pays only Fine 1 via /api/student/fines/<id>/pay
            client.post('/login', data={'email': 'sameer.verma@sst.scaler.com', 'password': 'scaler123', 'role': 'Student'})
            pay_single = client.post(f"/api/student/fines/{f1_id}/pay")
            self.assertEqual(pay_single.status_code, 200)

            # Student checks history
            stu_hist = json.loads(client.get('/api/student/fines').data)
            self.assertEqual(stu_hist['total_pending_amount'], 600)
            self.assertTrue(stu_hist['total_paid_amount'] >= 200)

            # Fine 1 is Paid, Fine 2 is Pending
            f1 = next(f for f in stu_hist['fines'] if f['id'] == f1_id)
            f2 = next(f for f in stu_hist['fines'] if f['id'] == f2_id)
            self.assertEqual(f1['status'], 'Paid')
            self.assertEqual(f2['status'], 'Pending')

    def test_fine_12_fines_persist_in_database(self):
        """
        Scenario 12: Fine records persist in SQLite.
        """
        with self.app as client:
            client.post('/login', data={'email': 'admin@sst.scaler.com', 'password': 'admin123', 'role': 'Admin'})
            res = client.post('/api/admin/fines',
                              data=json.dumps({'email': 'sameer.verma@sst.scaler.com', 'amount': 750, 'reason': 'Persistent Fine Test'}),
                              content_type='application/json')
            fine_id = json.loads(res.data)['fine']['id']

        # Query raw SQLite connection directly
        conn = get_db()
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM fines WHERE id = ?", (fine_id,))
        row = cursor.fetchone()
        conn.close()

        self.assertIsNotNone(row)
        self.assertEqual(row['amount'], 750)
        self.assertEqual(row['reason'], 'Persistent Fine Test')
        self.assertEqual(row['status'], 'Pending')

    def test_fine_13_student_with_no_fines_empty_history(self):
        """
        Scenario 13: Student with no fines sees total_fines=0, fines=[], has_fines=False.
        """
        with self.app as client:
            # Create a brand new clean student
            client.post('/login', data={'email': 'admin@sst.scaler.com', 'password': 'admin123', 'role': 'Admin'})
            client.post('/api/admin/users',
                        data=json.dumps({
                            'name': 'Clean Student',
                            'email': 'clean.student@sst.scaler.com',
                            'password': 'scalerpassword123',
                            'role': 'Student',
                            'student_id': 'SST-2023-CS101'
                        }),
                        content_type='application/json')

            # Log in as clean student
            client.post('/login', data={'email': 'clean.student@sst.scaler.com', 'password': 'scalerpassword123', 'role': 'Student'})
            res = client.get('/api/student/fines')
            self.assertEqual(res.status_code, 200)
            data = json.loads(res.data)
            self.assertEqual(data['total_fines'], 0)
            self.assertEqual(data['total_pending_amount'], 0)
            self.assertEqual(data['total_paid_amount'], 0)
            self.assertEqual(len(data['fines']), 0)
            self.assertFalse(data['has_fines'])
            self.assertIsNone(data['current_pending_fine'])

    def test_fine_14_student_cannot_access_other_student_fines_or_admin_routes(self):
        """
        Scenario 14: Security verification.
        - Student cannot access another student's fine history by passing user_id query params.
        - Student cannot access admin fine routes (GET /api/admin/fines, POST /api/admin/fines).
        """
        with self.app as client:
            # 1. Admin creates Student X and assigns a fine to Student X
            client.post('/login', data={'email': 'admin@sst.scaler.com', 'password': 'admin123', 'role': 'Admin'})
            stu_x_res = client.post('/api/admin/users',
                                    data=json.dumps({
                                        'name': 'Student X',
                                        'email': 'student.x@sst.scaler.com',
                                        'password': 'scalerpassword123',
                                        'role': 'Student',
                                        'student_id': 'SST-2023-CS999'
                                    }),
                                    content_type='application/json')
            stu_x_id = json.loads(stu_x_res.data)['user']['id']
            client.post('/api/admin/fines',
                        data=json.dumps({'user_id': stu_x_id, 'amount': 999, 'reason': 'Secret Student X Infraction'}),
                        content_type='application/json')

            # 2. Sameer logs in as regular Student
            client.post('/login', data={'email': 'sameer.verma@sst.scaler.com', 'password': 'scaler123', 'role': 'Student'})

            # Attempt parameter manipulation on student endpoint
            manip_res = client.get(f'/api/student/fines?user_id={stu_x_id}')
            self.assertEqual(manip_res.status_code, 200)
            manip_data = json.loads(manip_res.data)
            # Must NOT contain Student X's fine
            reasons = [f['reason'] for f in manip_data['fines']]
            self.assertNotIn('Secret Student X Infraction', reasons)

            # Attempt to call Admin fine endpoints
            self.assertEqual(client.get('/api/admin/fines').status_code, 403)
            self.assertEqual(client.get(f'/api/admin/students/{stu_x_id}/fines').status_code, 403)
            self.assertEqual(client.post('/api/admin/fines', data=json.dumps({'amount': 100}), content_type='application/json').status_code, 403)


if __name__ == '__main__':
    unittest.main()

