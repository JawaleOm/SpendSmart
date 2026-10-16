"""
tests/test_app.py - Pytest Test Suite for SpendSmart Personal Expense Tracker
=============================================================================
Covers:
  - Login with valid & invalid name, email, phone
  - Protected pages redirect when logged out
  - Add, edit, delete a transaction
  - Validation: reject negative/zero amount, invalid date, empty description
  - Monthly totals, balance, and budget percentage calculations
  - Student Budget Health Indicator exact thresholds (69%, 70%, 90%, 91%, 100%, 101%)
  - Budget save and update (upsert)
  - CSV export download
  - Multi-user isolation
  - Sample data loader
"""

import os
import tempfile
import pytest
from app import app
import database


@pytest.fixture
def test_client():
    """Sets up an isolated test client with a clean temporary SQLite database."""
    db_fd, db_path = tempfile.mkstemp(suffix=".db")
    app.config["TESTING"] = True
    app.config["SECRET_KEY"] = "test-secret-key-12345"

    orig_default_db = database.DEFAULT_DB_PATH
    database.DEFAULT_DB_PATH = db_path
    database.init_db(db_path)

    with app.test_client() as client:
        yield client

    database.DEFAULT_DB_PATH = orig_default_db
    os.close(db_fd)
    if os.path.exists(db_path):
        os.remove(db_path)


def login(client, name="Aditya Rao", email="aditya@example.com", phone="+91 9876543210"):
    """Helper to log in a test user."""
    return client.post(
        "/login",
        data={"name": name, "email": email, "phone": phone},
        follow_redirects=True,
    )


# -----------------------------------------------------------------------------
# 1. Login Tests (Valid & Invalid)
# -----------------------------------------------------------------------------
def test_login_valid(test_client):
    """Test successful login with valid 3 fields, redirect, and session creation."""
    res = login(test_client, name="Rahul Verma", email="rahul@example.com", phone="+91 9876543210")
    assert res.status_code == 200
    assert b"Welcome, Rahul Verma!" in res.data
    assert b"Dashboard" in res.data

    with test_client.session_transaction() as sess:
        assert sess["user_name"] == "Rahul Verma"
        assert sess["user_email"] == "rahul@example.com"
        assert "login_date" in sess
        assert "login_time" in sess


def test_login_phone_without_prefix(test_client):
    """Test login with plain 10-digit Indian mobile number."""
    res = login(test_client, name="Priya Singh", email="priya@example.com", phone="9876543210")
    assert res.status_code == 200
    assert b"Welcome, Priya Singh!" in res.data


def test_login_invalid_name(test_client):
    """Test login rejected when name is empty or less than 2 characters."""
    res = test_client.post(
        "/login",
        data={"name": "A", "email": "valid@example.com", "phone": "9876543210"},
    )
    assert res.status_code == 200
    assert b"Full Name must be at least 2 characters long." in res.data


def test_login_invalid_email(test_client):
    """Test login rejected when email format is invalid."""
    res = test_client.post(
        "/login",
        data={"name": "Valid Name", "email": "invalid-email-string", "phone": "9876543210"},
    )
    assert res.status_code == 200
    assert b"Please enter a valid email address" in res.data


def test_login_invalid_phone(test_client):
    """Test login rejected when phone is not a valid 10-digit Indian mobile number."""
    # Too short
    res1 = test_client.post(
        "/login",
        data={"name": "Valid Name", "email": "valid@example.com", "phone": "12345"},
    )
    assert res1.status_code == 200
    assert b"Please enter a valid 10-digit Indian mobile number" in res1.data

    # Doesn't start with 6, 7, 8, or 9
    res2 = test_client.post(
        "/login",
        data={"name": "Valid Name", "email": "valid@example.com", "phone": "1234567890"},
    )
    assert res2.status_code == 200
    assert b"Indian mobile numbers must begin with 6, 7, 8, or 9" in res2.data


def test_login_upsert_existing_email(test_client):
    """Test that logging in with an existing email updates details without duplicate users."""
    login(test_client, name="Original Name", email="user@example.com", phone="9876543210")
    login(test_client, name="Updated Name", email="user@example.com", phone="9123456789")

    conn = database.get_db_connection()
    users = conn.execute("SELECT * FROM users WHERE email = 'user@example.com'").fetchall()
    conn.close()

    assert len(users) == 1
    assert users[0]["name"] == "Updated Name"


# -----------------------------------------------------------------------------
# 2. Protected Pages Redirect When Logged Out
# -----------------------------------------------------------------------------
@pytest.mark.parametrize("route", [
    "/dashboard",
    "/transactions",
    "/transactions/add",
    "/budget",
    "/reports",
    "/reports/export-csv",
])
def test_protected_pages_redirect_when_logged_out(test_client, route):
    """Ensure unauthenticated access to protected routes redirects to /login."""
    res = test_client.get(route)
    assert res.status_code == 302
    assert "/login" in res.headers["Location"]


def test_root_redirects_to_login_when_logged_out(test_client):
    """Test that '/' redirects to /login when user is not logged in."""
    res = test_client.get("/")
    assert res.status_code == 302
    assert "/login" in res.headers["Location"]


def test_logout(test_client):
    """Test logout clears session and redirects to /login."""
    login(test_client)
    res = test_client.get("/logout", follow_redirects=True)
    assert res.status_code == 200
    assert b"You have been logged out successfully." in res.data

    # Ensure dashboard is now protected
    dash_res = test_client.get("/dashboard")
    assert dash_res.status_code == 302


# -----------------------------------------------------------------------------
# 3. Add, Edit, Delete Transaction Tests
# -----------------------------------------------------------------------------
def test_add_and_view_transaction(test_client):
    """Test adding income and expense transactions and viewing them in the list."""
    login(test_client)

    # 1. Add Income
    res_inc = test_client.post(
        "/transactions/add",
        data={
            "transaction_type": "income",
            "amount": "15000",
            "description": "Monthly Student Allowance",
            "category": "Allowance",
            "need_or_want": "N/A",
            "date": "2026-10-01",
        },
        follow_redirects=True,
    )
    assert res_inc.status_code == 200
    assert b"Transaction added successfully!" in res_inc.data
    assert b"Monthly Student Allowance" in res_inc.data

    # 2. Add Expense with Need
    res_exp = test_client.post(
        "/transactions/add",
        data={
            "transaction_type": "expense",
            "amount": "850",
            "description": "Python Reference Textbooks",
            "category": "Education",
            "need_or_want": "Need",
            "date": "2026-10-05",
        },
        follow_redirects=True,
    )
    assert res_exp.status_code == 200
    assert b"Python Reference Textbooks" in res_exp.data


def test_edit_transaction(test_client):
    """Test editing an existing transaction."""
    login(test_client)

    # Add initial transaction
    test_client.post(
        "/transactions/add",
        data={
            "transaction_type": "expense",
            "amount": "500",
            "description": "Mess Food",
            "category": "Food",
            "need_or_want": "Need",
            "date": "2026-10-02",
        },
    )

    with test_client.session_transaction() as sess:
        uid = sess["user_id"]

    txs = database.get_transactions(uid)
    assert len(txs) == 1
    tx_id = txs[0]["id"]

    # Edit the transaction
    res = test_client.post(
        f"/transactions/edit/{tx_id}",
        data={
            "transaction_type": "expense",
            "amount": "650",
            "description": "Mess Food + Evening Snacks",
            "category": "Food",
            "need_or_want": "Need",
            "date": "2026-10-02",
        },
        follow_redirects=True,
    )
    assert res.status_code == 200
    assert b"Transaction updated successfully!" in res.data
    assert b"Mess Food + Evening Snacks" in res.data

    # Verify in DB
    updated = database.get_transaction_by_id(tx_id, uid)
    assert updated["amount"] == 650.0
    assert updated["description"] == "Mess Food + Evening Snacks"


def test_delete_transaction(test_client):
    """Test deleting a transaction."""
    login(test_client)

    test_client.post(
        "/transactions/add",
        data={
            "transaction_type": "expense",
            "amount": "300",
            "description": "Cinema Popcorn",
            "category": "Entertainment",
            "need_or_want": "Want",
            "date": "2026-10-04",
        },
    )

    with test_client.session_transaction() as sess:
        uid = sess["user_id"]

    txs = database.get_transactions(uid)
    tx_id = txs[0]["id"]

    # Delete transaction
    res = test_client.post(f"/transactions/delete/{tx_id}", follow_redirects=True)
    assert res.status_code == 200
    assert b"Transaction deleted successfully." in res.data

    # Verify deleted
    assert database.get_transaction_by_id(tx_id, uid) is None


# -----------------------------------------------------------------------------
# 4. Server-Side Validation: Reject Negative, Zero, Invalid Dates & Descriptions
# -----------------------------------------------------------------------------
def test_reject_zero_or_negative_amount(test_client):
    """Test that zero or negative amounts are rejected."""
    login(test_client)

    # Zero amount
    res1 = test_client.post(
        "/transactions/add",
        data={
            "transaction_type": "expense",
            "amount": "0",
            "description": "Free sample",
            "category": "Other",
            "need_or_want": "Want",
            "date": "2026-10-05",
        },
    )
    assert res1.status_code == 200
    assert b"greater than zero" in res1.data

    # Negative amount
    res2 = test_client.post(
        "/transactions/add",
        data={
            "transaction_type": "expense",
            "amount": "-500",
            "description": "Invalid negative",
            "category": "Other",
            "need_or_want": "Want",
            "date": "2026-10-05",
        },
    )
    assert res2.status_code == 200
    assert b"greater than zero" in res2.data


def test_reject_empty_description(test_client):
    """Test that empty descriptions are rejected."""
    login(test_client)
    res = test_client.post(
        "/transactions/add",
        data={
            "transaction_type": "expense",
            "amount": "100",
            "description": "   ",
            "category": "Food",
            "need_or_want": "Need",
            "date": "2026-10-05",
        },
    )
    assert res.status_code == 200
    assert b"Description cannot be empty" in res.data


def test_reject_invalid_date(test_client):
    """Test that malformed dates are rejected."""
    login(test_client)
    res = test_client.post(
        "/transactions/add",
        data={
            "transaction_type": "expense",
            "amount": "100",
            "description": "Test tx",
            "category": "Food",
            "need_or_want": "Need",
            "date": "not-a-date",
        },
    )
    assert res.status_code == 200
    assert b"Invalid date format" in res.data


# -----------------------------------------------------------------------------
# 5. Financial Totals, Balance, and Calculations
# -----------------------------------------------------------------------------
def test_totals_and_balance_calculation(test_client):
    """Test accurate monthly income, expense, and net balance calculation."""
    login(test_client)
    with test_client.session_transaction() as sess:
        uid = sess["user_id"]

    month = "2026-10"
    database.add_transaction(uid, "income", "Freelance", 12000.0, "Freelance", "N/A", f"{month}-01")
    database.add_transaction(uid, "income", "Scholarship", 5000.0, "Scholarship", "N/A", f"{month}-02")
    database.add_transaction(uid, "expense", "Hostel Rent", 6000.0, "Bills", "Need", f"{month}-03")
    database.add_transaction(uid, "expense", "Groceries", 2500.0, "Food", "Need", f"{month}-04")

    totals = database.get_monthly_totals(uid, month)
    assert totals["income"] == 17000.0
    assert totals["expense"] == 8500.0
    assert totals["balance"] == 8500.0


# -----------------------------------------------------------------------------
# 6. Student Budget Health Indicator Exact Thresholds (69%, 70%, 90%, 91%, 100%, 101%)
# -----------------------------------------------------------------------------
def test_budget_health_thresholds():
    """
    Test exact Health Indicator rules required by specification:
      - 69%  -> On Track (<70%)
      - 70%  -> Caution (70-90%)
      - 90%  -> Caution (70-90%)
      - 91%  -> Near Limit (>90%)
      - 100% -> Near Limit (<=100%)
      - 101% -> Over Budget (>100%)
    """
    # 69% -> On Track
    h69 = database.calculate_budget_health(69.0, 100.0)
    assert h69["status"] == "On Track"
    assert h69["is_warning"] is False

    # 70% -> Caution
    h70 = database.calculate_budget_health(70.0, 100.0)
    assert h70["status"] == "Caution"
    assert h70["is_warning"] is True
    assert h70["warning_level"] == 70

    # 90% -> Caution
    h90 = database.calculate_budget_health(90.0, 100.0)
    assert h90["status"] == "Caution"
    assert h90["is_warning"] is True
    assert h90["warning_level"] == 70

    # 91% -> Near Limit
    h91 = database.calculate_budget_health(91.0, 100.0)
    assert h91["status"] == "Near Limit"
    assert h91["is_warning"] is True
    assert h91["warning_level"] == 90

    # 100% -> Near Limit
    h100 = database.calculate_budget_health(100.0, 100.0)
    assert h100["status"] == "Near Limit"
    assert h100["is_warning"] is True
    assert h100["warning_level"] == 90

    # 101% -> Over Budget
    h101 = database.calculate_budget_health(101.0, 100.0)
    assert h101["status"] == "Over Budget"
    assert h101["is_warning"] is True
    assert h101["warning_level"] == 100


# -----------------------------------------------------------------------------
# 7. Budget Save & Update (Upsert)
# -----------------------------------------------------------------------------
def test_budget_save_and_update(test_client):
    """Test setting a monthly budget and then updating it for the same month."""
    login(test_client)
    with test_client.session_transaction() as sess:
        uid = sess["user_id"]

    month = "2026-10"

    # Set initial budget: ₹8,000
    res1 = test_client.post(
        "/budget",
        data={"month": month, "monthly_limit": "8000"},
        follow_redirects=True,
    )
    assert res1.status_code == 200
    assert b"Budget limit of" in res1.data

    b1 = database.get_budget(uid, month)
    assert b1["monthly_limit"] == 8000.0

    # Update budget to ₹12,000
    res2 = test_client.post(
        "/budget",
        data={"month": month, "monthly_limit": "12000"},
        follow_redirects=True,
    )
    assert res2.status_code == 200

    b2 = database.get_budget(uid, month)
    assert b2["monthly_limit"] == 12000.0

    # Ensure no duplicates in DB
    conn = database.get_db_connection()
    count = conn.execute(
        "SELECT COUNT(*) as cnt FROM budgets WHERE user_id = ? AND month = ?",
        (uid, month),
    ).fetchone()["cnt"]
    conn.close()
    assert count == 1


# -----------------------------------------------------------------------------
# 8. CSV Export Test
# -----------------------------------------------------------------------------
def test_csv_export(test_client):
    """Test exporting monthly transactions to CSV."""
    login(test_client)
    with test_client.session_transaction() as sess:
        uid = sess["user_id"]

    month = "2026-10"
    database.add_transaction(uid, "income", "College Stipend", 5000.0, "Salary", "N/A", f"{month}-01")
    database.add_transaction(uid, "expense", "Metro Card Recharge", 600.0, "Transport", "Need", f"{month}-03")

    res = test_client.get(f"/reports/export-csv?month={month}")
    assert res.status_code == 200
    assert "text/csv" in res.headers["Content-Type"]
    assert f"SpendSmart_Transactions_{month}.csv" in res.headers["Content-Disposition"]

    csv_text = res.data.decode("utf-8")
    assert "Date,Description,Type,Category,Need_or_Want,Amount_INR" in csv_text
    assert "College Stipend,income,Salary,N/A,5000.00" in csv_text
    assert "Metro Card Recharge,expense,Transport,Need,600.00" in csv_text


# -----------------------------------------------------------------------------
# 9. Multi-User Isolation Test
# -----------------------------------------------------------------------------
def test_multi_user_data_isolation(test_client):
    """Ensure User A cannot see User B's transactions or budgets."""
    # User A logs in and adds a transaction
    login(test_client, name="User A", email="usera@example.com", phone="9876543210")
    test_client.post(
        "/transactions/add",
        data={
            "transaction_type": "expense",
            "amount": "999",
            "description": "Secret Transaction A",
            "category": "Shopping",
            "need_or_want": "Want",
            "date": "2026-10-05",
        },
    )

    # User B logs in
    login(test_client, name="User B", email="userb@example.com", phone="9123456789")

    # User B checks transactions list
    res_b = test_client.get("/transactions")
    assert b"Secret Transaction A" not in res_b.data


# -----------------------------------------------------------------------------
# 10. Sample Data Loader Test
# -----------------------------------------------------------------------------
def test_sample_data_loader(test_client):
    """Test loading sample data inserts ₹15,000 allowance, 12 expenses, and a budget."""
    login(test_client, name="Demo Student", email="demo@example.com", phone="9876543210")
    with test_client.session_transaction() as sess:
        uid = sess["user_id"]

    res = test_client.post("/load-sample-data", follow_redirects=True)
    assert res.status_code == 200
    assert b"Demo data loaded successfully!" in res.data

    txs = database.get_transactions(uid)
    assert len(txs) >= 13  # 1 allowance + 12 expenses
    assert any(t["transaction_type"] == "income" and t["amount"] == 15000.0 for t in txs)
