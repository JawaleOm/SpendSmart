"""
database.py - SQLite Database Management for SpendSmart Personal Expense Tracker
================================================================================
Handles database connection, table initialization, parameterized queries,
user upserts with login timestamps, transaction CRUD, monthly budgets,
and student budget health indicator calculations.
"""

import os
import re
import sqlite3
from datetime import datetime, timezone, timedelta
from typing import Any, Dict, List, Optional, Tuple

# Dynamic database path resolution according to Vercel serverless requirements
def get_default_db_path() -> str:
    """
    Returns the appropriate SQLite database file path:
      1. If env var DATABASE_PATH is set, use it.
      2. Else if running on Vercel (env var VERCEL is set), use /tmp/spendsmart.db.
      3. Else use ./spendsmart.db next to the code (local development).
    """
    if os.environ.get("DATABASE_PATH"):
        return os.environ.get("DATABASE_PATH")
    elif os.environ.get("VERCEL"):
        return "/tmp/spendsmart.db"
    base_dir = os.path.dirname(os.path.abspath(__file__))
    return os.path.join(base_dir, "spendsmart.db")


# Default database file path in the SpendSmart root directory
DEFAULT_DB_PATH = get_default_db_path()

# Standard Categories according to specification
EXPENSE_CATEGORIES = [
    "Food",
    "Transport",
    "Shopping",
    "Subscriptions",
    "Education",
    "Entertainment",
    "Health",
    "Bills",
    "Other"
]

INCOME_CATEGORIES = [
    "Allowance",
    "Salary",
    "Freelance",
    "Scholarship",
    "Gift",
    "Other"
]


def get_current_time_display() -> Tuple[str, str, str]:
    """
    Returns current date, time, and full formatted string in Indian Standard Time (IST, UTC+5:30).
    Returns:
        (date_str, time_str, full_display_str)
        Example: ('16 Oct 2026', '03:42 PM', 'Friday, 16 October 2026 · 03:42:17 PM')
    """
    ist_offset = timezone(timedelta(hours=5, minutes=30))
    now = datetime.now(ist_offset)
    date_str = now.strftime("%d %b %Y")
    time_str = now.strftime("%I:%M %p")
    full_display = now.strftime("%A, %d %B %Y · %I:%M:%S %p")
    return date_str, time_str, full_display


def format_inr(amount: Any, include_symbol: bool = True) -> str:
    """
    Formats a numeric amount into Indian Rupee notation (e.g. ₹15,000.00, ₹1,25,000.50).
    Follows Indian numbering formatting: last 3 digits, then groups of 2.
    """
    try:
        val = float(amount)
    except (ValueError, TypeError):
        val = 0.0

    is_negative = val < 0
    val = round(abs(val), 2)
    formatted_float = f"{val:.2f}"
    int_part, dec_part = formatted_float.split(".")

    if len(int_part) <= 3:
        grouped = int_part
    else:
        last3 = int_part[-3:]
        rest = int_part[:-3]
        groups = []
        while len(rest) > 2:
            groups.insert(0, rest[-2:])
            rest = rest[:-2]
        if rest:
            groups.insert(0, rest)
        grouped = ",".join(groups) + "," + last3

    symbol = "₹" if include_symbol else ""
    sign = "-" if is_negative else ""
    return f"{sign}{symbol}{grouped}.{dec_part}"


# -----------------------------------------------------------------------------
# Input Validation Helpers
# -----------------------------------------------------------------------------
def validate_name(name: str) -> Tuple[bool, str]:
    """Validates user full name (required, min 2 characters)."""
    clean = (name or "").strip()
    if not clean:
        return False, "Full Name is required."
    if len(clean) < 2:
        return False, "Full Name must be at least 2 characters long."
    if len(clean) > 80:
        return False, "Full Name cannot exceed 80 characters."
    return True, ""


def validate_email(email: str) -> Tuple[bool, str]:
    """Validates email ID format."""
    clean = (email or "").strip().lower()
    if not clean:
        return False, "Email ID is required."
    pattern = r"^[a-zA-Z0-9_.+-]+@[a-zA-Z0-9-]+\.[a-zA-Z0-9-.]+$"
    if not re.match(pattern, clean) or len(clean) > 120:
        return False, "Please enter a valid email address (e.g. name@example.com)."
    return True, ""


def validate_phone(phone: str) -> Tuple[bool, str]:
    """
    Validates a 10-digit Indian mobile number with optional +91 prefix.
    Accepts: +91 9876543210, 9876543210, +91-98765-43210, etc.
    """
    clean = (phone or "").strip()
    if not clean:
        return False, "Phone Number is required."

    # Extract digits only
    digits = re.sub(r"\D", "", clean)

    # If it starts with country code 91 and has 12 digits total
    if len(digits) == 12 and digits.startswith("91"):
        mobile_digits = digits[2:]
    elif len(digits) == 10:
        mobile_digits = digits
    else:
        return False, "Please enter a valid 10-digit Indian mobile number (optional +91)."

    if mobile_digits[0] not in "6789":
        return False, "Indian mobile numbers must begin with 6, 7, 8, or 9."

    return True, ""


def clean_phone_number(phone: str) -> str:
    """Normalizes phone string to standard '+91 XXXXX XXXXX' format."""
    digits = re.sub(r"\D", "", phone.strip())
    if len(digits) == 12 and digits.startswith("91"):
        mobile = digits[2:]
    else:
        mobile = digits[-10:]
    return f"+91 {mobile[:5]} {mobile[5:]}"


# -----------------------------------------------------------------------------
# Database Connection & Initialization
# -----------------------------------------------------------------------------
def get_db_connection(db_path: Optional[str] = None) -> sqlite3.Connection:
    """Creates and returns an active SQLite connection with row factory and foreign keys enabled."""
    path = db_path or DEFAULT_DB_PATH
    os.makedirs(os.path.dirname(os.path.abspath(path)), exist_ok=True)
    conn = sqlite3.connect(path, timeout=10.0)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON;")
    return conn


def init_db(db_path: Optional[str] = None) -> None:
    """
    Auto-creates database tables on first run WITHOUT overwriting existing data:
      - users(id, name, email UNIQUE, phone, last_login)
      - transactions(id, user_id, transaction_type, description, amount REAL, category, need_or_want, date)
      - budgets(id, user_id, month TEXT 'YYYY-MM', monthly_limit REAL)
      - categories(id, name, category_type)
    Pre-populates default categories if missing.
    """
    conn = get_db_connection(db_path)
    try:
        with conn:
            # 1. users table
            conn.execute("""
                CREATE TABLE IF NOT EXISTS users (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    name TEXT NOT NULL,
                    email TEXT NOT NULL UNIQUE,
                    phone TEXT NOT NULL,
                    last_login TEXT NOT NULL
                );
            """)

            # 2. transactions table
            conn.execute("""
                CREATE TABLE IF NOT EXISTS transactions (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    user_id INTEGER NOT NULL,
                    transaction_type TEXT NOT NULL CHECK(transaction_type IN ('income', 'expense')),
                    description TEXT NOT NULL,
                    amount REAL NOT NULL CHECK(amount > 0),
                    category TEXT NOT NULL,
                    need_or_want TEXT NOT NULL DEFAULT 'Need' CHECK(need_or_want IN ('Need', 'Want', 'N/A')),
                    date TEXT NOT NULL,
                    FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE
                );
            """)

            # 3. budgets table
            conn.execute("""
                CREATE TABLE IF NOT EXISTS budgets (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    user_id INTEGER NOT NULL,
                    month TEXT NOT NULL,
                    monthly_limit REAL NOT NULL CHECK(monthly_limit > 0),
                    UNIQUE(user_id, month),
                    FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE
                );
            """)

            # 4. categories table
            conn.execute("""
                CREATE TABLE IF NOT EXISTS categories (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    name TEXT NOT NULL,
                    category_type TEXT NOT NULL CHECK(category_type IN ('income', 'expense')),
                    UNIQUE(name, category_type)
                );
            """)

            # Create performance indexes
            conn.execute("CREATE INDEX IF NOT EXISTS idx_transactions_user_date ON transactions(user_id, date);")
            conn.execute("CREATE INDEX IF NOT EXISTS idx_budgets_user_month ON budgets(user_id, month);")

            # Pre-populate default categories if categories table is empty
            cat_count = conn.execute("SELECT COUNT(*) AS cnt FROM categories").fetchone()["cnt"]
            if cat_count == 0:
                for cat in INCOME_CATEGORIES:
                    conn.execute("INSERT OR IGNORE INTO categories (name, category_type) VALUES (?, 'income')", (cat,))
                for cat in EXPENSE_CATEGORIES:
                    conn.execute("INSERT OR IGNORE INTO categories (name, category_type) VALUES (?, 'expense')", (cat,))
    finally:
        conn.close()


# -----------------------------------------------------------------------------
# User Operations
# -----------------------------------------------------------------------------
def upsert_user(name: str, email: str, phone: str, last_login: str, db_path: Optional[str] = None) -> Dict[str, Any]:
    """
    Stores or updates user in SQLite users table:
    If email exists, updates name, phone, and last_login without creating a duplicate.
    If email does not exist, inserts a new user record.
    Returns the user dict with id, name, email, phone, last_login.
    """
    clean_n = name.strip()
    clean_e = email.strip().lower()
    clean_p = clean_phone_number(phone)

    conn = get_db_connection(db_path)
    try:
        with conn:
            existing = conn.execute("SELECT * FROM users WHERE email = ?", (clean_e,)).fetchone()
            if existing:
                conn.execute(
                    "UPDATE users SET name = ?, phone = ?, last_login = ? WHERE id = ?",
                    (clean_n, clean_p, last_login, existing["id"])
                )
                user_id = existing["id"]
            else:
                cursor = conn.execute(
                    "INSERT INTO users (name, email, phone, last_login) VALUES (?, ?, ?, ?)",
                    (clean_n, clean_e, clean_p, last_login)
                )
                user_id = cursor.lastrowid

            user = conn.execute("SELECT * FROM users WHERE id = ?", (user_id,)).fetchone()
            return dict(user)
    finally:
        conn.close()


def get_user_by_id(user_id: int, db_path: Optional[str] = None) -> Optional[Dict[str, Any]]:
    """Retrieves a user by id."""
    conn = get_db_connection(db_path)
    try:
        row = conn.execute("SELECT * FROM users WHERE id = ?", (user_id,)).fetchone()
        return dict(row) if row else None
    finally:
        conn.close()


# -----------------------------------------------------------------------------
# Budget Health Indicator Calculation
# -----------------------------------------------------------------------------
def calculate_budget_health(spent: float, budget_limit: Optional[float]) -> Dict[str, Any]:
    """
    Calculates Student Budget Health according to exact specification:
      - On Track (<70% used, green)
      - Caution (70-90% used, orange)
      - Near Limit (>90% used and <=100%, deep orange)
      - Over Budget (>100% used, red)
    Special case: If budget_limit is None or <= 0, returns 'No Budget Set'
    """
    if budget_limit is None or budget_limit <= 0:
        return {
            "status": "No Budget Set",
            "pct": 0.0,
            "pct_display": "0%",
            "color_class": "badge-info",
            "progress_color": "var(--primary)",
            "message": "Set a monthly budget to track your student spending health.",
            "is_warning": False,
            "warning_level": 0
        }

    pct = round((spent / budget_limit) * 100, 1)

    if pct < 70.0:
        return {
            "status": "On Track",
            "pct": pct,
            "pct_display": f"{pct}%",
            "color_class": "badge-success",
            "progress_color": "var(--green)",
            "message": "Excellent! Your spending is well within budget (<70%). Keep up the smart saving!",
            "is_warning": False,
            "warning_level": 0
        }
    elif 70.0 <= pct <= 90.0:
        return {
            "status": "Caution",
            "pct": pct,
            "pct_display": f"{pct}%",
            "color_class": "badge-warning",
            "progress_color": "var(--accent)",
            "message": "Caution: You have used 70-90% of your budget. Slow down on non-essential wants.",
            "is_warning": True,
            "warning_level": 70
        }
    elif 90.0 < pct <= 100.0:
        return {
            "status": "Near Limit",
            "pct": pct,
            "pct_display": f"{pct}%",
            "color_class": "badge-near-limit",
            "progress_color": "var(--orange, #FF7675)",
            "message": "Alert: You have reached over 90% of your budget! Only spend on essential needs.",
            "is_warning": True,
            "warning_level": 90
        }
    else:  # pct > 100.0
        return {
            "status": "Over Budget",
            "pct": pct,
            "pct_display": f"{pct}%",
            "color_class": "badge-danger",
            "progress_color": "var(--red)",
            "message": "Warning: You have exceeded your monthly budget! Review your expenses immediately.",
            "is_warning": True,
            "warning_level": 100
        }


# -----------------------------------------------------------------------------
# Transaction Operations (Scoped to user_id)
# -----------------------------------------------------------------------------
def add_transaction(
    user_id: int,
    tx_type: str,
    description: str,
    amount: float,
    category: str,
    need_or_want: str,
    date_str: str,
    db_path: Optional[str] = None
) -> int:
    """Inserts a new transaction scoped to user_id with server validation."""
    clean_type = tx_type.strip().lower()
    if clean_type not in ("income", "expense"):
        raise ValueError("Transaction type must be 'income' or 'expense'.")

    clean_desc = (description or "").strip()
    if not clean_desc:
        raise ValueError("Description cannot be empty.")

    try:
        clean_amount = round(float(amount), 2)
    except (ValueError, TypeError):
        raise ValueError("Amount must be a valid number.")

    if clean_amount <= 0:
        raise ValueError("Amount must be greater than zero.")

    clean_cat = (category or "").strip()
    if not clean_cat:
        raise ValueError("Category is required.")

    # Need vs Want tag: default to 'Need' for expense if not specified, 'N/A' for income
    if clean_type == "income":
        clean_nw = "N/A"
    else:
        clean_nw = "Want" if need_or_want.strip().lower() == "want" else "Need"

    # Validate date format YYYY-MM-DD
    try:
        datetime.strptime(date_str.strip(), "%Y-%m-%d")
        clean_date = date_str.strip()
    except ValueError:
        raise ValueError("Invalid date format. Expected YYYY-MM-DD.")

    conn = get_db_connection(db_path)
    try:
        with conn:
            cursor = conn.execute(
                """
                INSERT INTO transactions (user_id, transaction_type, description, amount, category, need_or_want, date)
                VALUES (?, ?, ?, ?, ?, ?, ?)
                """,
                (user_id, clean_type, clean_desc, clean_amount, clean_cat, clean_nw, clean_date)
            )
            return cursor.lastrowid
    finally:
        conn.close()


def update_transaction(
    tx_id: int,
    user_id: int,
    tx_type: str,
    description: str,
    amount: float,
    category: str,
    need_or_want: str,
    date_str: str,
    db_path: Optional[str] = None
) -> bool:
    """Updates an existing transaction scoped to user_id."""
    clean_type = tx_type.strip().lower()
    if clean_type not in ("income", "expense"):
        raise ValueError("Transaction type must be 'income' or 'expense'.")

    clean_desc = (description or "").strip()
    if not clean_desc:
        raise ValueError("Description cannot be empty.")

    try:
        clean_amount = round(float(amount), 2)
    except (ValueError, TypeError):
        raise ValueError("Amount must be a valid number.")

    if clean_amount <= 0:
        raise ValueError("Amount must be greater than zero.")

    clean_cat = (category or "").strip()
    if not clean_cat:
        raise ValueError("Category is required.")

    if clean_type == "income":
        clean_nw = "N/A"
    else:
        clean_nw = "Want" if need_or_want.strip().lower() == "want" else "Need"

    try:
        datetime.strptime(date_str.strip(), "%Y-%m-%d")
        clean_date = date_str.strip()
    except ValueError:
        raise ValueError("Invalid date format. Expected YYYY-MM-DD.")

    conn = get_db_connection(db_path)
    try:
        with conn:
            cursor = conn.execute(
                """
                UPDATE transactions
                SET transaction_type = ?, description = ?, amount = ?, category = ?, need_or_want = ?, date = ?
                WHERE id = ? AND user_id = ?
                """,
                (clean_type, clean_desc, clean_amount, clean_cat, clean_nw, clean_date, tx_id, user_id)
            )
            return cursor.rowcount > 0
    finally:
        conn.close()


def delete_transaction(tx_id: int, user_id: int, db_path: Optional[str] = None) -> bool:
    """Deletes a transaction scoped to user_id."""
    conn = get_db_connection(db_path)
    try:
        with conn:
            cursor = conn.execute(
                "DELETE FROM transactions WHERE id = ? AND user_id = ?",
                (tx_id, user_id)
            )
            return cursor.rowcount > 0
    finally:
        conn.close()


def get_transaction_by_id(tx_id: int, user_id: int, db_path: Optional[str] = None) -> Optional[Dict[str, Any]]:
    """Retrieves a single transaction by ID scoped to user_id."""
    conn = get_db_connection(db_path)
    try:
        row = conn.execute(
            "SELECT * FROM transactions WHERE id = ? AND user_id = ?",
            (tx_id, user_id)
        ).fetchone()
        return dict(row) if row else None
    finally:
        conn.close()


def get_transactions(
    user_id: int,
    search: Optional[str] = None,
    tx_type: Optional[str] = None,
    category: Optional[str] = None,
    month: Optional[str] = None,
    sort_by: str = "date",
    sort_order: str = "desc",
    limit: Optional[int] = None,
    db_path: Optional[str] = None
) -> List[Dict[str, Any]]:
    """
    Queries transactions scoped to user_id with search, filters, and sorting.
    """
    query = "SELECT * FROM transactions WHERE user_id = ?"
    params: List[Any] = [user_id]

    if search:
        query += " AND (description LIKE ? OR category LIKE ?)"
        term = f"%{search.strip()}%"
        params.extend([term, term])

    if tx_type and tx_type.lower() in ("income", "expense"):
        query += " AND transaction_type = ?"
        params.append(tx_type.lower())

    if category and category.strip():
        query += " AND category = ?"
        params.append(category.strip())

    if month and re.match(r"^\d{4}-\d{2}$", month.strip()):
        query += " AND strftime('%Y-%m', date) = ?"
        params.append(month.strip())

    # Sorting
    order = "ASC" if sort_order.lower() == "asc" else "DESC"
    if sort_by == "amount":
        query += f" ORDER BY amount {order}, date DESC, id DESC"
    else:
        query += f" ORDER BY date {order}, id DESC"

    if limit and limit > 0:
        query += f" LIMIT {int(limit)}"

    conn = get_db_connection(db_path)
    try:
        rows = conn.execute(query, params).fetchall()
        return [dict(r) for r in rows]
    finally:
        conn.close()


def get_transaction_count(user_id: int, db_path: Optional[str] = None) -> int:
    """Returns total number of transactions for user."""
    conn = get_db_connection(db_path)
    try:
        row = conn.execute("SELECT COUNT(*) as cnt FROM transactions WHERE user_id = ?", (user_id,)).fetchone()
        return row["cnt"] if row else 0
    finally:
        conn.close()


# -----------------------------------------------------------------------------
# Monthly Totals & Aggregations
# -----------------------------------------------------------------------------
def get_monthly_totals(user_id: int, month: str, db_path: Optional[str] = None) -> Dict[str, float]:
    """
    Returns monthly income, expense, and net balance for a user and month (YYYY-MM).
    """
    conn = get_db_connection(db_path)
    try:
        rows = conn.execute(
            """
            SELECT transaction_type, COALESCE(SUM(amount), 0.0) as total
            FROM transactions
            WHERE user_id = ? AND strftime('%Y-%m', date) = ?
            GROUP BY transaction_type
            """,
            (user_id, month)
        ).fetchall()

        totals = {"income": 0.0, "expense": 0.0, "balance": 0.0}
        for r in rows:
            if r["transaction_type"] == "income":
                totals["income"] = round(r["total"], 2)
            elif r["transaction_type"] == "expense":
                totals["expense"] = round(r["total"], 2)

        totals["balance"] = round(totals["income"] - totals["expense"], 2)
        return totals
    finally:
        conn.close()


def get_monthly_category_expenses(user_id: int, month: str, db_path: Optional[str] = None) -> List[Dict[str, Any]]:
    """Returns category-wise expense breakdown for user and month."""
    conn = get_db_connection(db_path)
    try:
        rows = conn.execute(
            """
            SELECT category, COALESCE(SUM(amount), 0.0) as total
            FROM transactions
            WHERE user_id = ? AND transaction_type = 'expense' AND strftime('%Y-%m', date) = ?
            GROUP BY category
            ORDER BY total DESC
            """,
            (user_id, month)
        ).fetchall()

        total_expense = sum(r["total"] for r in rows)
        result = []
        for r in rows:
            t = round(r["total"], 2)
            pct = round((t / total_expense * 100), 1) if total_expense > 0 else 0.0
            result.append({
                "category": r["category"],
                "total": t,
                "percentage": pct
            })
        return result
    finally:
        conn.close()


def get_needs_wants_split(user_id: int, month: str, db_path: Optional[str] = None) -> Dict[str, float]:
    """
    Returns total spent on Needs vs Wants for user and month.
    """
    conn = get_db_connection(db_path)
    try:
        rows = conn.execute(
            """
            SELECT need_or_want, COALESCE(SUM(amount), 0.0) as total
            FROM transactions
            WHERE user_id = ? AND transaction_type = 'expense' AND strftime('%Y-%m', date) = ?
            GROUP BY need_or_want
            """,
            (user_id, month)
        ).fetchall()

        res = {"Need": 0.0, "Want": 0.0}
        for r in rows:
            nw = r["need_or_want"]
            if nw in res:
                res[nw] = round(r["total"], 2)
        return res
    finally:
        conn.close()


def get_monthly_comparison(user_id: int, current_month: str, num_months: int = 6, db_path: Optional[str] = None) -> List[Dict[str, Any]]:
    """
    Returns last `num_months` comparison of income, expense, and savings.
    """
    try:
        curr_dt = datetime.strptime(current_month, "%Y-%m")
    except ValueError:
        curr_dt = datetime.now()

    months = []
    # Build list of month strings in chronological order
    for i in range(num_months - 1, -1, -1):
        # Approximate month subtraction safely
        year = curr_dt.year
        month = curr_dt.month - i
        while month <= 0:
            month += 12
            year -= 1
        m_str = f"{year:04d}-{month:02d}"
        months.append(m_str)

    conn = get_db_connection(db_path)
    try:
        result = []
        for m in months:
            totals = get_monthly_totals(user_id, m, db_path=db_path)
            dt = datetime.strptime(m, "%Y-%m")
            result.append({
                "month": m,
                "label": dt.strftime("%b %Y"),
                "income": totals["income"],
                "expense": totals["expense"],
                "savings": totals["balance"]
            })
        return result
    finally:
        conn.close()


# -----------------------------------------------------------------------------
# Budget Operations
# -----------------------------------------------------------------------------
def set_budget(user_id: int, month: str, monthly_limit: float, db_path: Optional[str] = None) -> None:
    """Sets or updates the monthly budget limit for user and month."""
    if not re.match(r"^\d{4}-\d{2}$", month.strip()):
        raise ValueError("Invalid month format. Expected YYYY-MM.")

    try:
        limit = round(float(monthly_limit), 2)
    except (ValueError, TypeError):
        raise ValueError("Monthly limit must be a valid number.")

    if limit <= 0:
        raise ValueError("Monthly limit must be greater than zero.")

    conn = get_db_connection(db_path)
    try:
        with conn:
            conn.execute(
                """
                INSERT INTO budgets (user_id, month, monthly_limit)
                VALUES (?, ?, ?)
                ON CONFLICT(user_id, month) DO UPDATE SET monthly_limit = excluded.monthly_limit
                """,
                (user_id, month.strip(), limit)
            )
    finally:
        conn.close()


def get_budget(user_id: int, month: str, db_path: Optional[str] = None) -> Optional[Dict[str, Any]]:
    """Retrieves budget record for user and month."""
    conn = get_db_connection(db_path)
    try:
        row = conn.execute(
            "SELECT * FROM budgets WHERE user_id = ? AND month = ?",
            (user_id, month.strip())
        ).fetchone()
        return dict(row) if row else None
    finally:
        conn.close()


# -----------------------------------------------------------------------------
# Demo Data Loader
# -----------------------------------------------------------------------------
def load_sample_data(user_id: int, month: Optional[str] = None, db_path: Optional[str] = None) -> int:
    """
    Inserts realistic demo data for current month:
      - ₹15,000 Allowance income
      - ~12 expenses (Food, Transport, Shopping, Subscriptions, Education, etc.)
      - ₹10,000 budget
    Only inserts if user has no transactions yet.
    """
    if not month:
        ist_offset = timezone(timedelta(hours=5, minutes=30))
        month = datetime.now(ist_offset).strftime("%Y-%m")

    conn = get_db_connection(db_path)
    try:
        with conn:
            # Check if user already has transactions
            count = conn.execute(
                "SELECT COUNT(*) as cnt FROM transactions WHERE user_id = ?",
                (user_id,)
            ).fetchone()["cnt"]

            if count > 0:
                return 0

            # 1. Set ₹10,000 budget
            conn.execute(
                """
                INSERT INTO budgets (user_id, month, monthly_limit)
                VALUES (?, ?, 10000.0)
                ON CONFLICT(user_id, month) DO UPDATE SET monthly_limit = 10000.0
                """,
                (user_id, month)
            )

            # 2. Add ₹15,000 Allowance income on the 1st
            demo_txs = [
                ("income", "Monthly Student Allowance from Parents", 15000.0, "Allowance", "N/A", f"{month}-01"),
                ("expense", "College Canteen Lunch & Snacks", 340.0, "Food", "Need", f"{month}-02"),
                ("expense", "Metro Smart Card Recharge", 600.0, "Transport", "Need", f"{month}-03"),
                ("expense", "Python Programming Reference Books", 850.0, "Education", "Need", f"{month}-05"),
                ("expense", "Spotify Student Premium Subscription", 59.0, "Subscriptions", "Want", f"{month}-06"),
                ("expense", "Weekend Cafe Coffee & Snacks", 280.0, "Food", "Want", f"{month}-08"),
                ("expense", "Monthly Mobile Data & Calling Recharge", 399.0, "Bills", "Need", f"{month}-10"),
                ("expense", "Casual Hoodie & Sneaker Cleaner", 1250.0, "Shopping", "Want", f"{month}-11"),
                ("expense", "Pharmacy Multivitamins & Cold Medicine", 260.0, "Health", "Need", f"{month}-12"),
                ("expense", "Movie Ticket & Popcorn with Friends", 450.0, "Entertainment", "Want", f"{month}-13"),
                ("expense", "Groceries & Hostel Essentials", 1120.0, "Food", "Need", f"{month}-14"),
                ("expense", "Auto Rickshaw Campus Travel", 180.0, "Transport", "Need", f"{month}-15"),
                ("expense", "Online Coding Bootcamp Certification Exam Fee", 1500.0, "Education", "Need", f"{month}-16"),
            ]

            inserted = 0
            for tx_type, desc, amt, cat, nw, dt in demo_txs:
                conn.execute(
                    """
                    INSERT INTO transactions (user_id, transaction_type, description, amount, category, need_or_want, date)
                    VALUES (?, ?, ?, ?, ?, ?, ?)
                    """,
                    (user_id, tx_type, desc, amt, cat, nw, dt)
                )
                inserted += 1

            return inserted
    finally:
        conn.close()
