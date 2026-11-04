"""
SQL problems — SQLite dialect (Judge0 "SQL (SQLite 3.27.2)").

Each test's input is the schema and seed data for a fresh, empty SQLite database
created inside the Judge0 sandbox (see coding_harness). Candidate SQL never runs
against the CareerSphere PostgreSQL database.

Output is the sqlite3 shell's list mode: columns separated by '|', NULL printed as
NULL, one row per line, no header. The oracle reproduces that format with Python's
sqlite3 module; Judge0 verification then confirms SQLite 3.27.2 produces the same.
"""

from __future__ import annotations

import random
import sqlite3
from typing import Callable

from app.data.coding_bank import ProblemSpec, Test

SQL_ONLY = ("SQLITE",)
SQL_ROLES = (
    "database-developer", "sql-developer", "postgresql-developer", "mysql-developer",
    "database-administrator", "data-analyst", "data-engineer",
)
SQL_NOTE = (
    "Dialect: SQLite 3.27.2. Write a single query (SQL statements only — no sqlite3 dot-commands). "
    "Output is printed in list mode: columns separated by '|', NULL shown as NULL, no header row."
)


def _cell(value) -> str:
    if value is None:
        return "NULL"
    if isinstance(value, float):
        text = format(value, ".15g")
        return text if any(ch in text for ch in ".eni") else text + ".0"  # sqlite3's "%!.15g"
    return str(value)


def sqlite_oracle(reference_sql: str) -> Callable[[str], str]:
    def run(setup_sql: str) -> str:
        db = sqlite3.connect(":memory:")
        try:
            db.execute("PRAGMA foreign_keys = ON")
            db.executescript(setup_sql)
            rows = db.execute(reference_sql).fetchall()
        finally:
            db.close()
        return "".join("|".join(_cell(v) for v in row) + "\n" for row in rows)

    return run


def _quote(value) -> str:
    if value is None:
        return "NULL"
    if isinstance(value, str):
        return "'" + value.replace("'", "''") + "'"
    return str(value)


def _insert(table: str, rows: list[tuple]) -> str:
    if not rows:
        return ""
    values = ",\n".join("(" + ", ".join(_quote(v) for v in row) + ")" for row in rows)
    return f"INSERT INTO {table} VALUES\n{values};\n"


FIRST = ["Aarav", "Diya", "Kabir", "Meera", "Rohan", "Sara", "Vikram", "Zoya", "Ishan", "Anika", "Dev", "Nisha"]
LAST = ["Shah", "Iyer", "Khan", "Rao", "Mehta", "Das", "Patel", "Nair", "Bose", "Gill"]


def _name(r: random.Random, used: set) -> str:
    while True:
        name = f"{r.choice(FIRST)} {r.choice(LAST)}"
        if name not in used:
            used.add(name)
            return name


# ---------------------------------------------------------------------------
# 17. Filtering — active customers
# ---------------------------------------------------------------------------

_CUSTOMERS_SCHEMA = """CREATE TABLE customers (
  id INTEGER PRIMARY KEY,
  name TEXT NOT NULL,
  city TEXT,
  status TEXT NOT NULL,          -- 'active' | 'inactive' | 'suspended'
  signup_date TEXT NOT NULL,     -- 'YYYY-MM-DD'
  credit INTEGER NOT NULL        -- in rupees
);
"""

_ACTIVE_SQL = """SELECT id, name, city
FROM customers
WHERE status = 'active'
  AND city IN ('Pune', 'Mumbai')
  AND signup_date >= '2024-01-01'
  AND credit >= 1000
ORDER BY signup_date DESC, name ASC, id ASC;"""


def _customers_setup(rows: list[tuple]) -> str:
    return _CUSTOMERS_SCHEMA + _insert("customers", rows)


def _random_customers(r: random.Random, n: int) -> list[tuple]:
    used: set = set()
    rows = []
    for i in range(1, n + 1):
        city = r.choice(["Pune", "Mumbai", "Delhi", "Chennai", None, "Pune"])
        date = f"{r.choice([2022, 2023, 2024, 2025])}-{r.randint(1, 12):02d}-{r.randint(1, 28):02d}"
        rows.append((i, _name(r, used) if len(used) < 110 else f"Customer {i}", city,
                     r.choice(["active", "active", "inactive", "suspended"]), date, r.choice([0, 500, 999, 1000, 2500, 10000])))
    return rows


def _active_tests() -> tuple[Test, ...]:
    r = random.Random(1717)
    sample = [
        (1, "Asha Rao", "Pune", "active", "2024-03-10", 1500),
        (2, "Bilal Khan", "Mumbai", "inactive", "2024-05-01", 5000),
        (3, "Chitra Iyer", "Delhi", "active", "2024-06-15", 2000),
        (4, "Dev Mehta", "Mumbai", "active", "2023-12-31", 3000),
        (5, "Esha Nair", "Mumbai", "active", "2025-01-20", 1000),
        (6, "Farhan Das", None, "active", "2024-08-08", 4000),
    ]
    ties = [
        (10, "Zara Shah", "Pune", "active", "2024-04-04", 1200),
        (11, "Arjun Shah", "Mumbai", "active", "2024-04-04", 1200),
        (12, "Mira Gill", "Pune", "active", "2024-01-01", 999),
    ]
    return (
        Test(_customers_setup(sample), hidden=False,
             explanation="Bilal is inactive, Chitra is in Delhi, Dev signed up in 2023 and Farhan has no city."),
        Test(_customers_setup(ties), hidden=False, explanation="Same signup date: sorted by name. Mira's credit is below 1000."),
        Test(_customers_setup([(1, "Only Inactive", "Pune", "inactive", "2025-01-01", 9000)])),
        Test(_customers_setup([(1, "Edge Case", "Pune", "active", "2024-01-01", 1000), (2, "Case Sensitive", "pune", "active", "2024-02-02", 5000)])),
        Test(_customers_setup(_random_customers(r, 60))),
        Test(_customers_setup(_random_customers(r, 400)), weight=2.0),
    )


ACTIVE_CUSTOMERS = ProblemSpec(
    slug="sql-active-customers",
    title="Active Customers in Target Cities",
    category="sql",
    difficulty="EASY",
    summary="Filter and sort customers with SELECT, WHERE and ORDER BY (SQLite).",
    roles=SQL_ROLES,
    competencies=("sql-queries",),
    statement=(
        "Marketing wants to contact recent, creditworthy customers in two cities.\n\n"
        "Table customers(id, name, city, status, signup_date, credit). Return id, name and city of "
        "customers who are 'active', live in 'Pune' or 'Mumbai', signed up on or after 2024-01-01 "
        "(signup_date is an ISO 'YYYY-MM-DD' string) and have credit of at least 1000.\n\n"
        "Order by signup_date descending, then name ascending, then id ascending. City names are "
        "case-sensitive; customers with no city are excluded."
    ),
    input_format=_CUSTOMERS_SCHEMA + "\nEach test creates this table in a fresh database with its own rows.",
    output_format="id|name|city per row, in the required order.",
    constraints="Up to 1 000 rows",
    languages=SQL_ONLY,
    starter_code={
        "SQLITE": "-- customers(id, name, city, status, signup_date, credit)\n"
                  "-- Write one SELECT statement.\n\n-- SELECT id, name, city\n-- FROM customers\n-- WHERE ...\n-- ORDER BY ...;\n",
    },
    reference_solutions={"SQLITE": _ACTIVE_SQL},
    wrong_solutions=(
        ("SQLITE", _ACTIVE_SQL.replace("  AND signup_date >= '2024-01-01'\n", ""), "Ignores the signup-date filter."),
        ("SQLITE", _ACTIVE_SQL.replace("credit >= 1000", "credit > 1000"), "Excludes the boundary credit value."),
        ("SQLITE", _ACTIVE_SQL.replace("ORDER BY signup_date DESC, name ASC, id ASC", "ORDER BY signup_date DESC"), "Missing the tie-break order."),
    ),
    tests=_active_tests(),
    oracle=sqlite_oracle(_ACTIVE_SQL),
    instructions=SQL_NOTE,
    time_limit_seconds=2.0,
    estimated_minutes=10,
)


# ---------------------------------------------------------------------------
# 18. JOIN — order counts including customers without orders
# ---------------------------------------------------------------------------

_ORDERS_SCHEMA = """CREATE TABLE customers (
  id INTEGER PRIMARY KEY,
  name TEXT NOT NULL
);
CREATE TABLE orders (
  id INTEGER PRIMARY KEY,
  customer_id INTEGER NOT NULL REFERENCES customers(id),
  status TEXT NOT NULL,          -- 'completed' | 'cancelled' | 'pending'
  amount INTEGER NOT NULL        -- in paise
);
"""

_JOIN_SQL = """SELECT c.name,
       COUNT(o.id) AS completed_orders,
       COALESCE(SUM(o.amount), 0) AS total_amount
FROM customers AS c
LEFT JOIN orders AS o
  ON o.customer_id = c.id AND o.status = 'completed'
GROUP BY c.id, c.name
ORDER BY total_amount DESC, c.name ASC, c.id ASC;"""


def _orders_setup(customers: list[tuple], orders: list[tuple]) -> str:
    return _ORDERS_SCHEMA + _insert("customers", customers) + _insert("orders", orders)


def _random_orders(r: random.Random, customers: int, orders: int) -> str:
    used: set = set()
    cust = [(i, _name(r, used) if len(used) < 110 else f"Customer {i}") for i in range(1, customers + 1)]
    rows = [(i, r.randint(1, customers), r.choice(["completed", "completed", "cancelled", "pending"]), r.randint(100, 50000))
            for i in range(1, orders + 1)]
    return _orders_setup(cust, rows)


def _join_tests() -> tuple[Test, ...]:
    r = random.Random(1818)
    return (
        Test(_orders_setup([(1, "Asha Rao"), (2, "Bilal Khan"), (3, "Chitra Iyer")],
                           [(1, 1, "completed", 500), (2, 1, "cancelled", 900), (3, 2, "completed", 700), (4, 1, "completed", 300)]),
             hidden=False, explanation="Asha has 2 completed orders (800); Chitra has none and still appears with 0."),
        Test(_orders_setup([(1, "Zed Gill"), (2, "Amy Das")], [(1, 1, "pending", 999)]), hidden=False,
             explanation="Only completed orders count; ties on 0 are ordered by name."),
        Test(_orders_setup([(1, "Solo Nair")], [])),
        Test(_orders_setup([(1, "A Shah"), (2, "B Shah")], [(1, 2, "completed", 10), (2, 2, "completed", 10), (3, 1, "completed", 20)])),
        Test(_random_orders(r, 30, 120)),
        Test(_random_orders(r, 200, 2000), weight=2.0),
    )


ORDER_COUNTS = ProblemSpec(
    slug="sql-customer-order-totals",
    title="Customer Order Totals",
    category="sql",
    difficulty="EASY",
    summary="Use a LEFT JOIN so customers without orders are still reported (SQLite).",
    roles=SQL_ROLES,
    competencies=("joins-subqueries", "sql-queries"),
    statement=(
        "Finance needs a list of every customer with the number and value of their completed orders.\n\n"
        "Tables customers(id, name) and orders(id, customer_id, status, amount). For every customer — "
        "including customers with no completed orders — return name, the number of completed orders "
        "and the total amount of those orders (0 when there are none).\n\n"
        "Order by total amount descending, then name ascending, then customer id ascending."
    ),
    input_format=_ORDERS_SCHEMA + "\nEach test creates these tables in a fresh database with its own rows.",
    output_format="name|completed_orders|total_amount per customer.",
    constraints="Up to 200 customers and 2 000 orders",
    languages=SQL_ONLY,
    starter_code={
        "SQLITE": "-- customers(id, name)\n-- orders(id, customer_id, status, amount)\n"
                  "-- Write one SELECT statement.\n\n-- SELECT c.name, ...\n-- FROM customers AS c\n-- ...;\n",
    },
    reference_solutions={"SQLITE": _JOIN_SQL},
    wrong_solutions=(
        ("SQLITE", """SELECT c.name, COUNT(o.id), COALESCE(SUM(o.amount), 0) AS total_amount
FROM customers AS c LEFT JOIN orders AS o ON o.customer_id = c.id
WHERE o.status = 'completed'
GROUP BY c.id, c.name
ORDER BY total_amount DESC, c.name ASC, c.id ASC;""", "Filters in WHERE, which drops customers without completed orders."),
        ("SQLITE", """SELECT c.name, COUNT(*), COALESCE(SUM(o.amount), 0) AS total_amount
FROM customers AS c LEFT JOIN orders AS o ON o.customer_id = c.id AND o.status = 'completed'
GROUP BY c.id, c.name
ORDER BY total_amount DESC, c.name ASC, c.id ASC;""", "COUNT(*) counts 1 for customers with no orders."),
    ),
    tests=_join_tests(),
    oracle=sqlite_oracle(_JOIN_SQL),
    instructions=SQL_NOTE,
    time_limit_seconds=2.0,
    estimated_minutes=15,
)


# ---------------------------------------------------------------------------
# 19. GROUP BY / HAVING — category revenue
# ---------------------------------------------------------------------------

_SALES_SCHEMA = """CREATE TABLE products (
  id INTEGER PRIMARY KEY,
  name TEXT NOT NULL,
  category TEXT NOT NULL
);
CREATE TABLE order_items (
  order_id INTEGER NOT NULL,
  product_id INTEGER NOT NULL REFERENCES products(id),
  quantity INTEGER NOT NULL,
  unit_price INTEGER NOT NULL    -- in rupees, price at the time of sale
);
"""

_REVENUE_SQL = """SELECT p.category,
       SUM(oi.quantity * oi.unit_price) AS revenue,
       SUM(oi.quantity) AS units,
       COUNT(DISTINCT oi.product_id) AS products_sold
FROM order_items AS oi
JOIN products AS p ON p.id = oi.product_id
GROUP BY p.category
HAVING SUM(oi.quantity * oi.unit_price) >= 10000
ORDER BY revenue DESC, p.category ASC;"""


def _sales_setup(products: list[tuple], items: list[tuple]) -> str:
    return _SALES_SCHEMA + _insert("products", products) + _insert("order_items", items)


def _random_sales(r: random.Random, products: int, items: int) -> str:
    categories = ["books", "garden", "kitchen", "toys", "audio", "fitness", "office", "pets"]
    prods = [(i, f"Product {i}", r.choice(categories)) for i in range(1, products + 1)]
    rows = [(r.randint(1, 500), r.randint(1, products), r.randint(1, 5), r.randint(50, 4000)) for _ in range(items)]
    return _sales_setup(prods, rows)


def _revenue_tests() -> tuple[Test, ...]:
    r = random.Random(1919)
    products = [(1, "Desk Lamp", "office"), (2, "Notebook", "office"), (3, "Blender", "kitchen"), (4, "Kettle", "kitchen"), (5, "Puzzle", "toys")]
    items = [(1, 1, 2, 1500), (1, 2, 10, 100), (2, 3, 1, 6000), (3, 4, 2, 2000), (4, 5, 3, 500), (5, 1, 4, 1500)]
    return (
        Test(_sales_setup(products, items), hidden=False,
             explanation="office = 2·1500 + 10·100 + 4·1500 = 10000 (kept); toys = 1500 (below 10000, removed)."),
        Test(_sales_setup([(1, "A", "x"), (2, "B", "y")], [(1, 1, 1, 10000), (1, 2, 2, 5000)]), hidden=False,
             explanation="Equal revenue is ordered by category name."),
        Test(_sales_setup([(1, "Cheap", "misc")], [(1, 1, 1, 9999)])),
        Test(_sales_setup([(1, "P", "solo"), (2, "Unsold", "solo")], [(1, 1, 5, 2000), (2, 1, 1, 1)])),
        Test(_random_sales(r, 40, 300)),
        Test(_random_sales(r, 150, 3000), weight=2.0),
    )


CATEGORY_REVENUE = ProblemSpec(
    slug="sql-category-revenue",
    title="Revenue by Category",
    category="sql",
    difficulty="MEDIUM",
    summary="Aggregate sales with GROUP BY and filter groups with HAVING (SQLite).",
    roles=SQL_ROLES,
    competencies=("sql-queries", "joins-subqueries"),
    statement=(
        "The merchandising team reviews only categories that earned at least 10 000.\n\n"
        "Tables products(id, name, category) and order_items(order_id, product_id, quantity, "
        "unit_price). For each category, compute revenue = sum of quantity × unit_price, units = total "
        "quantity, and products_sold = number of distinct products that appear in order_items. Keep "
        "only categories with revenue of at least 10 000.\n\n"
        "Return category, revenue, units, products_sold ordered by revenue descending, then category ascending."
    ),
    input_format=_SALES_SCHEMA + "\nEach test creates these tables in a fresh database with its own rows.",
    output_format="category|revenue|units|products_sold per category.",
    constraints="Up to 150 products and 3 000 order items",
    languages=SQL_ONLY,
    starter_code={
        "SQLITE": "-- products(id, name, category)\n-- order_items(order_id, product_id, quantity, unit_price)\n"
                  "-- Write one SELECT statement.\n\n-- SELECT p.category, ...\n-- FROM order_items AS oi\n-- ...;\n",
    },
    reference_solutions={"SQLITE": _REVENUE_SQL},
    wrong_solutions=(
        ("SQLITE", _REVENUE_SQL.replace("HAVING SUM(oi.quantity * oi.unit_price) >= 10000\n", ""), "Does not filter categories with HAVING."),
        ("SQLITE", _REVENUE_SQL.replace("COUNT(DISTINCT oi.product_id)", "COUNT(oi.product_id)"), "Counts order lines instead of distinct products."),
        ("SQLITE", _REVENUE_SQL.replace("SUM(oi.quantity * oi.unit_price) AS revenue", "SUM(oi.unit_price) AS revenue")
                                .replace("HAVING SUM(oi.quantity * oi.unit_price)", "HAVING SUM(oi.unit_price)"),
         "Ignores quantity when computing revenue."),
    ),
    tests=_revenue_tests(),
    oracle=sqlite_oracle(_REVENUE_SQL),
    instructions=SQL_NOTE,
    time_limit_seconds=2.0,
    estimated_minutes=15,
)


# ---------------------------------------------------------------------------
# 20. Subqueries — employees above their department average
# ---------------------------------------------------------------------------

_HR_SCHEMA = """CREATE TABLE departments (
  id INTEGER PRIMARY KEY,
  name TEXT NOT NULL
);
CREATE TABLE employees (
  id INTEGER PRIMARY KEY,
  name TEXT NOT NULL,
  department_id INTEGER NOT NULL REFERENCES departments(id),
  salary INTEGER NOT NULL
);
"""

_ABOVE_SQL = """SELECT d.name AS department, e.name AS employee, e.salary
FROM employees AS e
JOIN departments AS d ON d.id = e.department_id
WHERE e.salary > (
  SELECT AVG(e2.salary) FROM employees AS e2 WHERE e2.department_id = e.department_id
)
ORDER BY d.name ASC, e.salary DESC, e.name ASC, e.id ASC;"""


def _hr_setup(departments: list[tuple], employees: list[tuple]) -> str:
    return _HR_SCHEMA + _insert("departments", departments) + _insert("employees", employees)


def _random_hr(r: random.Random, departments: int, employees: int) -> str:
    names = ["Platform", "Payments", "Search", "Mobile", "Data", "Security", "Support", "Growth"][:departments]
    deps = [(i + 1, name) for i, name in enumerate(names)]
    used: set = set()
    rows = [(i, _name(r, used) if len(used) < 110 else f"Employee {i}", r.randint(1, departments), r.randrange(30000, 250000, 500))
            for i in range(1, employees + 1)]
    return _hr_setup(deps, rows)


def _above_tests() -> tuple[Test, ...]:
    r = random.Random(2020)
    return (
        Test(_hr_setup([(1, "Payments"), (2, "Search")],
                       [(1, "Asha Rao", 1, 90000), (2, "Bilal Khan", 1, 60000), (3, "Chitra Iyer", 1, 75000),
                        (4, "Dev Mehta", 2, 50000), (5, "Esha Nair", 2, 50000)]),
             hidden=False, explanation="Payments averages 75 000, so only Asha is above it; in Search both equal the average."),
        Test(_hr_setup([(1, "Data"), (2, "Mobile")],
                       [(1, "Zoya Das", 1, 120000), (2, "Kabir Shah", 1, 40000), (3, "Meera Bose", 2, 70000), (4, "Ishan Gill", 2, 30000)]),
             hidden=False, explanation="Compare with each employee's own department, not the company-wide average."),
        Test(_hr_setup([(1, "Solo")], [(1, "Only Person", 1, 100000)])),
        Test(_hr_setup([(1, "Ops")], [(1, "A Rao", 1, 100), (2, "B Rao", 1, 101), (3, "C Rao", 1, 101)])),
        Test(_random_hr(r, 4, 40)),
        Test(_random_hr(r, 8, 600), weight=2.0),
    )


ABOVE_AVERAGE = ProblemSpec(
    slug="sql-above-department-average",
    title="Above the Department Average",
    category="sql",
    difficulty="MEDIUM",
    summary="Compare each employee with their own department's average using a subquery (SQLite).",
    roles=SQL_ROLES,
    competencies=("joins-subqueries", "sql-queries"),
    statement=(
        "HR is reviewing pay bands: who earns strictly more than the average salary of their own department?\n\n"
        "Tables departments(id, name) and employees(id, name, department_id, salary). Return the "
        "department name, employee name and salary of every employee whose salary is strictly greater "
        "than the average salary of the employees in the same department.\n\n"
        "Order by department name ascending, salary descending, employee name ascending, then employee id ascending."
    ),
    input_format=_HR_SCHEMA + "\nEach test creates these tables in a fresh database with its own rows.",
    output_format="department|employee|salary per row.",
    constraints="Up to 8 departments and 600 employees",
    languages=SQL_ONLY,
    starter_code={
        "SQLITE": "-- departments(id, name)\n-- employees(id, name, department_id, salary)\n"
                  "-- Write one SELECT statement.\n\n-- SELECT d.name AS department, e.name AS employee, e.salary\n-- FROM employees AS e\n-- ...;\n",
    },
    reference_solutions={"SQLITE": _ABOVE_SQL},
    wrong_solutions=(
        ("SQLITE", _ABOVE_SQL.replace(" WHERE e2.department_id = e.department_id", ""), "Compares with the company-wide average."),
        ("SQLITE", _ABOVE_SQL.replace("WHERE e.salary > (", "WHERE e.salary >= ("), "Includes employees exactly at the average."),
    ),
    tests=_above_tests(),
    oracle=sqlite_oracle(_ABOVE_SQL),
    instructions=SQL_NOTE,
    time_limit_seconds=2.0,
    estimated_minutes=15,
)


PROBLEMS = (ACTIVE_CUSTOMERS, ORDER_COUNTS, CATEGORY_REVENUE, ABOVE_AVERAGE)
