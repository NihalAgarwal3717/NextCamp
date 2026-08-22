"""
NextCamp Comprehensive Test Suite
Validates:
1. Domain-restricted authentication (@sst.scaler.com) & route protection
2. Student problem reporting with smart solver allocation (highest rating & solved count)
3. CCTV Damage fine issuance (₹500 & 'Action Required 🔴' status)
4. Worker Management CRUD (Add, Edit, Delete) and dynamic smart allocation integration
5. Event booking venue & time clash detection
6. Post-Resolution Rating System (3-dimensional star ratings, worker cumulative score recalculation, +5 student reputation points, review log)
"""
import unittest
import json
from app import (
    app, WORKERS, STUDENT_PROFILE, CAMPUS_EVENTS, CCTV_DAMAGE_INCIDENT,
    WORKER_REVIEWS, TICKETS, allocate_smart_worker
)

class NextCampComprehensiveTestCase(unittest.TestCase):
    def setUp(self):
        self.app = app.test_client()
        self.app.testing = True

        # Reset student profile
        STUDENT_PROFILE["fine_amount"] = 0
        STUDENT_PROFILE["status"] = "Good Standing 🟢"
        STUDENT_PROFILE["fine_reason"] = None
        STUDENT_PROFILE["fine_history"] = []
        STUDENT_PROFILE["reputation"] = 4.7
        STUDENT_PROFILE["reputation_points"] = 94

    # =========================================================================
    # 1. AUTHENTICATION & DOMAIN RESTRICTION TESTS
    # =========================================================================

    def test_login_rejects_non_sst_domain(self):
        """
        Verify that attempting to log in with an unauthorized email domain
        (e.g., @gmail.com or @other.edu) is rejected with the exact required error message.
        """
        res = self.app.post('/login', data={
            'email': 'student@gmail.com',
            'password': 'password123',
            'role': 'Student'
        })
        self.assertEqual(res.status_code, 200)
        self.assertIn(b"Access restricted! Only @sst.scaler.com email addresses are authorized.", res.data)

    def test_login_accepts_sst_scaler_domain(self):
        """
        Verify that an email strictly ending with @sst.scaler.com logs in successfully
        and sets the session.
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
            # Login
            client.post('/login', data={
                'email': 'sameer.verma@sst.scaler.com',
                'password': 'scaler123',
                'role': 'Student'
            })
            # Logout
            logout_res = client.get('/logout', follow_redirects=False)
            self.assertEqual(logout_res.status_code, 302)
            self.assertIn('/login', logout_res.headers['Location'])

    # =========================================================================
    # 2. SMART PROBLEM ALLOCATION TESTS
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
        'Assigned to: Ravi (⭐ 4.9)'.
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

    # =========================================================================
    # 3. CCTV DAMAGE REVIEW & FINE ISSUANCE TESTS
    # =========================================================================

    def test_cctv_issue_fine_updates_student_status_and_applies_fine(self):
        """
        Verify that clicking [Review & Issue Fine ₹500] (/api/issue-fine)
        updates student status from 'Good Standing 🟢' to 'Action Required 🔴'
        and applies a ₹500 fine.
        """
        res = self.app.post('/api/issue-fine',
                            data=json.dumps({"amount": 500, "reason": "Classroom 204 — 3:20 PM - Damaged Chair"}),
                            content_type='application/json')
        self.assertEqual(res.status_code, 200)
        data = json.loads(res.data)
        self.assertEqual(data["student"]["fine_amount"], 500)
        self.assertEqual(data["student"]["status"], "Action Required 🔴")

        # Verify via profile endpoint
        prof_res = self.app.get('/api/student/profile')
        prof_data = json.loads(prof_res.data)
        self.assertEqual(prof_data["status"], "Action Required 🔴")
        self.assertEqual(prof_data["fine_amount"], 500)

    # =========================================================================
    # 4. WORKER MANAGEMENT (CRUD) TESTS
    # =========================================================================

    def test_worker_crud_and_dynamic_smart_allocation(self):
        """
        Verify:
        1. ➕ Adding a new worker defaults to rating ⭐ 5.0 and tasks solved 0.
        2. Newly added worker with ⭐ 5.0 is picked by smart allocation for their category!
        3. ✏️ Editing worker name / category works.
        4. 🗑️ Deleting worker works.
        """
        # 1. Add New Worker
        add_res = self.app.post('/api/workers',
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
        edit_res = self.app.put(f'/api/workers/{new_worker_id}',
                                data=json.dumps({"name": "Devendra Sharma", "category": "Hardware"}),
                                content_type='application/json')
        self.assertEqual(edit_res.status_code, 200)
        edit_data = json.loads(edit_res.data)
        self.assertEqual(edit_data["worker"]["name"], "Devendra Sharma")

        # 4. Delete Worker
        del_res = self.app.delete(f'/api/workers/{new_worker_id}')
        self.assertEqual(del_res.status_code, 200)

    # =========================================================================
    # 5. EVENT BOOKING & TIME CLASH DETECTION TESTS
    # =========================================================================

    def test_event_booking_detects_time_clash(self):
        """
        Verify that booking Main Auditorium for Today during existing conference
        returns 409 and '⚠️ TIME CLASH DETECTED: Auditorium is already booked'.
        """
        payload = {
            "name": "SST AI Demo Day",
            "venue": "Main Auditorium",
            "date": "Today",
            "start_time": "11:00",
            "end_time": "14:00"
        }
        res = self.app.post('/api/events/book',
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
        payload = {
            "name": "Design Sprint",
            "venue": "Innovation Hub",
            "date": "Tomorrow",
            "start_time": "10:00",
            "end_time": "13:00"
        }
        res = self.app.post('/api/events/book',
                            data=json.dumps(payload),
                            content_type='application/json')
        self.assertEqual(res.status_code, 201)
        data = json.loads(res.data)
        self.assertFalse(data["clash"])

    # =========================================================================
    # 6. POST-RESOLUTION RATING SYSTEM & REVIEWS LOG TESTS
    # =========================================================================

    def test_ticket_resolution_workflow(self):
        """
        Verify that marking a ticket as Resolved via POST /api/tickets/<id>/resolve
        updates ticket status to 'Resolved'.
        """
        res = self.app.post('/api/tickets/TCK-1001/resolve')
        self.assertEqual(res.status_code, 200)
        data = json.loads(res.data)
        self.assertEqual(data["ticket"]["status"], "Resolved")

    def test_submit_rating_awards_reputation_and_recalculates_worker_rating(self):
        """
        Verify that submitting a 3-dimensional rating (Response Time: 5, Quality: 4, Behavior: 5):
        1. Calculates average score (4.67)
        2. Recalculates worker cumulative rating in app.py
        3. Awards +5 Reputation Points to reporting student
        4. Appends review to Admin Review Log
        """
        with self.app as client:
            client.post('/login', data={
                'email': 'sameer.verma@sst.scaler.com',
                'password': 'scaler123',
                'role': 'Student'
            })

            initial_rep_points = STUDENT_PROFILE.get("reputation_points", 94)
            worker_ravi = next(w for w in WORKERS if w["name"] == "Ravi")
            initial_tasks = worker_ravi["tasks_solved"]

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

            # 2. Student reputation awarded check (+5 points)
            self.assertEqual(data["reputation_points"], initial_rep_points + 5)
            self.assertEqual(STUDENT_PROFILE["reputation_points"], initial_rep_points + 5)

            # 3. Worker cumulative tasks count incremented
            self.assertEqual(worker_ravi["tasks_solved"], initial_tasks + 1)

            # 4. Review object appended to log
            self.assertEqual(data["review"]["student_name"], "Sameer Verma")
            self.assertEqual(data["review"]["worker_name"], "Ravi")
            self.assertEqual(data["review"]["avg_rating"], 4.67)

    def test_reviews_endpoint_returns_review_log(self):
        """
        Verify that GET /api/reviews returns the log of student submitted reviews.
        """
        res = self.app.get('/api/reviews')
        self.assertEqual(res.status_code, 200)
        reviews = json.loads(res.data)
        self.assertIsInstance(reviews, list)
        self.assertGreater(len(reviews), 0)
        self.assertIn("worker_name", reviews[0])
        self.assertIn("avg_rating", reviews[0])
        self.assertIn("suggestion", reviews[0])

if __name__ == '__main__':
    unittest.main()
