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
            os.remove(os.environ["NEXTCAMP_DB"])
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

    def test_event_booking_detects_time_clash(self):
        """
        Verify that booking Main Auditorium for Today during existing conference
        returns 409 and '⚠️ TIME CLASH DETECTED: Auditorium is already booked'.
        """
        with self.app as client:
            client.post('/login', data={'email': 'sameer.verma@sst.scaler.com', 'password': 'scaler123', 'role': 'Student'})
            payload = {
                "name": "SST AI Demo Day",
                "venue": "Main Auditorium",
                "date": "Today",
                "start_time": "11:00",
                "end_time": "14:00"
            }
            res = client.post('/api/events/book',
                              data=json.dumps(payload),
                              content_type='application/json')
            self.assertEqual(res.status_code, 409)
            data = json.loads(res.data)
            self.assertTrue(data["clash"])
            self.assertIn("⚠️ TIME CLASH DETECTED: Auditorium is already booked", data["message"])

    def test_event_booking_no_clash_succeeds(self):
        """
        Verify that booking a non-clashing venue and time slot succeeds (201).
        """
        with self.app as client:
            client.post('/login', data={'email': 'sameer.verma@sst.scaler.com', 'password': 'scaler123', 'role': 'Student'})
            payload = {
                "name": "Design Sprint",
                "venue": "Innovation Hub",
                "date": "Tomorrow",
                "start_time": "10:00",
                "end_time": "13:00"
            }
            res = client.post('/api/events/book',
                              data=json.dumps(payload),
                              content_type='application/json')
            self.assertEqual(res.status_code, 201)
            data = json.loads(res.data)
            self.assertFalse(data["clash"])

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

if __name__ == '__main__':
    unittest.main()
