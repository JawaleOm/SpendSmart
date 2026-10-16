"""
app.py - SpendSmart: Personal Expense Tracker
=============================================
A modern, colorful, student-friendly personal finance web application built
with Python, Flask, HTML5, CSS3, vanilla JavaScript, and SQLite (without ORM).

Features:
  - Passwordless 3-field login with server & client validation
  - Live clock updating every second on login page
  - Student Budget Health Indicator (Python rules: On Track, Caution, Near Limit, Over Budget)
  - Responsive glassmorphism UI with Google Poppins & Inter fonts
  - Dynamic popping and floating finance icons background
  - Complete transactions management (Add, Edit, Delete, Search, Filter, Sort)
  - Needs vs Wants tagging and breakdown analytics
  - Monthly budget setting with 70%, 90%, 100% threshold warning alerts
  - Category doughnut/bar charts and 6-month cash flow trends with Chart.js
  - CSV report export
  - Clean error handling (404, 500)
"""

import csv
import io
import os
import re
from datetime import datetime
from functools import wraps
from typing import Optional

from flask import (
    Flask,
    Response,
    abort,
    flash,
    redirect,
    render_template,
    request,
    session,
    url_for,
)

import database

# Initialize Flask application
app = Flask(__name__)

# Application Configuration
# Secret key read from environment with safe local dev fallback
app.config["SECRET_KEY"] = os.environ.get(
    "SECRET_KEY", "spendsmart-dev-secure-key-2026-python-cert"
)

# Production-grade session cookie settings (Secure on Vercel over HTTPS)
is_vercel = bool(os.environ.get("VERCEL"))
app.config["SESSION_COOKIE_HTTPONLY"] = True
app.config["SESSION_COOKIE_SAMESITE"] = "Lax"
app.config["SESSION_COOKIE_SECURE"] = is_vercel

# Ensure database tables exist on startup
database.init_db()


# -----------------------------------------------------------------------------
# Authentication Guard Decorator
# -----------------------------------------------------------------------------
def login_required(f):
    """Decorator ensuring routes are protected: redirects unauthenticated users to /login."""
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if "user_id" not in session:
            flash("Please sign in to access SpendSmart.", "info")
            return redirect(url_for("login_page"))
        return f(*args, **kwargs)
    return decorated_function


# -----------------------------------------------------------------------------
# Template Context Processors & Filters
# -----------------------------------------------------------------------------
@app.context_processor
def inject_global_utilities():
    """Injects formatting functions and categories into all Jinja2 templates."""
    date_str, time_str, _ = database.get_current_time_display()
    now_dt = datetime.now()
    return {
        "format_inr": database.format_inr,
        "expense_categories": database.EXPENSE_CATEGORIES,
        "income_categories": database.INCOME_CATEGORIES,
        "today_date": now_dt.strftime("%Y-%m-%d"),
        "current_month_str": now_dt.strftime("%Y-%m"),
        "min": min,
        "max": max,
    }


def get_month_label(month_str: str) -> str:
    """Converts 'YYYY-MM' to a friendly string like 'October 2026'."""
    try:
        dt = datetime.strptime(month_str, "%Y-%m")
        return dt.strftime("%B %Y")
    except (ValueError, TypeError):
        return month_str


# -----------------------------------------------------------------------------
# Route: Root ("/")
# -----------------------------------------------------------------------------
@app.route("/")
def index():
    """
    Root route: redirects to /login if user is not logged in,
    otherwise redirects to /dashboard.
    """
    if "user_id" in session:
        return redirect(url_for("dashboard"))
    return redirect(url_for("login_page"))


# -----------------------------------------------------------------------------
# Route: Login Page ("/login")
# -----------------------------------------------------------------------------
@app.route("/login", methods=["GET", "POST"])
def login_page():
    """
    Renders login card with Live Clock, big SpendSmart logo, and exactly 3 fields:
      1. Full Name (required, min 2 characters)
      2. Email ID (required, valid email format)
      3. Phone Number (required, 10-digit Indian mobile number, optional +91 prefix)
    Validates on server-side and stores login timestamp in session and users table.
    """
    # If already logged in, go straight to dashboard
    if "user_id" in session and request.method == "GET":
        return redirect(url_for("dashboard"))

    errors = {}
    form_data = {}

    if request.method == "POST":
        name = request.form.get("name", "").strip()
        email = request.form.get("email", "").strip()
        phone = request.form.get("phone", "").strip()

        form_data = {"name": name, "email": email, "phone": phone}

        # Validate Name
        is_name_valid, err_name = database.validate_name(name)
        if not is_name_valid:
            errors["name"] = err_name

        # Validate Email
        is_email_valid, err_email = database.validate_email(email)
        if not is_email_valid:
            errors["email"] = err_email

        # Validate Phone (10-digit Indian mobile number with optional +91)
        is_phone_valid, err_phone = database.validate_phone(phone)
        if not is_phone_valid:
            errors["phone"] = err_phone

        if errors:
            return render_template("login.html", errors=errors, form_data=form_data)

        # Record exact login timestamp
        date_str, time_str, full_display = database.get_current_time_display()

        # Upsert user record in SQLite users table
        user = database.upsert_user(name, email, phone, full_display)

        # Store in Flask session
        session["user_id"] = user["id"]
        session["user_name"] = user["name"]
        session["user_email"] = user["email"]
        session["user_phone"] = user["phone"]
        session["login_date"] = date_str
        session["login_time"] = time_str
        session["login_time_short"] = time_str
        session["login_timestamp"] = full_display

        # Flash welcome message
        flash(f"Welcome, {user['name']}! You logged in on {date_str} at {time_str}.", "success")
        return redirect(url_for("dashboard"))

    return render_template("login.html", errors=errors, form_data=form_data)


# -----------------------------------------------------------------------------
# Route: Logout ("/logout")
# -----------------------------------------------------------------------------
@app.route("/logout", methods=["GET", "POST"])
def logout():
    """Clears the session and redirects to the login page."""
    session.clear()
    flash("You have been logged out successfully.", "info")
    return redirect(url_for("login_page"))


# -----------------------------------------------------------------------------
# Route: Demo Quick Sign-In ("/demo-login")
# -----------------------------------------------------------------------------
@app.route("/demo-login")
def demo_login():
    """Seeds sample student profile with demo data and sets session for review."""
    date_str, time_str, full_display = database.get_current_time_display()
    user = database.upsert_user("Aarav Sharma", "aarav@example.com", "+91 9876543210", full_display)
    database.load_sample_data(user["id"])

    session["user_id"] = user["id"]
    session["user_name"] = user["name"]
    session["user_email"] = user["email"]
    session["user_phone"] = user["phone"]
    session["login_date"] = date_str
    session["login_time"] = time_str
    session["login_time_short"] = time_str
    session["login_timestamp"] = full_display

    target = request.args.get("next", url_for("dashboard"))
    return redirect(target)


# -----------------------------------------------------------------------------
# Route: Dashboard ("/dashboard")
# -----------------------------------------------------------------------------
@app.route("/dashboard")
@login_required
def dashboard():
    """
    Renders main dashboard with:
      - Welcome banner with user name & login timestamp
      - 4 summary cards: Total Income, Total Expenses, Remaining Balance, Monthly Budget Left
      - Budget usage progress bar & Student Budget Health Indicator (Python rules)
      - Doughnut chart of expenses by category (Chart.js)
      - Recent 5 transactions list
      - Quick "+ Add Transaction" floating action button
      - "Load Sample Data" button if user has 0 transactions
    """
    user_id = session["user_id"]
    current_month = request.args.get("month", "").strip()
    if not re.match(r"^\d{4}-\d{2}$", current_month):
        current_month = datetime.now().strftime("%Y-%m")

    month_label = get_month_label(current_month)

    # Scoped financial totals for the month
    totals = database.get_monthly_totals(user_id, current_month)

    # Scoped budget for the month
    budget_row = database.get_budget(user_id, current_month)
    budget_info = None
    if budget_row:
        limit = budget_row["monthly_limit"]
        remaining = round(limit - totals["expense"], 2)
        budget_info = {
            "monthly_limit": limit,
            "spent": totals["expense"],
            "remaining": remaining,
        }

    # Student Budget Health Indicator calculation (Python rules)
    health = database.calculate_budget_health(
        totals["expense"],
        budget_info["monthly_limit"] if budget_info else None
    )

    # Category breakdown for doughnut chart
    category_expenses = database.get_monthly_category_expenses(user_id, current_month)
    cat_labels = [c["category"] for c in category_expenses]
    cat_data = [c["total"] for c in category_expenses]

    # Recent 5 transactions
    recent_transactions = database.get_transactions(user_id, month=current_month, limit=5)

    # Total user transactions count (for demo data button visibility)
    tx_count = database.get_transaction_count(user_id)

    return render_template(
        "dashboard.html",
        user_name=session.get("user_name"),
        login_date=session.get("login_date", datetime.now().strftime("%d %b %Y")),
        login_time=session.get("login_time", datetime.now().strftime("%I:%M %p")),
        current_month=current_month,
        month_label=month_label,
        totals=totals,
        budget_info=budget_info,
        health=health,
        category_expenses=category_expenses,
        cat_labels=cat_labels,
        cat_data=cat_data,
        recent_transactions=recent_transactions,
        tx_count=tx_count,
    )


# -----------------------------------------------------------------------------
# Route: Load Sample Data ("/load-sample-data")
# -----------------------------------------------------------------------------
@app.route("/load-sample-data", methods=["POST"])
@login_required
def load_sample_data_route():
    """Seeds realistic demo data (₹15,000 allowance, 12 expenses, ₹10,000 budget)."""
    user_id = session["user_id"]
    inserted = database.load_sample_data(user_id)
    if inserted > 0:
        flash(
            "Demo data loaded successfully! Added ₹15,000 allowance income, 12 categorized student expenses, and a ₹10,000 budget.",
            "success",
        )
    else:
        flash("Sample data was not loaded because you already have transactions.", "info")
    return redirect(url_for("dashboard"))


# -----------------------------------------------------------------------------
# Route: Transactions List ("/transactions")
# -----------------------------------------------------------------------------
@app.route("/transactions")
@login_required
def transactions_list():
    """
    Displays transactions table with search, type filter, category filter,
    month filter, and sorting by date or amount.
    """
    user_id = session["user_id"]
    search_query = request.args.get("search", "").strip()
    current_type = request.args.get("type", "").strip().lower()
    current_category = request.args.get("category", "").strip()
    current_month = request.args.get("month", "").strip()
    current_sort = request.args.get("sort", "date_desc").strip().lower()

    # Determine sort field & order
    if current_sort == "amount_asc":
        sort_by, sort_order = "amount", "asc"
    elif current_sort == "amount_desc":
        sort_by, sort_order = "amount", "desc"
    elif current_sort == "date_asc":
        sort_by, sort_order = "date", "asc"
    else:
        sort_by, sort_order = "date", "desc"

    transactions = database.get_transactions(
        user_id=user_id,
        search=search_query,
        tx_type=current_type,
        category=current_category,
        month=current_month,
        sort_by=sort_by,
        sort_order=sort_order,
    )

    return render_template(
        "transactions.html",
        transactions=transactions,
        search_query=search_query,
        current_type=current_type,
        current_category=current_category,
        current_month=current_month,
        current_sort=current_sort,
    )


# -----------------------------------------------------------------------------
# Route: Add Transaction ("/transactions/add")
# -----------------------------------------------------------------------------
@app.route("/transactions/add", methods=["GET", "POST"])
@login_required
def transaction_add():
    """Handles adding a new transaction with server-side validation."""
    user_id = session["user_id"]
    errors = {}
    form_data = {
        "transaction_type": "expense",
        "date": datetime.now().strftime("%Y-%m-%d"),
        "need_or_want": "Need",
    }

    if request.method == "POST":
        tx_type = request.form.get("transaction_type", "").strip().lower()
        amount_raw = request.form.get("amount", "").strip()
        description = request.form.get("description", "").strip()
        category = request.form.get("category", "").strip()
        need_or_want = request.form.get("need_or_want", "Need").strip()
        date_str = request.form.get("date", "").strip()

        form_data = {
            "transaction_type": tx_type,
            "amount": amount_raw,
            "description": description,
            "category": category,
            "need_or_want": need_or_want,
            "date": date_str,
        }

        # Server-side validations with try/except
        try:
            database.add_transaction(
                user_id=user_id,
                tx_type=tx_type,
                description=description,
                amount=amount_raw,
                category=category,
                need_or_want=need_or_want,
                date_str=date_str,
            )
            flash("Transaction added successfully!", "success")
            return redirect(url_for("transactions_list"))
        except ValueError as e:
            msg = str(e)
            if "Amount" in msg:
                errors["amount"] = msg
            elif "Description" in msg:
                errors["description"] = msg
            elif "Category" in msg:
                errors["category"] = msg
            elif "date" in msg.lower():
                errors["date"] = msg
            else:
                errors["general"] = msg
            flash(f"Please check your inputs: {msg}", "danger")

    return render_template(
        "transaction_form.html",
        is_edit=False,
        form_data=form_data,
        errors=errors,
    )


# -----------------------------------------------------------------------------
# Route: Edit Transaction ("/transactions/edit/<id>")
# -----------------------------------------------------------------------------
@app.route("/transactions/edit/<int:tx_id>", methods=["GET", "POST"])
@login_required
def transaction_edit(tx_id: int):
    """Handles updating an existing transaction scoped to the user."""
    user_id = session["user_id"]
    tx = database.get_transaction_by_id(tx_id, user_id)
    if not tx:
        abort(404)

    errors = {}
    form_data = dict(tx)

    if request.method == "POST":
        tx_type = request.form.get("transaction_type", "").strip().lower()
        amount_raw = request.form.get("amount", "").strip()
        description = request.form.get("description", "").strip()
        category = request.form.get("category", "").strip()
        need_or_want = request.form.get("need_or_want", "Need").strip()
        date_str = request.form.get("date", "").strip()

        form_data = {
            "transaction_type": tx_type,
            "amount": amount_raw,
            "description": description,
            "category": category,
            "need_or_want": need_or_want,
            "date": date_str,
        }

        try:
            database.update_transaction(
                tx_id=tx_id,
                user_id=user_id,
                tx_type=tx_type,
                description=description,
                amount=amount_raw,
                category=category,
                need_or_want=need_or_want,
                date_str=date_str,
            )
            flash("Transaction updated successfully!", "success")
            return redirect(url_for("transactions_list"))
        except ValueError as e:
            msg = str(e)
            if "Amount" in msg:
                errors["amount"] = msg
            elif "Description" in msg:
                errors["description"] = msg
            elif "Category" in msg:
                errors["category"] = msg
            elif "date" in msg.lower():
                errors["date"] = msg
            else:
                errors["general"] = msg
            flash(f"Error updating transaction: {msg}", "danger")

    return render_template(
        "transaction_form.html",
        is_edit=True,
        form_data=form_data,
        errors=errors,
    )


# -----------------------------------------------------------------------------
# Route: Delete Transaction ("/transactions/delete/<id>")
# -----------------------------------------------------------------------------
@app.route("/transactions/delete/<int:tx_id>", methods=["POST"])
@login_required
def transaction_delete(tx_id: int):
    """Deletes a transaction scoped to the logged-in user."""
    user_id = session["user_id"]
    deleted = database.delete_transaction(tx_id, user_id)
    if deleted:
        flash("Transaction deleted successfully.", "success")
    else:
        flash("Transaction not found or could not be deleted.", "danger")
    return redirect(url_for("transactions_list"))


# -----------------------------------------------------------------------------
# Route: Budget Planner ("/budget")
# -----------------------------------------------------------------------------
@app.route("/budget", methods=["GET", "POST"])
@login_required
def budget_planner():
    """
    Sets monthly budget limits, displays spent, remaining, % used,
    and shows warning banners for spending reaching 70%, 90%, and 100%.
    """
    user_id = session["user_id"]

    # Determine selected month
    if request.method == "POST":
        selected_month = request.form.get("month", "").strip()
    else:
        selected_month = request.args.get("month", "").strip()

    if not re.match(r"^\d{4}-\d{2}$", selected_month):
        selected_month = datetime.now().strftime("%Y-%m")

    month_label = get_month_label(selected_month)

    # Handle Budget Set / Update POST
    if request.method == "POST":
        monthly_limit_raw = request.form.get("monthly_limit", "").strip()
        try:
            database.set_budget(user_id, selected_month, monthly_limit_raw)
            flash(
                f"Budget limit of {database.format_inr(monthly_limit_raw)} saved for {month_label}!",
                "success",
            )
            return redirect(url_for("budget_planner", month=selected_month))
        except ValueError as e:
            flash(f"Could not save budget: {str(e)}", "danger")

    # Scoped calculations
    totals = database.get_monthly_totals(user_id, selected_month)
    budget = database.get_budget(user_id, selected_month)

    remaining_budget = 0.0
    if budget:
        remaining_budget = round(budget["monthly_limit"] - totals["expense"], 2)

    health = database.calculate_budget_health(
        totals["expense"],
        budget["monthly_limit"] if budget else None
    )

    return render_template(
        "budget.html",
        selected_month=selected_month,
        month_label=month_label,
        totals=totals,
        budget=budget,
        remaining_budget=remaining_budget,
        health=health,
    )


# -----------------------------------------------------------------------------
# Route: Reports & Analytics ("/reports")
# -----------------------------------------------------------------------------
@app.route("/reports")
@login_required
def reports_page():
    """
    Renders reports page with:
      - Month selector
      - Total income, total expenses, savings or deficit for the month
      - Category-wise expense table and bar chart
      - Needs vs Wants split chart
      - Month-by-month spending comparison chart (last 6 months)
      - Export CSV button
    """
    user_id = session["user_id"]
    selected_month = request.args.get("month", "").strip()
    if not re.match(r"^\d{4}-\d{2}$", selected_month):
        selected_month = datetime.now().strftime("%Y-%m")

    month_label = get_month_label(selected_month)

    # Monthly financial summary
    totals = database.get_monthly_totals(user_id, selected_month)

    # Category breakdown
    category_expenses = database.get_monthly_category_expenses(user_id, selected_month)
    cat_labels = [c["category"] for c in category_expenses]
    cat_data = [c["total"] for c in category_expenses]

    # Needs vs Wants split
    needs_wants = database.get_needs_wants_split(user_id, selected_month)

    # 6-Month comparison
    comparison = database.get_monthly_comparison(user_id, selected_month, num_months=6)
    comparison_labels = [c["label"] for c in comparison]
    comparison_income = [c["income"] for c in comparison]
    comparison_expense = [c["expense"] for c in comparison]

    return render_template(
        "reports.html",
        selected_month=selected_month,
        month_label=month_label,
        totals=totals,
        category_expenses=category_expenses,
        cat_labels=cat_labels,
        cat_data=cat_data,
        needs_wants=needs_wants,
        comparison_labels=comparison_labels,
        comparison_income=comparison_income,
        comparison_expense=comparison_expense,
    )


# -----------------------------------------------------------------------------
# Route: Export CSV ("/reports/export-csv")
# -----------------------------------------------------------------------------
@app.route("/reports/export-csv")
@login_required
def export_csv_route():
    """Exports monthly transactions for the selected month as a CSV download."""
    user_id = session["user_id"]
    month = request.args.get("month", "").strip()
    if not re.match(r"^\d{4}-\d{2}$", month):
        month = datetime.now().strftime("%Y-%m")

    transactions = database.get_transactions(user_id=user_id, month=month, sort_by="date", sort_order="asc")

    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow(["Date", "Description", "Type", "Category", "Need_or_Want", "Amount_INR"])

    for tx in transactions:
        # Sanitize formula injection prefixes
        desc = tx["description"]
        if desc and desc[0] in ("=", "+", "-", "@"):
            desc = "'" + desc
        writer.writerow([
            tx["date"],
            desc,
            tx["transaction_type"],
            tx["category"],
            tx["need_or_want"],
            f"{tx['amount']:.2f}",
        ])

    csv_data = output.getvalue()
    filename = f"SpendSmart_Transactions_{month}.csv"
    return Response(
        csv_data,
        mimetype="text/csv",
        headers={"Content-Disposition": f"attachment; filename={filename}"},
    )


# -----------------------------------------------------------------------------
# Route: About Page ("/about")
# -----------------------------------------------------------------------------
@app.route("/about")
def about_page():
    """Renders the About page with architecture details and certification note."""
    return render_template("about.html")


# -----------------------------------------------------------------------------
# Error Handlers: 404 & 500
# -----------------------------------------------------------------------------
@app.errorhandler(404)
def page_not_found(e):
    """Custom themed 404 error page."""
    return render_template("404.html"), 404


@app.errorhandler(500)
def server_error(e):
    """Custom themed 500 error page."""
    return render_template("500.html"), 500


# -----------------------------------------------------------------------------
# Application Runner
# -----------------------------------------------------------------------------
if __name__ == "__main__":
    # Dev server listening on port 5000
    app.run(host="127.0.0.1", port=5000, debug=True)
