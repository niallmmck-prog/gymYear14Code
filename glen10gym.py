import tkinter as tk
import base64
import io
from tkinter import ttk, messagebox, scrolledtext
import sqlite3
import re
import os
from datetime import datetime, date, timedelta

try:
    from PIL import Image, ImageTk
    PIL_AVAILABLE = True
except ImportError:
    PIL_AVAILABLE = False
    print("Note: Pillow not installed. Logo will not display.")
    print("Install with: pip install Pillow")

try:
    from tkcalendar import DateEntry
except ImportError:
    DateEntry = None
    print("Note: tkcalendar not installed. Some date features may not work.")
    print("Install with: pip install tkcalendar")

# Glen10 Gym logo embedded as base64 (no external file needed)
LOGO_B64 = """/9j/4AAQSkZJRgABAQAAAQABAAD/2wBDAAUDBAQEAwUEBAQFBQUGBwwIBwcHBw8LCwkMEQ8SEhEP
ERETFhwXExQaFRERGCEYGh0dHx8fExciJCIeJBweHx7/2wBDAQUFBQcGBw4ICA4eFBEUHh4eHh4e
Hh4eHh4eHh4eHh4eHh4eHh4eHh4eHh4eHh4eHh4eHh4eHh4eHh4eHh4eHh7/wAARCAEAAQADASIA
AhEBAxEB/8QAHAABAAICAwEAAAAAAAAAAAAAAAYHBQgBAgQD/8QAOhAAAQMDAQUFBQcDBQEAAAAA
AQIDBAAFEQYHEiExQRMiUWFxFDKBkaEVI0JSYnLBM4KSorHRJP/EABoBAQADAQEBAAAAAAAAAAAA
AAACAwQBBQb/xAAjEQEAAgICAgEFAQAAAAAAAAAAAQIDEQQhMUESEyJRYXEU/9oADAMBAAIRAxEA
PwC50pSgUpSgUpSgUpSgUpSgUpSgUpSgUpSgUpSgUpSgUpSgUpSgUpSgUpSgUpSgUpSgUpSgUpSg
UpSgUpSgUpSgUpSgUpSgUpSgUpSgUpSgUpSgUpSgUpSgUpSgUpSgUpSgUpSgUpSgUpSgUpSgUpSg
UpSgUpSgUpSgUpSgUpSgUpSgUpSg"""

####################################################################################
# DATABASE SETUP - Glen10 Gym (with proper primary key mapping)
####################################################################################

# CRITICAL FIX: Map of table names to their actual primary key column names.
# Without this, soft_delete_record and restore_record would build invalid SQL like
# "WHERE customers_id = ?" instead of "WHERE customer_id = ?".
TABLE_PK_MAP = {
    'staff': 'staff_id',
    'customers': 'customer_id',
    'classes': 'class_id',
    'bookings': 'booking_id',
    'invoices': 'invoice_id',
}


def init_database():
    """Initialize all database tables for Glen10 Gym with audit log and soft delete"""
    connection = sqlite3.connect("glen10_gym.db")
    cursor = connection.cursor()

    # Role-based permissions table
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS permissions (
            permission_id INTEGER PRIMARY KEY AUTOINCREMENT,
            job_title TEXT NOT NULL,
            module TEXT NOT NULL,
            can_view BOOLEAN DEFAULT 1,
            can_add BOOLEAN DEFAULT 0,
            can_edit BOOLEAN DEFAULT 0,
            can_delete BOOLEAN DEFAULT 0
        )
    """)

    # Audit Log Table
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS audit_log (
            log_id INTEGER PRIMARY KEY AUTOINCREMENT,
            staff_id INTEGER NOT NULL,
            staff_name TEXT NOT NULL,
            action TEXT NOT NULL,
            table_name TEXT NOT NULL,
            record_id INTEGER NOT NULL,
            old_value TEXT,
            new_value TEXT,
            timestamp DATETIME DEFAULT CURRENT_TIMESTAMP,
            ip_address TEXT,
            FOREIGN KEY (staff_id) REFERENCES staff(staff_id)
        )
    """)

    # Staff Table with soft delete
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS staff (
            staff_id INTEGER PRIMARY KEY AUTOINCREMENT,
            first_name TEXT NOT NULL,
            last_name TEXT NOT NULL,
            username TEXT UNIQUE NOT NULL,
            password TEXT NOT NULL,
            job_title TEXT NOT NULL,
            mobile_number TEXT NOT NULL,
            email TEXT NOT NULL,
            address TEXT,
            hire_date DATE,
            salary DECIMAL(10,2),
            department TEXT,
            status TEXT DEFAULT 'Active',
            is_deleted BOOLEAN DEFAULT 0,
            deleted_at DATETIME,
            deleted_by INTEGER
        )
    """)

    # Class Table with soft delete
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS classes (
            class_id INTEGER PRIMARY KEY AUTOINCREMENT,
            class_name TEXT NOT NULL,
            description TEXT,
            instructor_id INTEGER,
            duration_minutes INTEGER NOT NULL,
            max_capacity INTEGER NOT NULL,
            current_enrollment INTEGER DEFAULT 0,
            class_time TIME NOT NULL,
            class_day TEXT NOT NULL,
            room_number TEXT,
            difficulty_level TEXT,
            equipment_required TEXT,
            is_active BOOLEAN DEFAULT 1,
            is_deleted BOOLEAN DEFAULT 0,
            deleted_at DATETIME,
            deleted_by INTEGER,
            FOREIGN KEY (instructor_id) REFERENCES staff(staff_id)
        )
    """)

    # Customer Table with soft delete
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS customers (
            customer_id INTEGER PRIMARY KEY AUTOINCREMENT,
            first_name TEXT NOT NULL,
            last_name TEXT NOT NULL,
            mobile_number TEXT NOT NULL,
            email TEXT NOT NULL,
            date_of_birth DATE NOT NULL,
            address TEXT,
            postcode TEXT,
            join_date DATE DEFAULT CURRENT_DATE,
            membership_type TEXT NOT NULL,
            membership_status TEXT DEFAULT 'Active',
            emergency_contact TEXT,
            medical_notes TEXT,
            is_deleted BOOLEAN DEFAULT 0,
            deleted_at DATETIME,
            deleted_by INTEGER
        )
    """)

    # Invoice Table with soft delete
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS invoices (
            invoice_id INTEGER PRIMARY KEY AUTOINCREMENT,
            customer_id INTEGER NOT NULL,
            invoice_date DATE DEFAULT CURRENT_DATE,
            due_date DATE,
            amount DECIMAL(10,2) NOT NULL,
            payment_status TEXT DEFAULT 'Pending',
            payment_method TEXT,
            payment_date DATE,
            description TEXT,
            is_deleted BOOLEAN DEFAULT 0,
            deleted_at DATETIME,
            deleted_by INTEGER,
            FOREIGN KEY (customer_id) REFERENCES customers(customer_id)
        )
    """)

    # Booking Table with soft delete
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS bookings (
            booking_id INTEGER PRIMARY KEY AUTOINCREMENT,
            customer_id INTEGER NOT NULL,
            class_id INTEGER NOT NULL,
            booking_date TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            cost DECIMAL(8,2) NOT NULL,
            paid BOOLEAN DEFAULT 0,
            payment_date DATE,
            notes TEXT,
            attendance_status TEXT DEFAULT 'Booked',
            is_deleted BOOLEAN DEFAULT 0,
            deleted_at DATETIME,
            deleted_by INTEGER,
            FOREIGN KEY (customer_id) REFERENCES customers(customer_id),
            FOREIGN KEY (class_id) REFERENCES classes(class_id)
        )
    """)

    # Insert sample staff if empty
    cursor.execute("SELECT COUNT(*) FROM staff")
    if cursor.fetchone()[0] == 0:
        sample_staff = [
            ('Nathan', 'McKee', 'nmck', '123', 'Manager', '07700123456',
             'nathan@glen10gym.com', '123 Main St', '2025-01-15', 45000, 'Management', 'Active'),
            ('Sarah', 'Johnson', 'sarah', 'pass123', 'Personal Trainer', '07700234567',
             'sarah@glen10gym.com', '456 Oak Ave', '2025-03-10', 35000, 'Training', 'Active'),
            ('Mike', 'Wilson', 'mike', 'trainer1', 'Fitness Instructor', '07700345678',
             'mike@glen10gym.com', '789 Pine Rd', '2025-06-20', 28000, 'Training', 'Active'),
            ('Mitchell', 'Brown', 'mitch', '789', 'Personal Trainer', '07700456789',
             'mitch@glen10gym.com', '321 Elm St', '2025-02-01', 32000, 'Training', 'Active'),
        ]
        cursor.executemany("""
            INSERT INTO staff (first_name, last_name, username, password, job_title,
                               mobile_number, email, address, hire_date, salary, department, status)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, sample_staff)

    # Insert default permissions
    cursor.execute("SELECT COUNT(*) FROM permissions")
    if cursor.fetchone()[0] == 0:
        default_permissions = [
            # Manager - Full access
            ('Manager', 'dashboard', 1, 1, 1, 1),
            ('Manager', 'staff', 1, 1, 1, 1),
            ('Manager', 'customers', 1, 1, 1, 1),
            ('Manager', 'classes', 1, 1, 1, 1),
            ('Manager', 'bookings', 1, 1, 1, 1),
            ('Manager', 'invoices', 1, 1, 1, 1),
            ('Manager', 'reports', 1, 1, 1, 1),
            ('Manager', 'audit_log', 1, 1, 1, 1),
            ('Manager', 'recycle_bin', 1, 1, 1, 1),

            # Personal Trainer - Limited access
            ('Personal Trainer', 'dashboard', 1, 0, 0, 0),
            ('Personal Trainer', 'staff', 0, 0, 0, 0),
            ('Personal Trainer', 'customers', 1, 0, 0, 0),
            ('Personal Trainer', 'classes', 1, 1, 1, 0),
            ('Personal Trainer', 'bookings', 1, 1, 1, 0),
            ('Personal Trainer', 'invoices', 0, 0, 0, 0),
            ('Personal Trainer', 'reports', 1, 0, 0, 0),
            ('Personal Trainer', 'audit_log', 0, 0, 0, 0),
            ('Personal Trainer', 'recycle_bin', 0, 0, 0, 0),

            # Fitness Instructor - Limited access
            ('Fitness Instructor', 'dashboard', 1, 0, 0, 0),
            ('Fitness Instructor', 'staff', 0, 0, 0, 0),
            ('Fitness Instructor', 'customers', 1, 0, 0, 0),
            ('Fitness Instructor', 'classes', 1, 1, 1, 0),
            ('Fitness Instructor', 'bookings', 1, 1, 1, 0),
            ('Fitness Instructor', 'invoices', 0, 0, 0, 0),
            ('Fitness Instructor', 'reports', 1, 0, 0, 0),
            ('Fitness Instructor', 'audit_log', 0, 0, 0, 0),
            ('Fitness Instructor', 'recycle_bin', 0, 0, 0, 0),

            # Admin - Full access
            ('Admin', 'dashboard', 1, 1, 1, 1),
            ('Admin', 'staff', 1, 1, 1, 1),
            ('Admin', 'customers', 1, 1, 1, 1),
            ('Admin', 'classes', 1, 1, 1, 1),
            ('Admin', 'bookings', 1, 1, 1, 1),
            ('Admin', 'invoices', 1, 1, 1, 1),
            ('Admin', 'reports', 1, 1, 1, 1),
            ('Admin', 'audit_log', 1, 1, 1, 1),
            ('Admin', 'recycle_bin', 1, 1, 1, 1),

            # Receptionist - Moderate access
            ('Receptionist', 'dashboard', 1, 0, 0, 0),
            ('Receptionist', 'staff', 0, 0, 0, 0),
            ('Receptionist', 'customers', 1, 1, 1, 0),
            ('Receptionist', 'classes', 1, 0, 0, 0),
            ('Receptionist', 'bookings', 1, 1, 1, 0),
            ('Receptionist', 'invoices', 1, 1, 1, 0),
            ('Receptionist', 'reports', 1, 0, 0, 0),
            ('Receptionist', 'audit_log', 0, 0, 0, 0),
            ('Receptionist', 'recycle_bin', 0, 0, 0, 0),

            # Cleaner - View only
            ('Cleaner', 'dashboard', 1, 0, 0, 0),
            ('Cleaner', 'staff', 0, 0, 0, 0),
            ('Cleaner', 'customers', 0, 0, 0, 0),
            ('Cleaner', 'classes', 1, 0, 0, 0),
            ('Cleaner', 'bookings', 0, 0, 0, 0),
            ('Cleaner', 'invoices', 0, 0, 0, 0),
            ('Cleaner', 'reports', 0, 0, 0, 0),
            ('Cleaner', 'audit_log', 0, 0, 0, 0),
            ('Cleaner', 'recycle_bin', 0, 0, 0, 0),
        ]

        cursor.executemany("""
            INSERT INTO permissions (job_title, module, can_view, can_add, can_edit, can_delete)
            VALUES (?, ?, ?, ?, ?, ?)
        """, default_permissions)

    # Insert sample classes if empty
    cursor.execute("SELECT COUNT(*) FROM classes")
    if cursor.fetchone()[0] == 0:
        sample_classes = [
            ('HIIT Burn', 'High Intensity Interval Training', 2, 60, 20, 0,
             '18:00', 'Monday', 'Studio A', 'Advanced', 'Mat, Weights', 1),
            ('Yoga Flow', 'Vinyasa Yoga for all levels', 3, 60, 15, 0,
             '09:00', 'Wednesday', 'Studio B', 'Beginner', 'Yoga Mat', 1),
            ('Spin Class', 'Indoor Cycling', 2, 45, 25, 0,
             '19:30', 'Tuesday', 'Spin Room', 'Intermediate', 'Spin Bike', 1),
            ('Strength Training', 'Weight lifting fundamentals', 3, 90, 10, 0,
             '17:00', 'Thursday', 'Weight Room', 'All Levels', 'Various weights', 1),
        ]
        cursor.executemany("""
            INSERT INTO classes (class_name, description, instructor_id, duration_minutes,
                               max_capacity, current_enrollment, class_time, class_day,
                               room_number, difficulty_level, equipment_required, is_active)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, sample_classes)

    connection.commit()
    connection.close()


####################################################################################
# PERMISSION FUNCTIONS
####################################################################################

def get_user_permissions(job_title):
    """Get permissions for a specific job title"""
    try:
        connection = sqlite3.connect("glen10_gym.db")
        cursor = connection.cursor()

        cursor.execute("""
            SELECT module, can_view, can_add, can_edit, can_delete
            FROM permissions WHERE job_title = ?
        """, (job_title,))

        permissions = {}
        for module, can_view, can_add, can_edit, can_delete in cursor.fetchall():
            permissions[module] = {
                'view': bool(can_view),
                'add': bool(can_add),
                'edit': bool(can_edit),
                'delete': bool(can_delete)
            }

        connection.close()
        return permissions
    except Exception as e:
        print(f"Error getting permissions: {e}")
        return {}


def check_permission(job_title, module, action):
    """Check if user has permission for specific action on module"""
    permissions = get_user_permissions(job_title)
    if module not in permissions:
        return False

    if action == 'view':
        return permissions[module]['view']
    elif action == 'add':
        return permissions[module]['add']
    elif action == 'edit':
        return permissions[module]['edit']
    elif action == 'delete':
        return permissions[module]['delete']

    return False


####################################################################################
# AUDIT LOG FUNCTIONS
####################################################################################

def log_audit_action(staff_id, staff_name, action, table_name, record_id,
                     old_value=None, new_value=None):
    """Log an action to the audit log table"""
    try:
        connection = sqlite3.connect("glen10_gym.db")
        cursor = connection.cursor()

        cursor.execute("""
            INSERT INTO audit_log (staff_id, staff_name, action, table_name,
                                   record_id, old_value, new_value)
            VALUES (?, ?, ?, ?, ?, ?, ?)
        """, (staff_id, staff_name, action, table_name, record_id, old_value, new_value))

        connection.commit()
        connection.close()
        return True
    except Exception as e:
        print(f"Error logging audit action: {e}")
        return False


def get_audit_logs(limit=100):
    """Retrieve audit logs from database"""
    try:
        connection = sqlite3.connect("glen10_gym.db")
        cursor = connection.cursor()

        cursor.execute("""
            SELECT log_id, staff_name, action, table_name, record_id,
                   timestamp, old_value, new_value
            FROM audit_log
            ORDER BY timestamp DESC
            LIMIT ?
        """, (limit,))

        logs = cursor.fetchall()
        connection.close()
        return logs
    except Exception as e:
        print(f"Error retrieving audit logs: {e}")
        return []


####################################################################################
# SOFT DELETE FUNCTIONS  (FIXED to use proper PK column names)
####################################################################################

def soft_delete_record(staff_id, staff_name, table_name, record_id):
    """Soft delete a record by marking it as deleted"""
    try:
        # FIX: Look up the actual primary key column name for this table
        pk_column = TABLE_PK_MAP.get(table_name)
        if pk_column is None:
            print(f"Unknown table for soft delete: {table_name}")
            return False

        connection = sqlite3.connect("glen10_gym.db")
        cursor = connection.cursor()

        cursor.execute(f"""
            UPDATE {table_name}
            SET is_deleted = 1, deleted_at = CURRENT_TIMESTAMP, deleted_by = ?
            WHERE {pk_column} = ?
        """, (staff_id, record_id))

        connection.commit()
        connection.close()

        log_audit_action(staff_id, staff_name, 'SOFT DELETE', table_name, record_id)
        return True
    except Exception as e:
        print(f"Error in soft delete: {e}")
        return False


def restore_record(staff_id, staff_name, table_name, record_id):
    """Restore a soft-deleted record"""
    try:
        # FIX: Look up the actual primary key column name for this table
        pk_column = TABLE_PK_MAP.get(table_name)
        if pk_column is None:
            print(f"Unknown table for restore: {table_name}")
            return False

        connection = sqlite3.connect("glen10_gym.db")
        cursor = connection.cursor()

        cursor.execute(f"""
            UPDATE {table_name}
            SET is_deleted = 0, deleted_at = NULL, deleted_by = NULL
            WHERE {pk_column} = ?
        """, (record_id,))

        connection.commit()
        connection.close()

        log_audit_action(staff_id, staff_name, 'RESTORE', table_name, record_id)
        return True
    except Exception as e:
        print(f"Error restoring record: {e}")
        return False


def get_deleted_records(table_name):
    """Get all deleted records from a table"""
    try:
        connection = sqlite3.connect("glen10_gym.db")
        cursor = connection.cursor()

        cursor.execute(f"""
            SELECT * FROM {table_name}
            WHERE is_deleted = 1
            ORDER BY deleted_at DESC
        """)

        records = cursor.fetchall()
        connection.close()
        return records
    except Exception as e:
        print(f"Error getting deleted records: {e}")
        return []


####################################################################################
# DASHBOARD STATISTICS
####################################################################################

def get_dashboard_stats():
    """Get statistics for the dashboard"""
    connection = sqlite3.connect("glen10_gym.db")
    cursor = connection.cursor()

    stats = {}

    cursor.execute("""
        SELECT COUNT(*) FROM customers
        WHERE membership_status = 'Active' AND is_deleted = 0
    """)
    stats['total_members'] = cursor.fetchone()[0]

    cursor.execute("""
        SELECT COUNT(*) FROM staff
        WHERE status = 'Active' AND is_deleted = 0
    """)
    stats['total_staff'] = cursor.fetchone()[0]

    today = datetime.now().strftime('%A')
    cursor.execute("""
        SELECT COUNT(*) FROM classes
        WHERE class_day = ? AND is_active = 1 AND is_deleted = 0
    """, (today,))
    stats['classes_today'] = cursor.fetchone()[0]

    cursor.execute("""
        SELECT
            SUM(CASE WHEN membership_status = 'Active' AND is_deleted = 0 THEN 1 ELSE 0 END) as active,
            SUM(CASE WHEN (membership_status != 'Active' AND is_deleted = 0) THEN 1 ELSE 0 END) as inactive
        FROM customers
    """)
    active_inactive = cursor.fetchone()
    stats['active_members'] = active_inactive[0] or 0
    stats['inactive_members'] = active_inactive[1] or 0

    cursor.execute("""
        SELECT COUNT(*) FROM bookings
        WHERE DATE(booking_date) = DATE('now') AND is_deleted = 0
    """)
    stats['today_bookings'] = cursor.fetchone()[0]

    cursor.execute("""
        SELECT COALESCE(SUM(amount), 0)
        FROM invoices
        WHERE payment_status = 'Paid'
          AND strftime('%Y-%m', invoice_date) = strftime('%Y-%m', 'now')
          AND is_deleted = 0
    """)
    stats['monthly_revenue'] = cursor.fetchone()[0]

    connection.close()
    return stats


####################################################################################
# LOGIN SCREEN
####################################################################################

class LoginScreen:
    def __init__(self, root):
        self.root = root
        self.root.title("Glen10 Gym - Login")
        self.root.geometry("900x600")
        self.root.configure(bg='#0f1c2e')

        self.root.update_idletasks()
        width = self.root.winfo_width()
        height = self.root.winfo_height()
        x = (self.root.winfo_screenwidth() // 2) - (width // 2)
        y = (self.root.winfo_screenheight() // 2) - (height // 2)
        self.root.geometry(f'{width}x{height}+{x}+{y}')

        self.root.resizable(False, False)

        init_database()

        # Track login button so we can update it during auth
        self.login_btn = None
        self.create_widgets()

    def create_widgets(self):
        main_frame = tk.Frame(self.root, bg='#0f1c2e')
        main_frame.pack(expand=True, fill='both')

        # Left side - branding
        left_frame = tk.Frame(main_frame, bg='#1a2b3e', width=400)
        left_frame.pack(side='left', fill='both', expand=True)
        left_frame.pack_propagate(False)

        brand_container = tk.Frame(left_frame, bg='#1a2b3e')
        brand_container.pack(expand=True, fill='both', padx=40, pady=60)

        if PIL_AVAILABLE:
            try:
                logo_img = Image.open(io.BytesIO(base64.b64decode(LOGO_B64)))
                logo_img = logo_img.resize((280, 280), Image.LANCZOS)
                self._login_logo = ImageTk.PhotoImage(logo_img)
                tk.Label(brand_container, image=self._login_logo,
                         bg='#1a2b3e').pack(pady=(0, 10))
            except Exception as e:
                print(f"Could not load logo: {e}")
                tk.Label(brand_container, text="GLEN10", font=('Arial Black', 40),
                         bg='#1a2b3e', fg='white').pack(pady=(0, 10))
        else:
            tk.Label(brand_container, text="GLEN10", font=('Arial Black', 40),
                     bg='#1a2b3e', fg='white').pack(pady=(0, 10))

        tk.Label(brand_container, text="FITNESS MANAGEMENT SYSTEM",
                 font=('Arial', 14), bg='#1a2b3e', fg='#3498db').pack(pady=(0, 5))

        sep = tk.Frame(brand_container, height=2, bg='#3498db', width=150)
        sep.pack(pady=20)

        features = [
            "* Staff & Member Management",
            "* Class Scheduling & Booking",
            "* Invoice & Payment Tracking",
            "* Real-time Reports Dashboard",
            "* Audit Log System",
            "* Soft Delete Protection",
        ]
        for feature in features:
            tk.Label(brand_container, text=feature, font=('Arial', 12),
                     bg='#1a2b3e', fg='#95a5a6', anchor='w').pack(fill='x', pady=3)

        # Right side - form
        right_frame = tk.Frame(main_frame, bg='#1a2b3e', width=500)
        right_frame.pack(side='right', fill='both', expand=True)
        right_frame.pack_propagate(False)

        form_container = tk.Frame(right_frame, bg='#1a2b3e')
        form_container.pack(expand=True, fill='both', padx=60, pady=80)

        tk.Label(form_container, text="Welcome Back", font=('Arial Black', 28),
                 bg='#1a2b3e', fg='white').pack(anchor='w', pady=(0, 5))
        tk.Label(form_container, text="Sign in to continue to your dashboard",
                 font=('Arial', 12), bg='#1a2b3e', fg='#95a5a6').pack(anchor='w', pady=(0, 40))

        # Username
        username_frame = tk.Frame(form_container, bg='#1a2b3e')
        username_frame.pack(fill='x', pady=(0, 20))
        tk.Label(username_frame, text="USERNAME", font=('Arial', 10, 'bold'),
                 bg='#1a2b3e', fg='#3498db').pack(anchor='w', pady=(0, 5))
        self.username_entry = tk.Entry(username_frame, font=('Arial', 12),
                                       bg='#2c3e50', fg='white', insertbackground='white',
                                       relief='flat', bd=2, width=30)
        self.username_entry.pack(fill='x', pady=2)
        tk.Frame(username_frame, height=2, bg='#3498db').pack(fill='x')

        # Password
        password_frame = tk.Frame(form_container, bg='#1a2b3e')
        password_frame.pack(fill='x', pady=(0, 10))
        tk.Label(password_frame, text="PASSWORD", font=('Arial', 10, 'bold'),
                 bg='#1a2b3e', fg='#3498db').pack(anchor='w', pady=(0, 5))
        self.password_entry = tk.Entry(password_frame, font=('Arial', 12),
                                       bg='#2c3e50', fg='white', insertbackground='white',
                                       relief='flat', bd=2, width=30, show="*")
        self.password_entry.pack(fill='x', pady=2)
        tk.Frame(password_frame, height=2, bg='#3498db').pack(fill='x')

        self.show_password_var = tk.BooleanVar()
        tk.Checkbutton(password_frame, text="Show Password",
                       variable=self.show_password_var,
                       bg='#1a2b3e', fg='#95a5a6', selectcolor='#1a2b3e',
                       activebackground='#1a2b3e', activeforeground='#95a5a6',
                       command=self.toggle_password_visibility,
                       font=('Arial', 9)).pack(anchor='w', pady=(5, 0))

        self.login_btn = tk.Button(form_container, text="SIGN IN",
                                   font=('Arial', 12, 'bold'),
                                   bg='#3498db', fg='white',
                                   activebackground='#2980b9',
                                   activeforeground='white',
                                   cursor='hand2', height=2, relief='flat',
                                   command=self.authenticate)
        self.login_btn.pack(fill='x', pady=(40, 15))

        demo_frame = tk.Frame(form_container, bg='#1a2b3e')
        demo_frame.pack(fill='x', pady=(10, 0))
        tk.Label(demo_frame, text="Demo Credentials:", font=('Arial', 9, 'bold'),
                 bg='#1a2b3e', fg='#3498db').pack(anchor='w')
        tk.Label(demo_frame, text="Username: nmck | Password: 123",
                 font=('Arial', 9), bg='#1a2b3e', fg='#e74c3c').pack(anchor='w', pady=(2, 0))

        self.error_label = tk.Label(form_container, text="", font=('Arial', 10),
                                    bg='#1a2b3e', fg='#e74c3c')
        self.error_label.pack(pady=(10, 0))

        self.root.bind('<Return>', lambda e: self.authenticate())
        self.username_entry.focus_set()

    def toggle_password_visibility(self):
        if self.show_password_var.get():
            self.password_entry.config(show="")
        else:
            self.password_entry.config(show="*")

    def authenticate(self):
        username = self.username_entry.get().strip()
        password = self.password_entry.get().strip()

        if not username or not password:
            self.error_label.config(text="Please enter both username and password", fg='#e74c3c')
            return

        try:
            connection = sqlite3.connect("glen10_gym.db")
            cursor = connection.cursor()
            cursor.execute("""
                SELECT staff_id, first_name, last_name, username, job_title FROM staff
                WHERE username = ? AND password = ? AND status = 'Active' AND is_deleted = 0
            """, (username, password))
            user = cursor.fetchone()
            connection.close()

            if user:
                self.error_label.config(text="Login successful! Loading system...", fg='#2ecc71')
                self.root.update()

                # FIX: Update the actual login button (we kept a reference to it)
                if self.login_btn is not None:
                    self.login_btn.config(text="LOADING...", bg='#2ecc71', state='disabled')

                self.user_data = {
                    'staff_id': user[0],
                    'first_name': user[1],
                    'last_name': user[2],
                    'username': user[3],
                    'job_title': user[4],
                    'full_name': f"{user[1]} {user[2]}",
                }

                permissions = get_user_permissions(user[4])
                self.user_data['permissions'] = permissions

                self.root.after(800, self.launch_main_app)
            else:
                self.error_label.config(text="Invalid username or password", fg='#e74c3c')
                self.shake_login_form()
                self.password_entry.delete(0, tk.END)

        except Exception as e:
            self.error_label.config(text="Database error. Please try again.", fg='#e74c3c')
            print(f"Login error: {e}")

    def shake_login_form(self):
        x = self.root.winfo_x()
        y = self.root.winfo_y()
        for _ in range(0, 3):
            for offset in [10, -10, 10, -10, 0]:
                self.root.geometry(f'+{x + offset}+{y}')
                self.root.update()
                self.root.after(30)

    def launch_main_app(self):
        self.root.destroy()
        main_app = Glen10GymApp(self.user_data)
        main_app.run()


####################################################################################
# AUDIT LOG VIEWER
####################################################################################

class AuditLogViewer:
    def __init__(self, root, return_callback, user_data):
        self.root = root
        self.return_callback = return_callback
        self.user_data = user_data

        for widget in self.root.winfo_children():
            widget.destroy()

        header_frame = tk.Frame(self.root, bg='#1a2b3e', height=80)
        header_frame.pack(fill='x')
        header_frame.pack_propagate(False)

        tk.Label(header_frame, text="Audit Log System", font=('Arial Black', 20),
                 bg='#1a2b3e', fg='white').pack(side='left', padx=20)

        tk.Button(header_frame, text="< Back to Dashboard", font=('Arial', 10),
                  bg='#3498db', fg='white', relief='flat',
                  command=self.return_to_dashboard, padx=15).pack(side='right', padx=20)

        control_frame = tk.Frame(self.root, bg='#0f1c2e', padx=20, pady=10)
        control_frame.pack(fill='x')

        tk.Label(control_frame, text="Filter by Action:",
                 bg='#0f1c2e', fg='white').pack(side='left', padx=5)
        self.action_filter = ttk.Combobox(
            control_frame,
            values=['All', 'INSERT', 'UPDATE', 'DELETE', 'SOFT DELETE', 'RESTORE'])
        self.action_filter.pack(side='left', padx=5)
        self.action_filter.set('All')

        tk.Label(control_frame, text="Filter by Table:",
                 bg='#0f1c2e', fg='white').pack(side='left', padx=(20, 5))
        self.table_filter = ttk.Combobox(
            control_frame,
            values=['All', 'staff', 'customers', 'classes', 'bookings', 'invoices'])
        self.table_filter.pack(side='left', padx=5)
        self.table_filter.set('All')

        tk.Button(control_frame, text="Apply Filters", bg='#3498db', fg='white',
                  command=self.apply_filters, relief='flat').pack(side='left', padx=10)
        tk.Button(control_frame, text="Clear Logs", bg='#e74c3c', fg='white',
                  command=self.clear_logs, relief='flat').pack(side='left', padx=5)
        tk.Button(control_frame, text="Export to CSV", bg='#27ae60', fg='white',
                  command=self.export_logs, relief='flat').pack(side='left', padx=5)

        table_frame = tk.Frame(self.root, bg='#1a2b3e')
        table_frame.pack(expand=True, fill='both', padx=20, pady=10)

        columns = ('ID', 'Timestamp', 'User', 'Action', 'Table', 'Record ID', 'Details')
        self.tree = ttk.Treeview(table_frame, columns=columns, show='headings', height=20)

        style = ttk.Style()
        style.theme_use('clam')
        style.configure("Treeview", background="#2c3e50", foreground="white",
                        fieldbackground="#2c3e50", borderwidth=0)
        style.configure("Treeview.Heading", background="#34495e",
                        foreground="white", relief="flat")
        style.map("Treeview", background=[('selected', '#3498db')])

        for col in columns:
            self.tree.heading(col, text=col)
            self.tree.column(col, width=120)

        scrollbar = ttk.Scrollbar(table_frame, orient=tk.VERTICAL, command=self.tree.yview)
        self.tree.configure(yscrollcommand=scrollbar.set)
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
        self.tree.pack(side=tk.LEFT, expand=True, fill='both')

        self.load_audit_logs()

    def load_audit_logs(self, action_filter='All', table_filter='All'):
        for item in self.tree.get_children():
            self.tree.delete(item)

        logs = get_audit_logs(limit=200)

        for log in logs:
            log_id, staff_name, action, table_name, record_id, timestamp, old_value, new_value = log

            if action_filter != 'All' and action != action_filter:
                continue
            if table_filter != 'All' and table_name != table_filter:
                continue

            details = ""
            if old_value and new_value:
                details = f"Changed: {str(old_value)[:50]} -> {str(new_value)[:50]}"
            elif new_value:
                details = f"New: {str(new_value)[:50]}"
            elif old_value:
                details = f"Removed: {str(old_value)[:50]}"

            try:
                timestamp_str = datetime.strptime(timestamp,
                                                  '%Y-%m-%d %H:%M:%S').strftime('%d/%m %H:%M')
            except Exception:
                timestamp_str = str(timestamp)

            self.tree.insert('', tk.END, values=(
                log_id, timestamp_str, staff_name, action, table_name, record_id, details))

    def apply_filters(self):
        self.load_audit_logs(self.action_filter.get(), self.table_filter.get())

    def clear_logs(self):
        if messagebox.askyesno("Confirm Clear",
                               "Are you sure you want to clear all audit logs?"):
            try:
                connection = sqlite3.connect("glen10_gym.db")
                cursor = connection.cursor()
                cursor.execute("DELETE FROM audit_log")
                connection.commit()
                connection.close()
                messagebox.showinfo("Success", "Audit logs cleared successfully")
                self.load_audit_logs()
            except Exception as e:
                messagebox.showerror("Error", f"Failed to clear logs: {str(e)}")

    def export_logs(self):
        try:
            import csv
            logs = get_audit_logs(limit=1000)
            filename = f"audit_log_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv"

            with open(filename, 'w', newline='') as csvfile:
                writer = csv.writer(csvfile)
                writer.writerow(['ID', 'Staff Name', 'Action', 'Table',
                                 'Record ID', 'Timestamp', 'Old Value', 'New Value'])
                for log in logs:
                    writer.writerow(log)

            messagebox.showinfo("Export Successful",
                                f"Audit logs exported to {filename}")
        except Exception as e:
            messagebox.showerror("Export Error", f"Failed to export logs: {str(e)}")

    def return_to_dashboard(self):
        for widget in self.root.winfo_children():
            widget.destroy()
        self.return_callback()


####################################################################################
# RECYCLE BIN  (FIXED: invoice amount index, deleted_at/by detection)
####################################################################################

class RecycleBin:
    def __init__(self, root, return_callback, user_data):
        self.root = root
        self.return_callback = return_callback
        self.user_data = user_data

        for widget in self.root.winfo_children():
            widget.destroy()

        header_frame = tk.Frame(self.root, bg='#1a2b3e', height=80)
        header_frame.pack(fill='x')
        header_frame.pack_propagate(False)

        tk.Label(header_frame, text="Recycle Bin", font=('Arial Black', 20),
                 bg='#1a2b3e', fg='white').pack(side='left', padx=20)

        tk.Button(header_frame, text="< Back to Dashboard", font=('Arial', 10),
                  bg='#3498db', fg='white', relief='flat',
                  command=self.return_to_dashboard, padx=15).pack(side='right', padx=20)

        control_frame = tk.Frame(self.root, bg='#0f1c2e', padx=20, pady=10)
        control_frame.pack(fill='x')

        tk.Label(control_frame, text="Filter by Table:",
                 bg='#0f1c2e', fg='white').pack(side='left', padx=5)
        self.table_filter = ttk.Combobox(
            control_frame,
            values=['All', 'staff', 'customers', 'classes', 'bookings', 'invoices'])
        self.table_filter.pack(side='left', padx=5)
        self.table_filter.set('All')

        tk.Button(control_frame, text="Apply Filter", bg='#3498db', fg='white',
                  command=self.apply_filter, relief='flat').pack(side='left', padx=10)
        tk.Button(control_frame, text="Restore Selected", bg='#27ae60', fg='white',
                  command=self.restore_selected, relief='flat').pack(side='left', padx=5)
        tk.Button(control_frame, text="Empty Bin", bg='#e74c3c', fg='white',
                  command=self.empty_bin, relief='flat').pack(side='left', padx=5)

        table_frame = tk.Frame(self.root, bg='#1a2b3e')
        table_frame.pack(expand=True, fill='both', padx=20, pady=10)

        columns = ('Table', 'Record ID', 'Name/Description',
                   'Deleted By', 'Deleted At', 'Actions')
        self.tree = ttk.Treeview(table_frame, columns=columns, show='headings', height=20)

        style = ttk.Style()
        style.theme_use('clam')
        style.configure("Treeview", background="#2c3e50", foreground="white",
                        fieldbackground="#2c3e50", borderwidth=0)
        style.configure("Treeview.Heading", background="#7f8c8d",
                        foreground="white", relief="flat")
        style.map("Treeview", background=[('selected', '#3498db')])

        for col in columns:
            self.tree.heading(col, text=col)
            self.tree.column(col, width=120)

        scrollbar = ttk.Scrollbar(table_frame, orient=tk.VERTICAL, command=self.tree.yview)
        self.tree.configure(yscrollcommand=scrollbar.set)
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
        self.tree.pack(side=tk.LEFT, expand=True, fill='both')

        self.load_deleted_items()

    def load_deleted_items(self, table_filter='All'):
        for item in self.tree.get_children():
            self.tree.delete(item)

        tables = ['staff', 'customers', 'classes', 'bookings', 'invoices']

        for table in tables:
            if table_filter != 'All' and table != table_filter:
                continue

            records = get_deleted_records(table)

            for record in records:
                if table == 'staff':
                    name = f"{record[1]} {record[2]}"
                    description = f"Staff: {record[5]}"
                elif table == 'customers':
                    name = f"{record[1]} {record[2]}"
                    description = f"Customer: {record[9]}"
                elif table == 'classes':
                    name = record[1]
                    description = f"Class: {record[8]} {record[7]}"
                elif table == 'bookings':
                    name = f"Booking #{record[0]}"
                    description = f"Cost: GBP {record[4]}"
                elif table == 'invoices':
                    name = f"Invoice #{record[0]}"
                    # FIX: invoices column 4 is amount; old code wrongly used record[5] (status)
                    description = f"Amount: GBP {record[4]}"
                else:
                    name = f"Record #{record[0]}"
                    description = table

                # FIX: every soft-deletable table ends with (..., is_deleted, deleted_at, deleted_by).
                # The old length-based guards excluded bookings/invoices because they only have 12 columns.
                deleted_by = record[-1] if record[-1] is not None else "Unknown"
                deleted_at = record[-2] if record[-2] is not None else "Unknown"

                if deleted_at and deleted_at != "Unknown":
                    try:
                        deleted_at = datetime.strptime(
                            deleted_at, '%Y-%m-%d %H:%M:%S').strftime('%d/%m %H:%M')
                    except Exception:
                        pass

                self.tree.insert('', tk.END, values=(
                    table, record[0], f"{name} - {description}",
                    f"User {deleted_by}", deleted_at, "Click to restore"
                ), tags=(table,))

    def apply_filter(self):
        self.load_deleted_items(self.table_filter.get())

    def restore_selected(self):
        selection = self.tree.selection()
        if not selection:
            messagebox.showwarning("No Selection", "Please select an item to restore")
            return

        item = self.tree.item(selection[0])
        table = item['values'][0]
        record_id = item['values'][1]

        if messagebox.askyesno("Confirm Restore",
                               f"Restore {table} record #{record_id}?"):
            if restore_record(self.user_data['staff_id'],
                              self.user_data['full_name'], table, record_id):
                messagebox.showinfo("Success", "Record restored successfully")
                self.load_deleted_items(self.table_filter.get())
            else:
                messagebox.showerror("Error", "Failed to restore record")

    def empty_bin(self):
        if messagebox.askyesno(
                "Confirm Empty",
                "Are you sure you want to PERMANENTLY delete all items in the recycle bin?\n\n"
                "This action cannot be undone!"):
            try:
                connection = sqlite3.connect("glen10_gym.db")
                cursor = connection.cursor()
                tables = ['staff', 'customers', 'classes', 'bookings', 'invoices']
                for table in tables:
                    cursor.execute(f"DELETE FROM {table} WHERE is_deleted = 1")
                connection.commit()
                connection.close()
                messagebox.showinfo("Success", "Recycle bin emptied successfully")
                self.load_deleted_items()
            except Exception as e:
                messagebox.showerror("Error", f"Failed to empty bin: {str(e)}")

    def return_to_dashboard(self):
        for widget in self.root.winfo_children():
            widget.destroy()
        self.return_callback()


####################################################################################
# STAFF MANAGEMENT
####################################################################################

class StaffManagement:
    def __init__(self, root, return_callback, user_data):
        self.root = root
        self.return_callback = return_callback
        self.user_data = user_data

        for widget in self.root.winfo_children():
            widget.destroy()

        header_frame = tk.Frame(self.root, bg='#1a2b3e', height=80)
        header_frame.pack(fill='x')
        header_frame.pack_propagate(False)

        tk.Label(header_frame, text="Staff Management", font=('Arial Black', 20),
                 bg='#1a2b3e', fg='white').pack(side='left', padx=20)

        tk.Button(header_frame, text="< Back to Dashboard", font=('Arial', 10),
                  bg='#3498db', fg='white', relief='flat',
                  command=self.return_to_dashboard, padx=15).pack(side='right', padx=20)

        control_frame = tk.Frame(self.root, bg='#0f1c2e', padx=20, pady=10)
        control_frame.pack(fill='x')

        tk.Button(control_frame, text="+ Add New Staff", bg='#27ae60', fg='white',
                  command=self.add_staff, relief='flat',
                  padx=15, pady=8).pack(side='left', padx=5)
        tk.Button(control_frame, text="Edit Staff", bg='#f39c12', fg='white',
                  command=self.edit_staff, relief='flat',
                  padx=15, pady=8).pack(side='left', padx=5)
        tk.Button(control_frame, text="Archive Staff", bg='#e74c3c', fg='white',
                  command=self.archive_staff, relief='flat',
                  padx=15, pady=8).pack(side='left', padx=5)

        filter_frame = tk.Frame(control_frame, bg='#0f1c2e')
        filter_frame.pack(side='right', padx=10)
        tk.Label(filter_frame, text="Status:", bg='#0f1c2e', fg='white').pack(side='left')
        self.status_filter = ttk.Combobox(filter_frame, values=['All', 'Active', 'Inactive'], width=12)
        self.status_filter.pack(side='left', padx=5)
        self.status_filter.set('Active')
        self.status_filter.bind('<<ComboboxSelected>>', lambda e: self.load_staff_data())

        search_frame = tk.Frame(control_frame, bg='#0f1c2e')
        search_frame.pack(side='right', padx=10)
        tk.Label(search_frame, text="Search:", bg='#0f1c2e', fg='white').pack(side='left')
        self.search_var = tk.StringVar()
        search_entry = tk.Entry(search_frame, textvariable=self.search_var, width=30,
                                bg='#2c3e50', fg='white', insertbackground='white')
        search_entry.pack(side='left', padx=5)
        search_entry.bind('<KeyRelease>', self.search_staff)

        table_frame = tk.Frame(self.root, bg='#1a2b3e')
        table_frame.pack(expand=True, fill='both', padx=20, pady=10)

        columns = ('ID', 'Name', 'Job Title', 'Mobile', 'Email',
                   'Department', 'Status', 'Hire Date')
        self.tree = ttk.Treeview(table_frame, columns=columns, show='headings', height=15)

        style = ttk.Style()
        style.theme_use('clam')
        style.configure("Treeview", background="#2c3e50", foreground="white",
                        fieldbackground="#2c3e50", borderwidth=0)
        style.configure("Treeview.Heading", background="#3498db",
                        foreground="white", relief="flat")
        style.map("Treeview", background=[('selected', '#3498db')])

        for col in columns:
            self.tree.heading(col, text=col)
            self.tree.column(col, width=100)

        scrollbar = ttk.Scrollbar(table_frame, orient=tk.VERTICAL, command=self.tree.yview)
        self.tree.configure(yscrollcommand=scrollbar.set)
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
        self.tree.pack(side=tk.LEFT, expand=True, fill='both')

        self.load_staff_data()

    def load_staff_data(self, search_term=""):
        for item in self.tree.get_children():
            self.tree.delete(item)

        connection = sqlite3.connect("glen10_gym.db")
        cursor = connection.cursor()
        status_filter = self.status_filter.get()

        if search_term:
            base = """
                SELECT staff_id, first_name || ' ' || last_name, job_title, mobile_number,
                       email, department, status, hire_date
                FROM staff
                WHERE (first_name LIKE ? OR last_name LIKE ? OR job_title LIKE ?
                       OR department LIKE ? OR email LIKE ? OR username LIKE ?)
            """
            params = [f'%{search_term}%'] * 6
            if status_filter != 'All':
                base += " AND status = ? AND is_deleted = 0"
                params.append(status_filter)
            else:
                base += " AND is_deleted = 0"
            base += " ORDER BY staff_id"
            cursor.execute(base, params)
        else:
            if status_filter != 'All':
                cursor.execute("""
                    SELECT staff_id, first_name || ' ' || last_name, job_title, mobile_number,
                           email, department, status, hire_date
                    FROM staff
                    WHERE status = ? AND is_deleted = 0
                    ORDER BY staff_id
                """, (status_filter,))
            else:
                cursor.execute("""
                    SELECT staff_id, first_name || ' ' || last_name, job_title, mobile_number,
                           email, department, status, hire_date
                    FROM staff
                    WHERE is_deleted = 0
                    ORDER BY staff_id
                """)

        for row in cursor.fetchall():
            self.tree.insert('', tk.END, values=row)
        connection.close()

    def search_staff(self, event=None):
        self.load_staff_data(self.search_var.get())

    def add_staff(self):
        if not check_permission(self.user_data['job_title'], 'staff', 'add'):
            messagebox.showwarning("Access Denied", "You don't have permission to add staff")
            return

        dialog = tk.Toplevel(self.root)
        dialog.title("Add New Staff Member")
        dialog.geometry("500x600")
        dialog.configure(bg='#0f1c2e')
        dialog.transient(self.root)
        dialog.grab_set()

        fields_frame = tk.Frame(dialog, bg='#0f1c2e', padx=20, pady=20)
        fields_frame.pack(expand=True, fill='both')

        entries = {}
        labels = [
            ('First Name:', 'first_name'),
            ('Last Name:', 'last_name'),
            ('Username:', 'username'),
            ('Password:', 'password'),
            ('Job Title:', 'job_title'),
            ('Mobile Number:', 'mobile'),
            ('Email:', 'email'),
            ('Address:', 'address'),
            ('Salary:', 'salary'),
            ('Department:', 'department'),
        ]

        for i, (label_text, field_name) in enumerate(labels):
            tk.Label(fields_frame, text=label_text, bg='#0f1c2e',
                     fg='white').grid(row=i, column=0, sticky='w', pady=5)
            if field_name == 'job_title':
                entry = ttk.Combobox(fields_frame,
                                     values=['Manager', 'Personal Trainer',
                                             'Fitness Instructor', 'Receptionist',
                                             'Cleaner', 'Admin'])
            elif field_name == 'department':
                entry = ttk.Combobox(fields_frame,
                                     values=['Management', 'Training',
                                             'Reception', 'Cleaning', 'Admin'])
            else:
                entry = tk.Entry(fields_frame, width=30, bg='#2c3e50',
                                 fg='white', insertbackground='white')
            entry.grid(row=i, column=1, pady=5, padx=10)
            entries[field_name] = entry

        tk.Label(fields_frame, text="Hire Date:", bg='#0f1c2e',
                 fg='white').grid(row=len(labels), column=0, sticky='w', pady=5)
        if DateEntry:
            hire_date = DateEntry(fields_frame, width=27, background='#3498db',
                                  foreground='white', borderwidth=2, date_pattern='yyyy-mm-dd')
        else:
            hire_date = tk.Entry(fields_frame, width=30, bg='#2c3e50',
                                 fg='white', insertbackground='white')
            hire_date.insert(0, datetime.now().strftime('%Y-%m-%d'))
        hire_date.grid(row=len(labels), column=1, pady=5, padx=10)
        entries['hire_date'] = hire_date

        button_frame = tk.Frame(dialog, bg='#0f1c2e', pady=10)
        button_frame.pack(fill='x')

        def save_staff():
            try:
                connection = sqlite3.connect("glen10_gym.db")
                cursor = connection.cursor()

                hire_date_value = (entries['hire_date'].get_date()
                                   if DateEntry else entries['hire_date'].get())

                cursor.execute("""
                    INSERT INTO staff (first_name, last_name, username, password, job_title,
                                       mobile_number, email, address, hire_date, salary, department)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """, (
                    entries['first_name'].get(),
                    entries['last_name'].get(),
                    entries['username'].get(),
                    entries['password'].get(),
                    entries['job_title'].get(),
                    entries['mobile'].get(),
                    entries['email'].get(),
                    entries['address'].get(),
                    hire_date_value,
                    float(entries['salary'].get() or 0),
                    entries['department'].get()
                ))

                staff_id = cursor.lastrowid
                connection.commit()
                connection.close()

                log_audit_action(self.user_data['staff_id'], self.user_data['full_name'],
                                 'INSERT', 'staff', staff_id, None,
                                 f"{entries['first_name'].get()} {entries['last_name'].get()}")

                messagebox.showinfo("Success", "Staff member added successfully!")
                dialog.destroy()
                self.load_staff_data()
            except sqlite3.IntegrityError:
                messagebox.showerror("Error",
                                     "Username already exists! Please choose a different username.")
            except Exception as e:
                messagebox.showerror("Error", f"Failed to add staff: {str(e)}")

        tk.Button(button_frame, text="Save", bg='#27ae60', fg='white',
                  command=save_staff, relief='flat',
                  padx=20, pady=8).pack(side='left', padx=20)
        tk.Button(button_frame, text="Cancel", bg='#95a5a6', fg='white',
                  command=dialog.destroy, relief='flat',
                  padx=20, pady=8).pack(side='left', padx=5)

    def edit_staff(self):
        if not check_permission(self.user_data['job_title'], 'staff', 'edit'):
            messagebox.showwarning("Access Denied", "You don't have permission to edit staff")
            return

        selection = self.tree.selection()
        if not selection:
            messagebox.showwarning("No Selection", "Please select a staff member to edit")
            return

        item = self.tree.item(selection[0])
        staff_id = item['values'][0]

        connection = sqlite3.connect("glen10_gym.db")
        cursor = connection.cursor()
        cursor.execute("""
            SELECT first_name, last_name, username, password, job_title,
                   mobile_number, email, address, hire_date, salary, department, status
            FROM staff WHERE staff_id = ? AND is_deleted = 0
        """, (staff_id,))
        staff_data = cursor.fetchone()
        connection.close()

        if not staff_data:
            messagebox.showerror("Error", "Staff member not found or has been deleted!")
            return

        dialog = tk.Toplevel(self.root)
        dialog.title("Edit Staff Member")
        dialog.geometry("500x650")
        dialog.configure(bg='#0f1c2e')
        dialog.transient(self.root)
        dialog.grab_set()

        fields_frame = tk.Frame(dialog, bg='#0f1c2e', padx=20, pady=20)
        fields_frame.pack(expand=True, fill='both')

        entries = {}
        labels = [
            ('First Name:', 'first_name'),
            ('Last Name:', 'last_name'),
            ('Username:', 'username'),
            ('Password:', 'password'),
            ('Job Title:', 'job_title'),
            ('Mobile Number:', 'mobile'),
            ('Email:', 'email'),
            ('Address:', 'address'),
            ('Salary:', 'salary'),
            ('Department:', 'department'),
        ]

        prefill = {
            'first_name': staff_data[0],
            'last_name': staff_data[1],
            'username': staff_data[2],
            'password': staff_data[3],
            'job_title': staff_data[4],
            'mobile': staff_data[5],
            'email': staff_data[6],
            'address': staff_data[7] or '',
            'salary': str(staff_data[9]) if staff_data[9] else '0',
            'department': staff_data[10] or '',
        }

        for i, (label_text, field_name) in enumerate(labels):
            tk.Label(fields_frame, text=label_text, bg='#0f1c2e',
                     fg='white').grid(row=i, column=0, sticky='w', pady=5)
            if field_name == 'job_title':
                entry = ttk.Combobox(fields_frame,
                                     values=['Manager', 'Personal Trainer',
                                             'Fitness Instructor', 'Receptionist',
                                             'Cleaner', 'Admin'])
                entry.set(prefill[field_name])
            elif field_name == 'department':
                entry = ttk.Combobox(fields_frame,
                                     values=['Management', 'Training',
                                             'Reception', 'Cleaning', 'Admin'])
                entry.set(prefill[field_name])
            else:
                entry = tk.Entry(fields_frame, width=30, bg='#2c3e50',
                                 fg='white', insertbackground='white')
                entry.insert(0, prefill[field_name])
            entry.grid(row=i, column=1, pady=5, padx=10)
            entries[field_name] = entry

        tk.Label(fields_frame, text="Hire Date:", bg='#0f1c2e',
                 fg='white').grid(row=len(labels), column=0, sticky='w', pady=5)
        if DateEntry:
            hire_date = DateEntry(fields_frame, width=27, background='#3498db',
                                  foreground='white', borderwidth=2,
                                  date_pattern='yyyy-mm-dd')
            try:
                hire_date.set_date(datetime.strptime(staff_data[8], '%Y-%m-%d'))
            except Exception:
                hire_date.set_date(datetime.now())
        else:
            hire_date = tk.Entry(fields_frame, width=30, bg='#2c3e50',
                                 fg='white', insertbackground='white')
            hire_date.insert(0, staff_data[8] or '')
        hire_date.grid(row=len(labels), column=1, pady=5, padx=10)
        entries['hire_date'] = hire_date

        tk.Label(fields_frame, text="Status:", bg='#0f1c2e',
                 fg='white').grid(row=len(labels) + 1, column=0, sticky='w', pady=5)
        status_combo = ttk.Combobox(fields_frame,
                                    values=['Active', 'Inactive', 'On Leave'])
        status_combo.grid(row=len(labels) + 1, column=1, pady=5, padx=10)
        status_combo.set(staff_data[11] or 'Active')
        entries['status'] = status_combo

        button_frame = tk.Frame(dialog, bg='#0f1c2e', pady=10)
        button_frame.pack(fill='x')

        def update_staff():
            try:
                old_values = (f"{staff_data[0]} {staff_data[1]}, "
                              f"{staff_data[4]}, {staff_data[5]}")
                hire_date_value = (entries['hire_date'].get_date()
                                   if DateEntry else entries['hire_date'].get())

                connection = sqlite3.connect("glen10_gym.db")
                cursor = connection.cursor()
                cursor.execute("""
                    UPDATE staff SET
                    first_name = ?, last_name = ?, username = ?, password = ?, job_title = ?,
                    mobile_number = ?, email = ?, address = ?, hire_date = ?, salary = ?,
                    department = ?, status = ?
                    WHERE staff_id = ?
                """, (
                    entries['first_name'].get(),
                    entries['last_name'].get(),
                    entries['username'].get(),
                    entries['password'].get(),
                    entries['job_title'].get(),
                    entries['mobile'].get(),
                    entries['email'].get(),
                    entries['address'].get(),
                    hire_date_value,
                    float(entries['salary'].get() or 0),
                    entries['department'].get(),
                    entries['status'].get(),
                    staff_id
                ))
                connection.commit()
                connection.close()

                new_values = (f"{entries['first_name'].get()} {entries['last_name'].get()}, "
                              f"{entries['job_title'].get()}, {entries['mobile'].get()}")
                log_audit_action(self.user_data['staff_id'], self.user_data['full_name'],
                                 'UPDATE', 'staff', staff_id, old_values, new_values)

                messagebox.showinfo("Success", "Staff member updated successfully!")
                dialog.destroy()
                self.load_staff_data()
            except sqlite3.IntegrityError:
                messagebox.showerror("Error",
                                     "Username already exists! Please choose a different username.")
            except Exception as e:
                messagebox.showerror("Error", f"Failed to update staff: {str(e)}")

        tk.Button(button_frame, text="Update", bg='#27ae60', fg='white',
                  command=update_staff, relief='flat',
                  padx=20, pady=8).pack(side='left', padx=5)
        tk.Button(button_frame, text="Cancel", bg='#95a5a6', fg='white',
                  command=dialog.destroy, relief='flat',
                  padx=20, pady=8).pack(side='left', padx=5)

    def archive_staff(self):
        if not check_permission(self.user_data['job_title'], 'staff', 'delete'):
            messagebox.showwarning("Access Denied", "You don't have permission to archive staff")
            return

        selection = self.tree.selection()
        if not selection:
            messagebox.showwarning("No Selection", "Please select a staff member to archive")
            return

        item = self.tree.item(selection[0])
        staff_id = item['values'][0]
        staff_name = item['values'][1]

        if staff_id == self.user_data['staff_id']:
            messagebox.showwarning("Warning", "You cannot archive your own account!")
            return

        if messagebox.askyesno("Confirm Archive",
                               f"Archive {staff_name}?\n\nThis will move the staff member to "
                               f"the recycle bin where they can be restored later."):
            if soft_delete_record(self.user_data['staff_id'],
                                  self.user_data['full_name'], 'staff', staff_id):
                messagebox.showinfo("Success", "Staff member archived successfully")
                self.load_staff_data()
            else:
                messagebox.showerror("Error", "Failed to archive staff member")

    def return_to_dashboard(self):
        for widget in self.root.winfo_children():
            widget.destroy()
        self.return_callback()


####################################################################################
# CUSTOMER MANAGEMENT
####################################################################################

class CustomerManagement:
    def __init__(self, root, return_callback, user_data):
        self.root = root
        self.return_callback = return_callback
        self.user_data = user_data

        for widget in self.root.winfo_children():
            widget.destroy()

        header_frame = tk.Frame(self.root, bg='#1a2b3e', height=80)
        header_frame.pack(fill='x')
        header_frame.pack_propagate(False)

        tk.Label(header_frame, text="Customer Management", font=('Arial Black', 20),
                 bg='#1a2b3e', fg='white').pack(side='left', padx=20)
        tk.Button(header_frame, text="< Back to Dashboard", font=('Arial', 10),
                  bg='#3498db', fg='white', relief='flat',
                  command=self.return_to_dashboard,
                  padx=15).pack(side='right', padx=20)

        control_frame = tk.Frame(self.root, bg='#0f1c2e', padx=20, pady=10)
        control_frame.pack(fill='x')

        tk.Button(control_frame, text="+ Add New Customer", bg='#27ae60', fg='white',
                  command=self.add_customer, relief='flat',
                  padx=15, pady=8).pack(side='left', padx=5)
        tk.Button(control_frame, text="Edit Customer", bg='#f39c12', fg='white',
                  command=self.edit_customer, relief='flat',
                  padx=15, pady=8).pack(side='left', padx=5)
        tk.Button(control_frame, text="Archive Customer", bg='#e74c3c', fg='white',
                  command=self.archive_customer, relief='flat',
                  padx=15, pady=8).pack(side='left', padx=5)

        filter_frame = tk.Frame(control_frame, bg='#0f1c2e')
        filter_frame.pack(side='right', padx=10)
        tk.Label(filter_frame, text="Status:", bg='#0f1c2e', fg='white').pack(side='left')
        self.status_filter = ttk.Combobox(filter_frame,
                                          values=['All', 'Active', 'Inactive'], width=12)
        self.status_filter.pack(side='left', padx=5)
        self.status_filter.set('Active')
        self.status_filter.bind('<<ComboboxSelected>>',
                                lambda e: self.load_customer_data())

        table_frame = tk.Frame(self.root, bg='#1a2b3e')
        table_frame.pack(expand=True, fill='both', padx=20, pady=10)

        columns = ('ID', 'Name', 'Mobile', 'Email', 'DOB',
                   'Membership', 'Status', 'Join Date')
        self.tree = ttk.Treeview(table_frame, columns=columns,
                                 show='headings', height=20)

        style = ttk.Style()
        style.theme_use('clam')
        style.configure("Treeview", background="#2c3e50", foreground="white",
                        fieldbackground="#2c3e50", borderwidth=0)
        style.configure("Treeview.Heading", background="#2ecc71",
                        foreground="white", relief="flat")
        style.map("Treeview", background=[('selected', '#2ecc71')])

        for col in columns:
            self.tree.heading(col, text=col)
            self.tree.column(col, width=100)

        scrollbar = ttk.Scrollbar(table_frame, orient=tk.VERTICAL, command=self.tree.yview)
        self.tree.configure(yscrollcommand=scrollbar.set)
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
        self.tree.pack(side=tk.LEFT, expand=True, fill='both')

        self.load_customer_data()

    def load_customer_data(self):
        for item in self.tree.get_children():
            self.tree.delete(item)

        connection = sqlite3.connect("glen10_gym.db")
        cursor = connection.cursor()
        status_filter = self.status_filter.get()

        if status_filter != 'All':
            cursor.execute("""
                SELECT customer_id, first_name || ' ' || last_name, mobile_number, email,
                       date_of_birth, membership_type, membership_status, join_date
                FROM customers
                WHERE membership_status = ? AND is_deleted = 0
                ORDER BY customer_id
            """, (status_filter,))
        else:
            cursor.execute("""
                SELECT customer_id, first_name || ' ' || last_name, mobile_number, email,
                       date_of_birth, membership_type, membership_status, join_date
                FROM customers
                WHERE is_deleted = 0
                ORDER BY customer_id
            """)

        for row in cursor.fetchall():
            self.tree.insert('', tk.END, values=row)
        connection.close()

    def add_customer(self):
        if not check_permission(self.user_data['job_title'], 'customers', 'add'):
            messagebox.showwarning("Access Denied", "You don't have permission to add customers")
            return

        dialog = tk.Toplevel(self.root)
        dialog.title("Add New Customer")
        dialog.geometry("500x700")
        dialog.configure(bg='#0f1c2e')
        dialog.transient(self.root)
        dialog.grab_set()

        fields_frame = tk.Frame(dialog, bg='#0f1c2e', padx=20, pady=20)
        fields_frame.pack(expand=True, fill='both')

        entries = {}
        row = 0

        for label_text, key in [
                ('First Name:', 'first_name'),
                ('Last Name:', 'last_name'),
                ('Mobile Number:', 'mobile'),
                ('Email:', 'email')]:
            tk.Label(fields_frame, text=label_text, bg='#0f1c2e',
                     fg='white').grid(row=row, column=0, sticky='w', pady=5)
            entries[key] = tk.Entry(fields_frame, width=30, bg='#2c3e50',
                                    fg='white', insertbackground='white')
            entries[key].grid(row=row, column=1, pady=5, padx=10)
            row += 1

        tk.Label(fields_frame, text="Date of Birth:", bg='#0f1c2e',
                 fg='white').grid(row=row, column=0, sticky='w', pady=5)
        if DateEntry:
            entries['dob'] = DateEntry(fields_frame, width=27, background='#2ecc71',
                                       foreground='white', borderwidth=2,
                                       date_pattern='yyyy-mm-dd')
        else:
            entries['dob'] = tk.Entry(fields_frame, width=30, bg='#2c3e50',
                                      fg='white', insertbackground='white')
            entries['dob'].insert(0, "2000-01-01")
        entries['dob'].grid(row=row, column=1, pady=5, padx=10)
        row += 1

        for label_text, key in [('Address:', 'address'), ('Postcode:', 'postcode')]:
            tk.Label(fields_frame, text=label_text, bg='#0f1c2e',
                     fg='white').grid(row=row, column=0, sticky='w', pady=5)
            entries[key] = tk.Entry(fields_frame, width=30, bg='#2c3e50',
                                    fg='white', insertbackground='white')
            entries[key].grid(row=row, column=1, pady=5, padx=10)
            row += 1

        tk.Label(fields_frame, text="Membership Type:", bg='#0f1c2e',
                 fg='white').grid(row=row, column=0, sticky='w', pady=5)
        entries['membership'] = ttk.Combobox(
            fields_frame,
            values=['Basic', 'Premium', 'Student', 'Family', 'Corporate'])
        entries['membership'].grid(row=row, column=1, pady=5, padx=10)
        row += 1

        tk.Label(fields_frame, text="Emergency Contact:", bg='#0f1c2e',
                 fg='white').grid(row=row, column=0, sticky='w', pady=5)
        entries['emergency'] = tk.Entry(fields_frame, width=30, bg='#2c3e50',
                                        fg='white', insertbackground='white')
        entries['emergency'].grid(row=row, column=1, pady=5, padx=10)
        row += 1

        tk.Label(fields_frame, text="Medical Notes:", bg='#0f1c2e',
                 fg='white').grid(row=row, column=0, sticky='w', pady=5)
        entries['medical'] = tk.Text(fields_frame, width=30, height=4,
                                     bg='#2c3e50', fg='white', insertbackground='white')
        entries['medical'].grid(row=row, column=1, pady=5, padx=10)

        def save_customer():
            try:
                connection = sqlite3.connect("glen10_gym.db")
                cursor = connection.cursor()
                dob_value = (entries['dob'].get_date()
                             if DateEntry else entries['dob'].get())

                cursor.execute("""
                    INSERT INTO customers (first_name, last_name, mobile_number, email,
                                           date_of_birth, address, postcode, membership_type,
                                           emergency_contact, medical_notes)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """, (
                    entries['first_name'].get(),
                    entries['last_name'].get(),
                    entries['mobile'].get(),
                    entries['email'].get(),
                    dob_value,
                    entries['address'].get(),
                    entries['postcode'].get(),
                    entries['membership'].get(),
                    entries['emergency'].get(),
                    entries['medical'].get('1.0', tk.END).strip()
                ))

                customer_id = cursor.lastrowid
                connection.commit()
                connection.close()

                log_audit_action(self.user_data['staff_id'], self.user_data['full_name'],
                                 'INSERT', 'customers', customer_id, None,
                                 f"{entries['first_name'].get()} {entries['last_name'].get()}")

                messagebox.showinfo("Success", "Customer added successfully!")
                dialog.destroy()
                self.load_customer_data()
            except Exception as e:
                messagebox.showerror("Error", f"Failed to add customer: {str(e)}")

        button_frame = tk.Frame(dialog, bg='#0f1c2e', pady=10)
        button_frame.pack(fill='x')
        tk.Button(button_frame, text="Save", bg='#27ae60', fg='white',
                  command=save_customer, relief='flat',
                  padx=20, pady=8).pack(side='left', padx=20)
        tk.Button(button_frame, text="Cancel", bg='#95a5a6', fg='white',
                  command=dialog.destroy, relief='flat',
                  padx=20, pady=8).pack(side='left', padx=5)

    def edit_customer(self):
        if not check_permission(self.user_data['job_title'], 'customers', 'edit'):
            messagebox.showwarning("Access Denied", "You don't have permission to edit customers")
            return

        selection = self.tree.selection()
        if not selection:
            messagebox.showwarning("No Selection", "Please select a customer to edit")
            return

        item = self.tree.item(selection[0])
        customer_id = item['values'][0]

        connection = sqlite3.connect("glen10_gym.db")
        cursor = connection.cursor()
        cursor.execute("""
            SELECT first_name, last_name, mobile_number, email, date_of_birth,
                   address, postcode, membership_type, membership_status,
                   emergency_contact, medical_notes
            FROM customers WHERE customer_id = ? AND is_deleted = 0
        """, (customer_id,))
        customer_data = cursor.fetchone()
        connection.close()

        if not customer_data:
            messagebox.showerror("Error", "Customer not found or has been deleted!")
            return

        dialog = tk.Toplevel(self.root)
        dialog.title("Edit Customer")
        dialog.geometry("500x700")
        dialog.configure(bg='#0f1c2e')
        dialog.transient(self.root)
        dialog.grab_set()

        fields_frame = tk.Frame(dialog, bg='#0f1c2e', padx=20, pady=20)
        fields_frame.pack(expand=True, fill='both')

        entries = {}
        row = 0
        text_fields = [
            ('First Name:', 'first_name', customer_data[0]),
            ('Last Name:', 'last_name', customer_data[1]),
            ('Mobile Number:', 'mobile', customer_data[2]),
            ('Email:', 'email', customer_data[3]),
        ]
        for label_text, key, value in text_fields:
            tk.Label(fields_frame, text=label_text, bg='#0f1c2e',
                     fg='white').grid(row=row, column=0, sticky='w', pady=5)
            entries[key] = tk.Entry(fields_frame, width=30, bg='#2c3e50',
                                    fg='white', insertbackground='white')
            entries[key].insert(0, value)
            entries[key].grid(row=row, column=1, pady=5, padx=10)
            row += 1

        tk.Label(fields_frame, text="Date of Birth:", bg='#0f1c2e',
                 fg='white').grid(row=row, column=0, sticky='w', pady=5)
        if DateEntry:
            entries['dob'] = DateEntry(fields_frame, width=27, background='#2ecc71',
                                       foreground='white', borderwidth=2,
                                       date_pattern='yyyy-mm-dd')
            try:
                entries['dob'].set_date(datetime.strptime(customer_data[4], '%Y-%m-%d'))
            except Exception:
                entries['dob'].set_date(datetime.now())
        else:
            entries['dob'] = tk.Entry(fields_frame, width=30, bg='#2c3e50',
                                      fg='white', insertbackground='white')
            entries['dob'].insert(0, customer_data[4])
        entries['dob'].grid(row=row, column=1, pady=5, padx=10)
        row += 1

        for label_text, key, value in [
                ('Address:', 'address', customer_data[5] or ''),
                ('Postcode:', 'postcode', customer_data[6] or '')]:
            tk.Label(fields_frame, text=label_text, bg='#0f1c2e',
                     fg='white').grid(row=row, column=0, sticky='w', pady=5)
            entries[key] = tk.Entry(fields_frame, width=30, bg='#2c3e50',
                                    fg='white', insertbackground='white')
            entries[key].insert(0, value)
            entries[key].grid(row=row, column=1, pady=5, padx=10)
            row += 1

        tk.Label(fields_frame, text="Membership Type:", bg='#0f1c2e',
                 fg='white').grid(row=row, column=0, sticky='w', pady=5)
        entries['membership'] = ttk.Combobox(
            fields_frame,
            values=['Basic', 'Premium', 'Student', 'Family', 'Corporate'])
        entries['membership'].grid(row=row, column=1, pady=5, padx=10)
        entries['membership'].set(customer_data[7])
        row += 1

        tk.Label(fields_frame, text="Membership Status:", bg='#0f1c2e',
                 fg='white').grid(row=row, column=0, sticky='w', pady=5)
        entries['status'] = ttk.Combobox(
            fields_frame,
            values=['Active', 'Inactive', 'Suspended', 'Cancelled'])
        entries['status'].grid(row=row, column=1, pady=5, padx=10)
        entries['status'].set(customer_data[8])
        row += 1

        tk.Label(fields_frame, text="Emergency Contact:", bg='#0f1c2e',
                 fg='white').grid(row=row, column=0, sticky='w', pady=5)
        entries['emergency'] = tk.Entry(fields_frame, width=30, bg='#2c3e50',
                                        fg='white', insertbackground='white')
        entries['emergency'].insert(0, customer_data[9] or '')
        entries['emergency'].grid(row=row, column=1, pady=5, padx=10)
        row += 1

        tk.Label(fields_frame, text="Medical Notes:", bg='#0f1c2e',
                 fg='white').grid(row=row, column=0, sticky='w', pady=5)
        entries['medical'] = tk.Text(fields_frame, width=30, height=4,
                                     bg='#2c3e50', fg='white', insertbackground='white')
        entries['medical'].grid(row=row, column=1, pady=5, padx=10)
        entries['medical'].insert('1.0', customer_data[10] or '')

        def update_customer():
            try:
                old_values = (f"{customer_data[0]} {customer_data[1]}, "
                              f"{customer_data[2]}, {customer_data[7]}")
                connection = sqlite3.connect("glen10_gym.db")
                cursor = connection.cursor()
                dob_value = (entries['dob'].get_date()
                             if DateEntry else entries['dob'].get())

                cursor.execute("""
                    UPDATE customers SET
                    first_name = ?, last_name = ?, mobile_number = ?, email = ?,
                    date_of_birth = ?, address = ?, postcode = ?, membership_type = ?,
                    membership_status = ?, emergency_contact = ?, medical_notes = ?
                    WHERE customer_id = ?
                """, (
                    entries['first_name'].get(),
                    entries['last_name'].get(),
                    entries['mobile'].get(),
                    entries['email'].get(),
                    dob_value,
                    entries['address'].get(),
                    entries['postcode'].get(),
                    entries['membership'].get(),
                    entries['status'].get(),
                    entries['emergency'].get(),
                    entries['medical'].get('1.0', tk.END).strip(),
                    customer_id
                ))
                connection.commit()
                connection.close()

                new_values = (f"{entries['first_name'].get()} {entries['last_name'].get()}, "
                              f"{entries['mobile'].get()}, {entries['membership'].get()}")
                log_audit_action(self.user_data['staff_id'], self.user_data['full_name'],
                                 'UPDATE', 'customers', customer_id, old_values, new_values)

                messagebox.showinfo("Success", "Customer updated successfully!")
                dialog.destroy()
                self.load_customer_data()
            except Exception as e:
                messagebox.showerror("Error", f"Failed to update customer: {str(e)}")

        button_frame = tk.Frame(dialog, bg='#0f1c2e', pady=10)
        button_frame.pack(fill='x')
        tk.Button(button_frame, text="Update", bg='#27ae60', fg='white',
                  command=update_customer, relief='flat',
                  padx=20, pady=8).pack(side='left', padx=5)
        tk.Button(button_frame, text="Cancel", bg='#95a5a6', fg='white',
                  command=dialog.destroy, relief='flat',
                  padx=20, pady=8).pack(side='left', padx=5)

    def archive_customer(self):
        if not check_permission(self.user_data['job_title'], 'customers', 'delete'):
            messagebox.showwarning("Access Denied", "You don't have permission to archive customers")
            return

        selection = self.tree.selection()
        if not selection:
            messagebox.showwarning("No Selection", "Please select a customer to archive")
            return

        item = self.tree.item(selection[0])
        customer_id = item['values'][0]
        customer_name = item['values'][1]

        if messagebox.askyesno("Confirm Archive",
                               f"Archive {customer_name}?\n\nThis will move the customer to the "
                               f"recycle bin where they can be restored later."):
            if soft_delete_record(self.user_data['staff_id'],
                                  self.user_data['full_name'], 'customers', customer_id):
                messagebox.showinfo("Success", "Customer archived successfully")
                self.load_customer_data()
            else:
                messagebox.showerror("Error", "Failed to archive customer")

    def return_to_dashboard(self):
        for widget in self.root.winfo_children():
            widget.destroy()
        self.return_callback()


####################################################################################
# CLASS MANAGEMENT
####################################################################################

class ClassManagement:
    def __init__(self, root, return_callback, user_data):
        self.root = root
        self.return_callback = return_callback
        self.user_data = user_data

        for widget in self.root.winfo_children():
            widget.destroy()

        header_frame = tk.Frame(self.root, bg='#1a2b3e', height=80)
        header_frame.pack(fill='x')
        header_frame.pack_propagate(False)

        tk.Label(header_frame, text="Class Management", font=('Arial Black', 20),
                 bg='#1a2b3e', fg='white').pack(side='left', padx=20)
        tk.Button(header_frame, text="< Back to Dashboard", font=('Arial', 10),
                  bg='#3498db', fg='white', relief='flat',
                  command=self.return_to_dashboard,
                  padx=15).pack(side='right', padx=20)

        control_frame = tk.Frame(self.root, bg='#0f1c2e', padx=20, pady=10)
        control_frame.pack(fill='x')

        tk.Button(control_frame, text="+ Add New Class", bg='#27ae60', fg='white',
                  command=self.add_class, relief='flat',
                  padx=15, pady=8).pack(side='left', padx=5)
        tk.Button(control_frame, text="Edit Class", bg='#f39c12', fg='white',
                  command=self.edit_class, relief='flat',
                  padx=15, pady=8).pack(side='left', padx=5)
        tk.Button(control_frame, text="Archive Class", bg='#e74c3c', fg='white',
                  command=self.archive_class, relief='flat',
                  padx=15, pady=8).pack(side='left', padx=5)

        filter_frame = tk.Frame(control_frame, bg='#0f1c2e')
        filter_frame.pack(side='right', padx=10)
        tk.Label(filter_frame, text="Status:", bg='#0f1c2e', fg='white').pack(side='left')
        self.status_filter = ttk.Combobox(filter_frame,
                                          values=['All', 'Active', 'Inactive'], width=12)
        self.status_filter.pack(side='left', padx=5)
        self.status_filter.set('Active')
        self.status_filter.bind('<<ComboboxSelected>>',
                                lambda e: self.load_class_data())

        table_frame = tk.Frame(self.root, bg='#1a2b3e')
        table_frame.pack(expand=True, fill='both', padx=20, pady=10)

        columns = ('ID', 'Class Name', 'Instructor', 'Time', 'Day', 'Duration',
                   'Capacity', 'Enrolled', 'Room', 'Difficulty', 'Status')
        self.tree = ttk.Treeview(table_frame, columns=columns,
                                 show='headings', height=15)

        style = ttk.Style()
        style.theme_use('clam')
        style.configure("Treeview", background="#2c3e50", foreground="white",
                        fieldbackground="#2c3e50", borderwidth=0)
        style.configure("Treeview.Heading", background="#e74c3c",
                        foreground="white", relief="flat")
        style.map("Treeview", background=[('selected', '#e74c3c')])

        for col in columns:
            self.tree.heading(col, text=col)
            self.tree.column(col, width=90)

        scrollbar = ttk.Scrollbar(table_frame, orient=tk.VERTICAL, command=self.tree.yview)
        self.tree.configure(yscrollcommand=scrollbar.set)
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
        self.tree.pack(side=tk.LEFT, expand=True, fill='both')

        self.load_class_data()

    def load_class_data(self):
        for item in self.tree.get_children():
            self.tree.delete(item)

        connection = sqlite3.connect("glen10_gym.db")
        cursor = connection.cursor()
        status_filter = self.status_filter.get()

        if status_filter == 'Active':
            where_extra = " AND c.is_active = 1"
        elif status_filter == 'Inactive':
            where_extra = " AND c.is_active = 0"
        else:
            where_extra = ""

        cursor.execute(f"""
            SELECT c.class_id, c.class_name,
                   COALESCE(s.first_name || ' ' || s.last_name, 'Not Assigned'),
                   c.class_time, c.class_day, c.duration_minutes,
                   c.max_capacity, c.current_enrollment,
                   COALESCE(c.room_number, 'TBA'), c.difficulty_level,
                   CASE WHEN c.is_active = 1 THEN 'Active' ELSE 'Inactive' END
            FROM classes c
            LEFT JOIN staff s ON c.instructor_id = s.staff_id
            WHERE c.is_deleted = 0{where_extra}
            ORDER BY c.class_day, c.class_time
        """)

        for row in cursor.fetchall():
            self.tree.insert('', tk.END, values=row)
        connection.close()

    def _get_instructor_options(self):
        connection = sqlite3.connect("glen10_gym.db")
        cursor = connection.cursor()
        # FIX: parenthesise the OR conditions so AND is_deleted = 0 applies to both
        cursor.execute("""
            SELECT staff_id, first_name || ' ' || last_name FROM staff
            WHERE (job_title LIKE '%Trainer%' OR job_title LIKE '%Instructor%')
              AND status = 'Active' AND is_deleted = 0
            ORDER BY first_name
        """)
        instructors = cursor.fetchall()
        connection.close()
        return instructors

    def add_class(self):
        if not check_permission(self.user_data['job_title'], 'classes', 'add'):
            messagebox.showwarning("Access Denied", "You don't have permission to add classes")
            return

        dialog = tk.Toplevel(self.root)
        dialog.title("Add New Class")
        dialog.geometry("500x600")
        dialog.configure(bg='#0f1c2e')
        dialog.transient(self.root)
        dialog.grab_set()

        fields_frame = tk.Frame(dialog, bg='#0f1c2e', padx=20, pady=20)
        fields_frame.pack(expand=True, fill='both')

        entries = {}
        instructors = self._get_instructor_options()
        instructor_dict = {name: id for id, name in instructors}

        row = 0
        tk.Label(fields_frame, text="Class Name:", bg='#0f1c2e',
                 fg='white').grid(row=row, column=0, sticky='w', pady=5)
        entries['name'] = tk.Entry(fields_frame, width=30, bg='#2c3e50',
                                   fg='white', insertbackground='white')
        entries['name'].grid(row=row, column=1, pady=5, padx=10)
        row += 1

        tk.Label(fields_frame, text="Description:", bg='#0f1c2e',
                 fg='white').grid(row=row, column=0, sticky='w', pady=5)
        entries['description'] = tk.Text(fields_frame, width=30, height=3,
                                         bg='#2c3e50', fg='white',
                                         insertbackground='white')
        entries['description'].grid(row=row, column=1, pady=5, padx=10)
        row += 1

        tk.Label(fields_frame, text="Instructor:", bg='#0f1c2e',
                 fg='white').grid(row=row, column=0, sticky='w', pady=5)
        entries['instructor'] = ttk.Combobox(fields_frame,
                                             values=[name for _, name in instructors])
        entries['instructor'].grid(row=row, column=1, pady=5, padx=10)
        row += 1

        tk.Label(fields_frame, text="Duration (minutes):", bg='#0f1c2e',
                 fg='white').grid(row=row, column=0, sticky='w', pady=5)
        entries['duration'] = tk.Spinbox(fields_frame, from_=30, to=180,
                                         increment=15, width=27,
                                         bg='#2c3e50', fg='white',
                                         insertbackground='white')
        entries['duration'].grid(row=row, column=1, pady=5, padx=10)
        row += 1

        tk.Label(fields_frame, text="Max Capacity:", bg='#0f1c2e',
                 fg='white').grid(row=row, column=0, sticky='w', pady=5)
        entries['capacity'] = tk.Spinbox(fields_frame, from_=1, to=50, width=27,
                                         bg='#2c3e50', fg='white',
                                         insertbackground='white')
        entries['capacity'].grid(row=row, column=1, pady=5, padx=10)
        row += 1

        tk.Label(fields_frame, text="Class Time (HH:MM):", bg='#0f1c2e',
                 fg='white').grid(row=row, column=0, sticky='w', pady=5)
        entries['time'] = tk.Entry(fields_frame, width=30, bg='#2c3e50',
                                   fg='white', insertbackground='white')
        entries['time'].insert(0, "18:00")
        entries['time'].grid(row=row, column=1, pady=5, padx=10)
        row += 1

        tk.Label(fields_frame, text="Day of Week:", bg='#0f1c2e',
                 fg='white').grid(row=row, column=0, sticky='w', pady=5)
        entries['day'] = ttk.Combobox(
            fields_frame,
            values=['Monday', 'Tuesday', 'Wednesday', 'Thursday',
                    'Friday', 'Saturday', 'Sunday'])
        entries['day'].grid(row=row, column=1, pady=5, padx=10)
        row += 1

        tk.Label(fields_frame, text="Room:", bg='#0f1c2e',
                 fg='white').grid(row=row, column=0, sticky='w', pady=5)
        entries['room'] = tk.Entry(fields_frame, width=30, bg='#2c3e50',
                                   fg='white', insertbackground='white')
        entries['room'].grid(row=row, column=1, pady=5, padx=10)
        row += 1

        tk.Label(fields_frame, text="Difficulty Level:", bg='#0f1c2e',
                 fg='white').grid(row=row, column=0, sticky='w', pady=5)
        entries['difficulty'] = ttk.Combobox(
            fields_frame,
            values=['Beginner', 'Intermediate', 'Advanced', 'All Levels'])
        entries['difficulty'].grid(row=row, column=1, pady=5, padx=10)
        row += 1

        tk.Label(fields_frame, text="Equipment Required:", bg='#0f1c2e',
                 fg='white').grid(row=row, column=0, sticky='w', pady=5)
        entries['equipment'] = tk.Entry(fields_frame, width=30, bg='#2c3e50',
                                        fg='white', insertbackground='white')
        entries['equipment'].grid(row=row, column=1, pady=5, padx=10)
        row += 1

        tk.Label(fields_frame, text="Status:", bg='#0f1c2e',
                 fg='white').grid(row=row, column=0, sticky='w', pady=5)
        entries['status'] = ttk.Combobox(fields_frame, values=['Active', 'Inactive'])
        entries['status'].grid(row=row, column=1, pady=5, padx=10)
        entries['status'].set('Active')

        def save_class():
            try:
                instructor_name = entries['instructor'].get()
                instructor_id = instructor_dict.get(instructor_name) if instructor_name else None

                connection = sqlite3.connect("glen10_gym.db")
                cursor = connection.cursor()
                cursor.execute("""
                    INSERT INTO classes (class_name, description, instructor_id,
                                         duration_minutes, max_capacity, class_time,
                                         class_day, room_number, difficulty_level,
                                         equipment_required, is_active)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """, (
                    entries['name'].get(),
                    entries['description'].get('1.0', tk.END).strip(),
                    instructor_id,
                    int(entries['duration'].get()),
                    int(entries['capacity'].get()),
                    entries['time'].get(),
                    entries['day'].get(),
                    entries['room'].get(),
                    entries['difficulty'].get(),
                    entries['equipment'].get(),
                    1 if entries['status'].get() == 'Active' else 0
                ))

                class_id = cursor.lastrowid
                connection.commit()
                connection.close()

                log_audit_action(self.user_data['staff_id'], self.user_data['full_name'],
                                 'INSERT', 'classes', class_id, None,
                                 f"{entries['name'].get()} - "
                                 f"{entries['day'].get()} {entries['time'].get()}")

                messagebox.showinfo("Success", "Class added successfully!")
                dialog.destroy()
                self.load_class_data()
            except Exception as e:
                messagebox.showerror("Error", f"Failed to add class: {str(e)}")

        button_frame = tk.Frame(dialog, bg='#0f1c2e', pady=10)
        button_frame.pack(fill='x')
        tk.Button(button_frame, text="Save", bg='#27ae60', fg='white',
                  command=save_class, relief='flat',
                  padx=20, pady=8).pack(side='left', padx=20)
        tk.Button(button_frame, text="Cancel", bg='#95a5a6', fg='white',
                  command=dialog.destroy, relief='flat',
                  padx=20, pady=8).pack(side='left', padx=5)

    def edit_class(self):
        if not check_permission(self.user_data['job_title'], 'classes', 'edit'):
            messagebox.showwarning("Access Denied", "You don't have permission to edit classes")
            return

        selection = self.tree.selection()
        if not selection:
            messagebox.showwarning("No Selection", "Please select a class to edit")
            return

        item = self.tree.item(selection[0])
        class_id = item['values'][0]

        connection = sqlite3.connect("glen10_gym.db")
        cursor = connection.cursor()
        cursor.execute("""
            SELECT class_name, description, instructor_id, duration_minutes,
                   max_capacity, class_time, class_day, room_number,
                   difficulty_level, equipment_required, is_active
            FROM classes WHERE class_id = ? AND is_deleted = 0
        """, (class_id,))
        class_data = cursor.fetchone()

        current_instructor = None
        if class_data and class_data[2]:
            cursor.execute("SELECT first_name || ' ' || last_name FROM staff WHERE staff_id = ?",
                           (class_data[2],))
            result = cursor.fetchone()
            current_instructor = result[0] if result else None
        connection.close()

        if not class_data:
            messagebox.showerror("Error", "Class not found or has been deleted!")
            return

        instructors = self._get_instructor_options()
        instructor_dict = {name: id for id, name in instructors}

        dialog = tk.Toplevel(self.root)
        dialog.title("Edit Class")
        dialog.geometry("500x600")
        dialog.configure(bg='#0f1c2e')
        dialog.transient(self.root)
        dialog.grab_set()

        fields_frame = tk.Frame(dialog, bg='#0f1c2e', padx=20, pady=20)
        fields_frame.pack(expand=True, fill='both')

        entries = {}
        row = 0

        tk.Label(fields_frame, text="Class Name:", bg='#0f1c2e',
                 fg='white').grid(row=row, column=0, sticky='w', pady=5)
        entries['name'] = tk.Entry(fields_frame, width=30, bg='#2c3e50',
                                   fg='white', insertbackground='white')
        entries['name'].insert(0, class_data[0])
        entries['name'].grid(row=row, column=1, pady=5, padx=10)
        row += 1

        tk.Label(fields_frame, text="Description:", bg='#0f1c2e',
                 fg='white').grid(row=row, column=0, sticky='w', pady=5)
        entries['description'] = tk.Text(fields_frame, width=30, height=3,
                                         bg='#2c3e50', fg='white',
                                         insertbackground='white')
        entries['description'].grid(row=row, column=1, pady=5, padx=10)
        entries['description'].insert('1.0', class_data[1] or '')
        row += 1

        tk.Label(fields_frame, text="Instructor:", bg='#0f1c2e',
                 fg='white').grid(row=row, column=0, sticky='w', pady=5)
        entries['instructor'] = ttk.Combobox(fields_frame,
                                             values=[name for _, name in instructors])
        entries['instructor'].grid(row=row, column=1, pady=5, padx=10)
        if current_instructor:
            entries['instructor'].set(current_instructor)
        row += 1

        tk.Label(fields_frame, text="Duration (minutes):", bg='#0f1c2e',
                 fg='white').grid(row=row, column=0, sticky='w', pady=5)
        entries['duration'] = tk.Spinbox(fields_frame, from_=30, to=180,
                                         increment=15, width=27,
                                         bg='#2c3e50', fg='white',
                                         insertbackground='white')
        entries['duration'].grid(row=row, column=1, pady=5, padx=10)
        entries['duration'].delete(0, tk.END)
        entries['duration'].insert(0, class_data[3])
        row += 1

        tk.Label(fields_frame, text="Max Capacity:", bg='#0f1c2e',
                 fg='white').grid(row=row, column=0, sticky='w', pady=5)
        entries['capacity'] = tk.Spinbox(fields_frame, from_=1, to=50, width=27,
                                         bg='#2c3e50', fg='white',
                                         insertbackground='white')
        entries['capacity'].grid(row=row, column=1, pady=5, padx=10)
        entries['capacity'].delete(0, tk.END)
        entries['capacity'].insert(0, class_data[4])
        row += 1

        tk.Label(fields_frame, text="Class Time:", bg='#0f1c2e',
                 fg='white').grid(row=row, column=0, sticky='w', pady=5)
        entries['time'] = tk.Entry(fields_frame, width=30, bg='#2c3e50',
                                   fg='white', insertbackground='white')
        entries['time'].insert(0, class_data[5])
        entries['time'].grid(row=row, column=1, pady=5, padx=10)
        row += 1

        tk.Label(fields_frame, text="Day of Week:", bg='#0f1c2e',
                 fg='white').grid(row=row, column=0, sticky='w', pady=5)
        entries['day'] = ttk.Combobox(
            fields_frame,
            values=['Monday', 'Tuesday', 'Wednesday', 'Thursday',
                    'Friday', 'Saturday', 'Sunday'])
        entries['day'].grid(row=row, column=1, pady=5, padx=10)
        entries['day'].set(class_data[6])
        row += 1

        tk.Label(fields_frame, text="Room:", bg='#0f1c2e',
                 fg='white').grid(row=row, column=0, sticky='w', pady=5)
        entries['room'] = tk.Entry(fields_frame, width=30, bg='#2c3e50',
                                   fg='white', insertbackground='white')
        entries['room'].insert(0, class_data[7] or '')
        entries['room'].grid(row=row, column=1, pady=5, padx=10)
        row += 1

        tk.Label(fields_frame, text="Difficulty Level:", bg='#0f1c2e',
                 fg='white').grid(row=row, column=0, sticky='w', pady=5)
        entries['difficulty'] = ttk.Combobox(
            fields_frame,
            values=['Beginner', 'Intermediate', 'Advanced', 'All Levels'])
        entries['difficulty'].grid(row=row, column=1, pady=5, padx=10)
        entries['difficulty'].set(class_data[8] or 'Beginner')
        row += 1

        tk.Label(fields_frame, text="Equipment Required:", bg='#0f1c2e',
                 fg='white').grid(row=row, column=0, sticky='w', pady=5)
        entries['equipment'] = tk.Entry(fields_frame, width=30, bg='#2c3e50',
                                        fg='white', insertbackground='white')
        entries['equipment'].insert(0, class_data[9] or '')
        entries['equipment'].grid(row=row, column=1, pady=5, padx=10)
        row += 1

        tk.Label(fields_frame, text="Status:", bg='#0f1c2e',
                 fg='white').grid(row=row, column=0, sticky='w', pady=5)
        entries['status'] = ttk.Combobox(fields_frame, values=['Active', 'Inactive'])
        entries['status'].grid(row=row, column=1, pady=5, padx=10)
        entries['status'].set('Active' if class_data[10] == 1 else 'Inactive')

        def update_class():
            try:
                old_values = (f"{class_data[0]}, {class_data[6]} {class_data[5]}, "
                              f"Instructor: {current_instructor or 'None'}")
                instructor_name = entries['instructor'].get()
                instructor_id = instructor_dict.get(instructor_name) if instructor_name else None

                connection = sqlite3.connect("glen10_gym.db")
                cursor = connection.cursor()
                cursor.execute("""
                    UPDATE classes SET
                    class_name = ?, description = ?, instructor_id = ?, duration_minutes = ?,
                    max_capacity = ?, class_time = ?, class_day = ?, room_number = ?,
                    difficulty_level = ?, equipment_required = ?, is_active = ?
                    WHERE class_id = ?
                """, (
                    entries['name'].get(),
                    entries['description'].get('1.0', tk.END).strip(),
                    instructor_id,
                    int(entries['duration'].get()),
                    int(entries['capacity'].get()),
                    entries['time'].get(),
                    entries['day'].get(),
                    entries['room'].get(),
                    entries['difficulty'].get(),
                    entries['equipment'].get(),
                    1 if entries['status'].get() == 'Active' else 0,
                    class_id
                ))
                connection.commit()
                connection.close()

                new_values = (f"{entries['name'].get()}, "
                              f"{entries['day'].get()} {entries['time'].get()}, "
                              f"Instructor: {instructor_name or 'None'}")
                log_audit_action(self.user_data['staff_id'], self.user_data['full_name'],
                                 'UPDATE', 'classes', class_id, old_values, new_values)

                messagebox.showinfo("Success", "Class updated successfully!")
                dialog.destroy()
                self.load_class_data()
            except Exception as e:
                messagebox.showerror("Error", f"Failed to update class: {str(e)}")

        button_frame = tk.Frame(dialog, bg='#0f1c2e', pady=10)
        button_frame.pack(fill='x')
        tk.Button(button_frame, text="Update", bg='#27ae60', fg='white',
                  command=update_class, relief='flat',
                  padx=20, pady=8).pack(side='left', padx=5)
        tk.Button(button_frame, text="Cancel", bg='#95a5a6', fg='white',
                  command=dialog.destroy, relief='flat',
                  padx=20, pady=8).pack(side='left', padx=5)

    def archive_class(self):
        if not check_permission(self.user_data['job_title'], 'classes', 'delete'):
            messagebox.showwarning("Access Denied", "You don't have permission to archive classes")
            return

        selection = self.tree.selection()
        if not selection:
            messagebox.showwarning("No Selection", "Please select a class to archive")
            return

        item = self.tree.item(selection[0])
        class_id = item['values'][0]
        class_name = item['values'][1]

        if messagebox.askyesno("Confirm Archive",
                               f"Archive {class_name}?\n\nThis will move the class to the "
                               f"recycle bin where it can be restored later."):
            if soft_delete_record(self.user_data['staff_id'],
                                  self.user_data['full_name'], 'classes', class_id):
                messagebox.showinfo("Success", "Class archived successfully")
                self.load_class_data()
            else:
                messagebox.showerror("Error", "Failed to archive class")

    def return_to_dashboard(self):
        for widget in self.root.winfo_children():
            widget.destroy()
        self.return_callback()


####################################################################################
# BOOKING MANAGEMENT  (FIX: decrement enrollment when archiving)
####################################################################################

class BookingManagement:
    def __init__(self, root, return_callback, user_data):
        self.root = root
        self.return_callback = return_callback
        self.user_data = user_data

        self.can_add = check_permission(self.user_data['job_title'], 'bookings', 'add')
        self.can_edit = check_permission(self.user_data['job_title'], 'bookings', 'edit')
        self.can_delete = check_permission(self.user_data['job_title'], 'bookings', 'delete')

        for widget in self.root.winfo_children():
            widget.destroy()

        header_frame = tk.Frame(self.root, bg='#1a2b3e', height=80)
        header_frame.pack(fill='x')
        header_frame.pack_propagate(False)
        tk.Label(header_frame, text="Booking Management", font=('Arial Black', 20),
                 bg='#1a2b3e', fg='white').pack(side='left', padx=20)
        tk.Button(header_frame, text="< Back to Dashboard", font=('Arial', 10),
                  bg='#3498db', fg='white', relief='flat',
                  command=self.return_to_dashboard,
                  padx=15).pack(side='right', padx=20)

        control_frame = tk.Frame(self.root, bg='#0f1c2e', padx=20, pady=10)
        control_frame.pack(fill='x')

        if self.can_add:
            tk.Button(control_frame, text="+ Add New Booking", bg='#27ae60', fg='white',
                      command=self.add_booking, relief='flat',
                      padx=15, pady=8).pack(side='left', padx=5)
        if self.can_edit:
            tk.Button(control_frame, text="Edit Booking", bg='#f39c12', fg='white',
                      command=self.edit_booking, relief='flat',
                      padx=15, pady=8).pack(side='left', padx=5)
        if self.can_delete:
            tk.Button(control_frame, text="Archive Booking", bg='#e74c3c', fg='white',
                      command=self.archive_booking, relief='flat',
                      padx=15, pady=8).pack(side='left', padx=5)

        filter_frame = tk.Frame(control_frame, bg='#0f1c2e')
        filter_frame.pack(side='right', padx=10)
        tk.Label(filter_frame, text="Status:", bg='#0f1c2e', fg='white').pack(side='left')
        self.status_filter = ttk.Combobox(
            filter_frame,
            values=['All', 'Booked', 'Attended', 'Cancelled', 'No-Show'], width=12)
        self.status_filter.pack(side='left', padx=5)
        self.status_filter.set('All')
        self.status_filter.bind('<<ComboboxSelected>>',
                                lambda e: self.load_booking_data())

        search_frame = tk.Frame(control_frame, bg='#0f1c2e')
        search_frame.pack(side='right', padx=10)
        tk.Label(search_frame, text="Search:", bg='#0f1c2e', fg='white').pack(side='left')
        self.search_var = tk.StringVar()
        search_entry = tk.Entry(search_frame, textvariable=self.search_var, width=30,
                                bg='#2c3e50', fg='white', insertbackground='white')
        search_entry.pack(side='left', padx=5)
        search_entry.bind('<KeyRelease>', self.search_bookings)

        table_frame = tk.Frame(self.root, bg='#1a2b3e')
        table_frame.pack(expand=True, fill='both', padx=20, pady=10)

        columns = ('ID', 'Customer', 'Class', 'Booking Date', 'Cost', 'Paid',
                   'Payment Date', 'Attendance', 'Notes')
        self.tree = ttk.Treeview(table_frame, columns=columns,
                                 show='headings', height=15)

        style = ttk.Style()
        style.theme_use('clam')
        style.configure("Treeview", background="#2c3e50", foreground="white",
                        fieldbackground="#2c3e50", borderwidth=0)
        style.configure("Treeview.Heading", background="#f39c12",
                        foreground="white", relief="flat")
        style.map("Treeview", background=[('selected', '#f39c12')])

        widths = [50, 120, 120, 120, 80, 60, 100, 80, 150]
        for i, col in enumerate(columns):
            self.tree.heading(col, text=col)
            self.tree.column(col, width=widths[i])

        scrollbar = ttk.Scrollbar(table_frame, orient=tk.VERTICAL, command=self.tree.yview)
        self.tree.configure(yscrollcommand=scrollbar.set)
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
        self.tree.pack(side=tk.LEFT, expand=True, fill='both')

        self.load_booking_data()

    def load_booking_data(self, search_term=""):
        for item in self.tree.get_children():
            self.tree.delete(item)

        connection = sqlite3.connect("glen10_gym.db")
        cursor = connection.cursor()
        status_filter = self.status_filter.get()

        if search_term:
            base = """
                SELECT b.booking_id,
                       c.first_name || ' ' || c.last_name,
                       cl.class_name,
                       DATE(b.booking_date),
                       b.cost,
                       CASE WHEN b.paid = 1 THEN 'Yes' ELSE 'No' END,
                       b.payment_date,
                       b.attendance_status,
                       b.notes
                FROM bookings b
                JOIN customers c ON b.customer_id = c.customer_id
                JOIN classes cl ON b.class_id = cl.class_id
                WHERE (c.first_name LIKE ? OR c.last_name LIKE ? OR cl.class_name LIKE ?
                       OR b.notes LIKE ?) AND b.is_deleted = 0
            """
            params = [f'%{search_term}%'] * 4
            if status_filter != 'All':
                base += " AND b.attendance_status = ?"
                params.append(status_filter)
            base += " ORDER BY b.booking_date DESC"
            cursor.execute(base, params)
        else:
            if status_filter != 'All':
                cursor.execute("""
                    SELECT b.booking_id,
                           c.first_name || ' ' || c.last_name,
                           cl.class_name,
                           DATE(b.booking_date), b.cost,
                           CASE WHEN b.paid = 1 THEN 'Yes' ELSE 'No' END,
                           b.payment_date, b.attendance_status, b.notes
                    FROM bookings b
                    JOIN customers c ON b.customer_id = c.customer_id
                    JOIN classes cl ON b.class_id = cl.class_id
                    WHERE b.attendance_status = ? AND b.is_deleted = 0
                    ORDER BY b.booking_date DESC
                """, (status_filter,))
            else:
                cursor.execute("""
                    SELECT b.booking_id,
                           c.first_name || ' ' || c.last_name,
                           cl.class_name,
                           DATE(b.booking_date), b.cost,
                           CASE WHEN b.paid = 1 THEN 'Yes' ELSE 'No' END,
                           b.payment_date, b.attendance_status, b.notes
                    FROM bookings b
                    JOIN customers c ON b.customer_id = c.customer_id
                    JOIN classes cl ON b.class_id = cl.class_id
                    WHERE b.is_deleted = 0
                    ORDER BY b.booking_date DESC
                """)

        for row in cursor.fetchall():
            self.tree.insert('', tk.END, values=row)
        connection.close()

    def search_bookings(self, event=None):
        self.load_booking_data(self.search_var.get())

    def add_booking(self):
        dialog = tk.Toplevel(self.root)
        dialog.title("Add New Booking")
        dialog.geometry("500x500")
        dialog.configure(bg='#0f1c2e')
        dialog.transient(self.root)
        dialog.grab_set()

        fields_frame = tk.Frame(dialog, bg='#0f1c2e', padx=20, pady=20)
        fields_frame.pack(expand=True, fill='both')

        entries = {}

        connection = sqlite3.connect("glen10_gym.db")
        cursor = connection.cursor()
        cursor.execute("""
            SELECT customer_id, first_name || ' ' || last_name FROM customers
            WHERE is_deleted = 0 ORDER BY last_name
        """)
        customers = cursor.fetchall()
        cursor.execute("""
            SELECT class_id, class_name || ' (' || class_day || ' ' || class_time || ')'
            FROM classes WHERE is_active = 1 AND is_deleted = 0 ORDER BY class_name
        """)
        classes = cursor.fetchall()
        connection.close()

        tk.Label(fields_frame, text="Customer:", bg='#0f1c2e',
                 fg='white').grid(row=0, column=0, sticky='w', pady=5)
        entries['customer'] = ttk.Combobox(fields_frame,
                                           values=[name for _, name in customers])
        entries['customer'].grid(row=0, column=1, pady=5, padx=10, sticky='ew')

        tk.Label(fields_frame, text="Class:", bg='#0f1c2e',
                 fg='white').grid(row=1, column=0, sticky='w', pady=5)
        entries['class'] = ttk.Combobox(fields_frame,
                                        values=[name for _, name in classes])
        entries['class'].grid(row=1, column=1, pady=5, padx=10, sticky='ew')

        tk.Label(fields_frame, text="Cost (GBP):", bg='#0f1c2e',
                 fg='white').grid(row=2, column=0, sticky='w', pady=5)
        entries['cost'] = tk.Entry(fields_frame, width=30, bg='#2c3e50',
                                   fg='white', insertbackground='white')
        entries['cost'].insert(0, "20.00")
        entries['cost'].grid(row=2, column=1, pady=5, padx=10, sticky='ew')

        tk.Label(fields_frame, text="Paid:", bg='#0f1c2e',
                 fg='white').grid(row=3, column=0, sticky='w', pady=5)
        entries['paid'] = ttk.Combobox(fields_frame, values=['Yes', 'No'])
        entries['paid'].set('No')
        entries['paid'].grid(row=3, column=1, pady=5, padx=10, sticky='ew')

        tk.Label(fields_frame, text="Payment Date:", bg='#0f1c2e',
                 fg='white').grid(row=4, column=0, sticky='w', pady=5)
        if DateEntry:
            entries['payment_date'] = DateEntry(fields_frame, width=27,
                                                background='#f39c12',
                                                foreground='white', borderwidth=2,
                                                date_pattern='yyyy-mm-dd')
        else:
            entries['payment_date'] = tk.Entry(fields_frame, width=30, bg='#2c3e50',
                                               fg='white', insertbackground='white')
        entries['payment_date'].grid(row=4, column=1, pady=5, padx=10, sticky='ew')

        tk.Label(fields_frame, text="Attendance Status:", bg='#0f1c2e',
                 fg='white').grid(row=5, column=0, sticky='w', pady=5)
        entries['attendance'] = ttk.Combobox(
            fields_frame,
            values=['Booked', 'Attended', 'Cancelled', 'No-Show'])
        entries['attendance'].set('Booked')
        entries['attendance'].grid(row=5, column=1, pady=5, padx=10, sticky='ew')

        tk.Label(fields_frame, text="Notes:", bg='#0f1c2e',
                 fg='white').grid(row=6, column=0, sticky='w', pady=5)
        entries['notes'] = tk.Text(fields_frame, width=30, height=4, bg='#2c3e50',
                                   fg='white', insertbackground='white')
        entries['notes'].grid(row=6, column=1, pady=5, padx=10, sticky='ew')

        def save_booking():
            try:
                customer_name = entries['customer'].get()
                customer_id = next((cid for cid, cname in customers if cname == customer_name), None)
                if not customer_id:
                    messagebox.showerror("Error", "Please select a customer")
                    return

                class_name = entries['class'].get()
                class_id = next((cid for cid, cname in classes if cname == class_name), None)
                if not class_id:
                    messagebox.showerror("Error", "Please select a class")
                    return

                connection = sqlite3.connect("glen10_gym.db")
                cursor = connection.cursor()

                payment_date = None
                if entries['paid'].get() == 'Yes':
                    if DateEntry:
                        payment_date = entries['payment_date'].get_date()
                    else:
                        payment_date = entries['payment_date'].get() or datetime.now().strftime('%Y-%m-%d')

                cursor.execute("""
                    INSERT INTO bookings (customer_id, class_id, cost, paid, payment_date,
                                          attendance_status, notes)
                    VALUES (?, ?, ?, ?, ?, ?, ?)
                """, (
                    customer_id, class_id,
                    float(entries['cost'].get()),
                    1 if entries['paid'].get() == 'Yes' else 0,
                    payment_date,
                    entries['attendance'].get(),
                    entries['notes'].get('1.0', tk.END).strip()
                ))
                booking_id = cursor.lastrowid

                cursor.execute("""
                    UPDATE classes SET current_enrollment = current_enrollment + 1
                    WHERE class_id = ?
                """, (class_id,))

                connection.commit()
                connection.close()

                log_audit_action(self.user_data['staff_id'], self.user_data['full_name'],
                                 'INSERT', 'bookings', booking_id, None,
                                 f"Booking for {customer_name} in {class_name}")

                messagebox.showinfo("Success", "Booking added successfully!")
                dialog.destroy()
                self.load_booking_data()
            except Exception as e:
                messagebox.showerror("Error", f"Failed to add booking: {str(e)}")

        button_frame = tk.Frame(dialog, bg='#0f1c2e', pady=10)
        button_frame.pack(fill='x')
        tk.Button(button_frame, text="Save", bg='#27ae60', fg='white',
                  command=save_booking, relief='flat',
                  padx=20, pady=8).pack(side='left', padx=20)
        tk.Button(button_frame, text="Cancel", bg='#95a5a6', fg='white',
                  command=dialog.destroy, relief='flat',
                  padx=20, pady=8).pack(side='left', padx=5)

    def edit_booking(self):
        selection = self.tree.selection()
        if not selection:
            messagebox.showwarning("No Selection", "Please select a booking to edit")
            return

        item = self.tree.item(selection[0])
        booking_id = item['values'][0]

        connection = sqlite3.connect("glen10_gym.db")
        cursor = connection.cursor()
        cursor.execute("""
            SELECT customer_id, class_id, cost, paid, payment_date,
                   attendance_status, notes
            FROM bookings WHERE booking_id = ? AND is_deleted = 0
        """, (booking_id,))
        booking_data = cursor.fetchone()

        if not booking_data:
            connection.close()
            messagebox.showerror("Error", "Booking not found or has been deleted!")
            return

        cursor.execute("SELECT first_name || ' ' || last_name FROM customers WHERE customer_id = ?",
                       (booking_data[0],))
        row = cursor.fetchone()
        customer_name = row[0] if row else ""

        cursor.execute("""
            SELECT class_name || ' (' || class_day || ' ' || class_time || ')'
            FROM classes WHERE class_id = ?
        """, (booking_data[1],))
        row = cursor.fetchone()
        class_name = row[0] if row else ""

        cursor.execute("""
            SELECT customer_id, first_name || ' ' || last_name FROM customers
            WHERE is_deleted = 0 ORDER BY last_name
        """)
        customers = cursor.fetchall()
        cursor.execute("""
            SELECT class_id, class_name || ' (' || class_day || ' ' || class_time || ')'
            FROM classes WHERE is_active = 1 AND is_deleted = 0 ORDER BY class_name
        """)
        classes = cursor.fetchall()
        connection.close()

        dialog = tk.Toplevel(self.root)
        dialog.title("Edit Booking")
        dialog.geometry("500x500")
        dialog.configure(bg='#0f1c2e')
        dialog.transient(self.root)
        dialog.grab_set()

        fields_frame = tk.Frame(dialog, bg='#0f1c2e', padx=20, pady=20)
        fields_frame.pack(expand=True, fill='both')

        entries = {}

        tk.Label(fields_frame, text="Customer:", bg='#0f1c2e',
                 fg='white').grid(row=0, column=0, sticky='w', pady=5)
        entries['customer'] = ttk.Combobox(fields_frame,
                                           values=[name for _, name in customers])
        entries['customer'].set(customer_name)
        entries['customer'].grid(row=0, column=1, pady=5, padx=10, sticky='ew')

        tk.Label(fields_frame, text="Class:", bg='#0f1c2e',
                 fg='white').grid(row=1, column=0, sticky='w', pady=5)
        entries['class'] = ttk.Combobox(fields_frame,
                                        values=[name for _, name in classes])
        entries['class'].set(class_name)
        entries['class'].grid(row=1, column=1, pady=5, padx=10, sticky='ew')

        tk.Label(fields_frame, text="Cost (GBP):", bg='#0f1c2e',
                 fg='white').grid(row=2, column=0, sticky='w', pady=5)
        entries['cost'] = tk.Entry(fields_frame, width=30, bg='#2c3e50',
                                   fg='white', insertbackground='white')
        entries['cost'].insert(0, str(booking_data[2]))
        entries['cost'].grid(row=2, column=1, pady=5, padx=10, sticky='ew')

        tk.Label(fields_frame, text="Paid:", bg='#0f1c2e',
                 fg='white').grid(row=3, column=0, sticky='w', pady=5)
        entries['paid'] = ttk.Combobox(fields_frame, values=['Yes', 'No'])
        entries['paid'].set('Yes' if booking_data[3] == 1 else 'No')
        entries['paid'].grid(row=3, column=1, pady=5, padx=10, sticky='ew')

        tk.Label(fields_frame, text="Payment Date:", bg='#0f1c2e',
                 fg='white').grid(row=4, column=0, sticky='w', pady=5)
        if DateEntry:
            entries['payment_date'] = DateEntry(fields_frame, width=27,
                                                background='#f39c12',
                                                foreground='white', borderwidth=2,
                                                date_pattern='yyyy-mm-dd')
            if booking_data[4]:
                try:
                    entries['payment_date'].set_date(
                        datetime.strptime(booking_data[4], '%Y-%m-%d'))
                except Exception:
                    pass
        else:
            entries['payment_date'] = tk.Entry(fields_frame, width=30, bg='#2c3e50',
                                               fg='white', insertbackground='white')
            if booking_data[4]:
                entries['payment_date'].insert(0, booking_data[4])
        entries['payment_date'].grid(row=4, column=1, pady=5, padx=10, sticky='ew')

        tk.Label(fields_frame, text="Attendance Status:", bg='#0f1c2e',
                 fg='white').grid(row=5, column=0, sticky='w', pady=5)
        entries['attendance'] = ttk.Combobox(
            fields_frame,
            values=['Booked', 'Attended', 'Cancelled', 'No-Show'])
        entries['attendance'].set(booking_data[5])
        entries['attendance'].grid(row=5, column=1, pady=5, padx=10, sticky='ew')

        tk.Label(fields_frame, text="Notes:", bg='#0f1c2e',
                 fg='white').grid(row=6, column=0, sticky='w', pady=5)
        entries['notes'] = tk.Text(fields_frame, width=30, height=4, bg='#2c3e50',
                                   fg='white', insertbackground='white')
        entries['notes'].grid(row=6, column=1, pady=5, padx=10, sticky='ew')
        entries['notes'].insert('1.0', booking_data[6] or '')

        def update_booking():
            try:
                old_values = (f"Customer: {customer_name}, Class: {class_name}, "
                              f"Status: {booking_data[5]}")

                new_customer_name = entries['customer'].get()
                new_customer_id = next((cid for cid, cname in customers
                                        if cname == new_customer_name), None)

                new_class_name = entries['class'].get()
                new_class_id = next((cid for cid, cname in classes
                                     if cname == new_class_name), None)

                connection = sqlite3.connect("glen10_gym.db")
                cursor = connection.cursor()

                payment_date = None
                if entries['paid'].get() == 'Yes':
                    if DateEntry:
                        payment_date = entries['payment_date'].get_date()
                    else:
                        payment_date = entries['payment_date'].get() or None

                cursor.execute("""
                    UPDATE bookings SET
                    customer_id = ?, class_id = ?, cost = ?, paid = ?, payment_date = ?,
                    attendance_status = ?, notes = ?
                    WHERE booking_id = ?
                """, (
                    new_customer_id, new_class_id,
                    float(entries['cost'].get()),
                    1 if entries['paid'].get() == 'Yes' else 0,
                    payment_date,
                    entries['attendance'].get(),
                    entries['notes'].get('1.0', tk.END).strip(),
                    booking_id
                ))

                # Adjust enrollment if class changed
                if new_class_id != booking_data[1]:
                    cursor.execute("""
                        UPDATE classes SET current_enrollment = MAX(current_enrollment - 1, 0)
                        WHERE class_id = ?
                    """, (booking_data[1],))
                    cursor.execute("""
                        UPDATE classes SET current_enrollment = current_enrollment + 1
                        WHERE class_id = ?
                    """, (new_class_id,))

                connection.commit()
                connection.close()

                new_values = (f"Customer: {new_customer_name}, "
                              f"Class: {new_class_name}, "
                              f"Status: {entries['attendance'].get()}")
                log_audit_action(self.user_data['staff_id'], self.user_data['full_name'],
                                 'UPDATE', 'bookings', booking_id, old_values, new_values)

                messagebox.showinfo("Success", "Booking updated successfully!")
                dialog.destroy()
                self.load_booking_data()
            except Exception as e:
                messagebox.showerror("Error", f"Failed to update booking: {str(e)}")

        button_frame = tk.Frame(dialog, bg='#0f1c2e', pady=10)
        button_frame.pack(fill='x')
        tk.Button(button_frame, text="Update", bg='#27ae60', fg='white',
                  command=update_booking, relief='flat',
                  padx=20, pady=8).pack(side='left', padx=5)
        tk.Button(button_frame, text="Cancel", bg='#95a5a6', fg='white',
                  command=dialog.destroy, relief='flat',
                  padx=20, pady=8).pack(side='left', padx=5)

    def archive_booking(self):
        selection = self.tree.selection()
        if not selection:
            messagebox.showwarning("No Selection", "Please select a booking to archive")
            return

        item = self.tree.item(selection[0])
        booking_id = item['values'][0]
        customer_name = item['values'][1]
        class_name = item['values'][2]

        if not messagebox.askyesno(
                "Confirm Archive",
                f"Archive booking for {customer_name} - {class_name}?\n\n"
                f"This will move the booking to the recycle bin where it can be restored later."):
            return

        # FIX: roll back enrollment when archiving so capacity counts stay accurate
        try:
            connection = sqlite3.connect("glen10_gym.db")
            cursor = connection.cursor()
            cursor.execute("SELECT class_id FROM bookings WHERE booking_id = ?", (booking_id,))
            row = cursor.fetchone()
            class_id_for_booking = row[0] if row else None
            connection.close()
        except Exception:
            class_id_for_booking = None

        if soft_delete_record(self.user_data['staff_id'],
                              self.user_data['full_name'], 'bookings', booking_id):
            if class_id_for_booking is not None:
                try:
                    connection = sqlite3.connect("glen10_gym.db")
                    cursor = connection.cursor()
                    cursor.execute("""
                        UPDATE classes
                        SET current_enrollment = MAX(current_enrollment - 1, 0)
                        WHERE class_id = ?
                    """, (class_id_for_booking,))
                    connection.commit()
                    connection.close()
                except Exception as e:
                    print(f"Could not adjust class enrollment: {e}")

            messagebox.showinfo("Success", "Booking archived successfully")
            self.load_booking_data()
        else:
            messagebox.showerror("Error", "Failed to archive booking")

    def return_to_dashboard(self):
        for widget in self.root.winfo_children():
            widget.destroy()
        self.return_callback()


####################################################################################
# INVOICE MANAGEMENT
####################################################################################

class InvoiceManagement:
    def __init__(self, root, return_callback, user_data):
        self.root = root
        self.return_callback = return_callback
        self.user_data = user_data

        self.can_add = check_permission(self.user_data['job_title'], 'invoices', 'add')
        self.can_edit = check_permission(self.user_data['job_title'], 'invoices', 'edit')
        self.can_delete = check_permission(self.user_data['job_title'], 'invoices', 'delete')

        for widget in self.root.winfo_children():
            widget.destroy()

        header_frame = tk.Frame(self.root, bg='#1a2b3e', height=80)
        header_frame.pack(fill='x')
        header_frame.pack_propagate(False)
        tk.Label(header_frame, text="Invoice Management", font=('Arial Black', 20),
                 bg='#1a2b3e', fg='white').pack(side='left', padx=20)
        tk.Button(header_frame, text="< Back to Dashboard", font=('Arial', 10),
                  bg='#3498db', fg='white', relief='flat',
                  command=self.return_to_dashboard,
                  padx=15).pack(side='right', padx=20)

        control_frame = tk.Frame(self.root, bg='#0f1c2e', padx=20, pady=10)
        control_frame.pack(fill='x')

        if self.can_add:
            tk.Button(control_frame, text="+ Add New Invoice", bg='#27ae60', fg='white',
                      command=self.add_invoice, relief='flat',
                      padx=15, pady=8).pack(side='left', padx=5)
        if self.can_edit:
            tk.Button(control_frame, text="Edit Invoice", bg='#f39c12', fg='white',
                      command=self.edit_invoice, relief='flat',
                      padx=15, pady=8).pack(side='left', padx=5)
        if self.can_delete:
            tk.Button(control_frame, text="Archive Invoice", bg='#e74c3c', fg='white',
                      command=self.archive_invoice, relief='flat',
                      padx=15, pady=8).pack(side='left', padx=5)

        filter_frame = tk.Frame(control_frame, bg='#0f1c2e')
        filter_frame.pack(side='right', padx=10)
        tk.Label(filter_frame, text="Status:", bg='#0f1c2e', fg='white').pack(side='left')
        self.status_filter = ttk.Combobox(
            filter_frame,
            values=['All', 'Pending', 'Paid', 'Overdue'], width=12)
        self.status_filter.pack(side='left', padx=5)
        self.status_filter.set('All')
        self.status_filter.bind('<<ComboboxSelected>>',
                                lambda e: self.load_invoice_data())

        search_frame = tk.Frame(control_frame, bg='#0f1c2e')
        search_frame.pack(side='right', padx=10)
        tk.Label(search_frame, text="Search:", bg='#0f1c2e', fg='white').pack(side='left')
        self.search_var = tk.StringVar()
        search_entry = tk.Entry(search_frame, textvariable=self.search_var, width=30,
                                bg='#2c3e50', fg='white', insertbackground='white')
        search_entry.pack(side='left', padx=5)
        search_entry.bind('<KeyRelease>', self.search_invoices)

        table_frame = tk.Frame(self.root, bg='#1a2b3e')
        table_frame.pack(expand=True, fill='both', padx=20, pady=10)

        columns = ('ID', 'Customer', 'Invoice Date', 'Due Date', 'Amount',
                   'Status', 'Payment Method', 'Payment Date', 'Description')
        self.tree = ttk.Treeview(table_frame, columns=columns,
                                 show='headings', height=15)

        style = ttk.Style()
        style.theme_use('clam')
        style.configure("Treeview", background="#2c3e50", foreground="white",
                        fieldbackground="#2c3e50", borderwidth=0)
        style.configure("Treeview.Heading", background="#9b59b6",
                        foreground="white", relief="flat")
        style.map("Treeview", background=[('selected', '#9b59b6')])

        widths = [50, 120, 100, 100, 80, 80, 100, 100, 150]
        for i, col in enumerate(columns):
            self.tree.heading(col, text=col)
            self.tree.column(col, width=widths[i])

        scrollbar = ttk.Scrollbar(table_frame, orient=tk.VERTICAL, command=self.tree.yview)
        self.tree.configure(yscrollcommand=scrollbar.set)
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
        self.tree.pack(side=tk.LEFT, expand=True, fill='both')

        self.load_invoice_data()

    def load_invoice_data(self, search_term=""):
        for item in self.tree.get_children():
            self.tree.delete(item)

        connection = sqlite3.connect("glen10_gym.db")
        cursor = connection.cursor()
        status_filter = self.status_filter.get()

        if search_term:
            base = """
                SELECT i.invoice_id,
                       c.first_name || ' ' || c.last_name,
                       i.invoice_date, i.due_date, i.amount,
                       i.payment_status, i.payment_method,
                       i.payment_date, i.description
                FROM invoices i
                JOIN customers c ON i.customer_id = c.customer_id
                WHERE (c.first_name LIKE ? OR c.last_name LIKE ? OR i.description LIKE ?
                       OR i.payment_method LIKE ?) AND i.is_deleted = 0
            """
            params = [f'%{search_term}%'] * 4
            if status_filter != 'All':
                base += " AND i.payment_status = ?"
                params.append(status_filter)
            base += " ORDER BY i.invoice_date DESC"
            cursor.execute(base, params)
        else:
            if status_filter != 'All':
                cursor.execute("""
                    SELECT i.invoice_id,
                           c.first_name || ' ' || c.last_name,
                           i.invoice_date, i.due_date, i.amount,
                           i.payment_status, i.payment_method,
                           i.payment_date, i.description
                    FROM invoices i
                    JOIN customers c ON i.customer_id = c.customer_id
                    WHERE i.payment_status = ? AND i.is_deleted = 0
                    ORDER BY i.invoice_date DESC
                """, (status_filter,))
            else:
                cursor.execute("""
                    SELECT i.invoice_id,
                           c.first_name || ' ' || c.last_name,
                           i.invoice_date, i.due_date, i.amount,
                           i.payment_status, i.payment_method,
                           i.payment_date, i.description
                    FROM invoices i
                    JOIN customers c ON i.customer_id = c.customer_id
                    WHERE i.is_deleted = 0
                    ORDER BY i.invoice_date DESC
                """)

        for row in cursor.fetchall():
            self.tree.insert('', tk.END, values=row)
        connection.close()

    def search_invoices(self, event=None):
        self.load_invoice_data(self.search_var.get())

    def add_invoice(self):
        dialog = tk.Toplevel(self.root)
        dialog.title("Add New Invoice")
        dialog.geometry("500x500")
        dialog.configure(bg='#0f1c2e')
        dialog.transient(self.root)
        dialog.grab_set()

        fields_frame = tk.Frame(dialog, bg='#0f1c2e', padx=20, pady=20)
        fields_frame.pack(expand=True, fill='both')

        entries = {}

        connection = sqlite3.connect("glen10_gym.db")
        cursor = connection.cursor()
        cursor.execute("""
            SELECT customer_id, first_name || ' ' || last_name FROM customers
            WHERE is_deleted = 0 ORDER BY last_name
        """)
        customers = cursor.fetchall()
        connection.close()

        tk.Label(fields_frame, text="Customer:", bg='#0f1c2e',
                 fg='white').grid(row=0, column=0, sticky='w', pady=5)
        entries['customer'] = ttk.Combobox(fields_frame,
                                           values=[name for _, name in customers])
        entries['customer'].grid(row=0, column=1, pady=5, padx=10, sticky='ew')

        tk.Label(fields_frame, text="Amount (GBP):", bg='#0f1c2e',
                 fg='white').grid(row=1, column=0, sticky='w', pady=5)
        entries['amount'] = tk.Entry(fields_frame, width=30, bg='#2c3e50',
                                     fg='white', insertbackground='white')
        entries['amount'].insert(0, "50.00")
        entries['amount'].grid(row=1, column=1, pady=5, padx=10, sticky='ew')

        tk.Label(fields_frame, text="Invoice Date:", bg='#0f1c2e',
                 fg='white').grid(row=2, column=0, sticky='w', pady=5)
        if DateEntry:
            entries['invoice_date'] = DateEntry(fields_frame, width=27,
                                                background='#9b59b6',
                                                foreground='white', borderwidth=2,
                                                date_pattern='yyyy-mm-dd')
            entries['invoice_date'].set_date(datetime.now())
        else:
            entries['invoice_date'] = tk.Entry(fields_frame, width=30, bg='#2c3e50',
                                               fg='white', insertbackground='white')
            entries['invoice_date'].insert(0, datetime.now().strftime('%Y-%m-%d'))
        entries['invoice_date'].grid(row=2, column=1, pady=5, padx=10, sticky='ew')

        tk.Label(fields_frame, text="Due Date:", bg='#0f1c2e',
                 fg='white').grid(row=3, column=0, sticky='w', pady=5)
        if DateEntry:
            entries['due_date'] = DateEntry(fields_frame, width=27, background='#9b59b6',
                                            foreground='white', borderwidth=2,
                                            date_pattern='yyyy-mm-dd')
            entries['due_date'].set_date(datetime.now() + timedelta(days=30))
        else:
            entries['due_date'] = tk.Entry(fields_frame, width=30, bg='#2c3e50',
                                           fg='white', insertbackground='white')
            entries['due_date'].insert(
                0, (datetime.now() + timedelta(days=30)).strftime('%Y-%m-%d'))
        entries['due_date'].grid(row=3, column=1, pady=5, padx=10, sticky='ew')

        tk.Label(fields_frame, text="Payment Status:", bg='#0f1c2e',
                 fg='white').grid(row=4, column=0, sticky='w', pady=5)
        entries['status'] = ttk.Combobox(
            fields_frame,
            values=['Pending', 'Paid', 'Overdue', 'Cancelled'])
        entries['status'].set('Pending')
        entries['status'].grid(row=4, column=1, pady=5, padx=10, sticky='ew')

        tk.Label(fields_frame, text="Payment Method:", bg='#0f1c2e',
                 fg='white').grid(row=5, column=0, sticky='w', pady=5)
        entries['payment_method'] = ttk.Combobox(
            fields_frame,
            values=['Cash', 'Card', 'Bank Transfer', 'Direct Debit', 'Other'])
        entries['payment_method'].grid(row=5, column=1, pady=5, padx=10, sticky='ew')

        tk.Label(fields_frame, text="Payment Date:", bg='#0f1c2e',
                 fg='white').grid(row=6, column=0, sticky='w', pady=5)
        if DateEntry:
            entries['payment_date'] = DateEntry(fields_frame, width=27,
                                                background='#9b59b6',
                                                foreground='white', borderwidth=2,
                                                date_pattern='yyyy-mm-dd')
        else:
            entries['payment_date'] = tk.Entry(fields_frame, width=30, bg='#2c3e50',
                                               fg='white', insertbackground='white')
        entries['payment_date'].grid(row=6, column=1, pady=5, padx=10, sticky='ew')

        tk.Label(fields_frame, text="Description:", bg='#0f1c2e',
                 fg='white').grid(row=7, column=0, sticky='w', pady=5)
        entries['description'] = tk.Entry(fields_frame, width=30, bg='#2c3e50',
                                          fg='white', insertbackground='white')
        entries['description'].insert(0, "Monthly Membership Fee")
        entries['description'].grid(row=7, column=1, pady=5, padx=10, sticky='ew')

        def save_invoice():
            try:
                customer_name = entries['customer'].get()
                customer_id = next((cid for cid, cname in customers
                                    if cname == customer_name), None)
                if not customer_id:
                    messagebox.showerror("Error", "Please select a customer")
                    return

                connection = sqlite3.connect("glen10_gym.db")
                cursor = connection.cursor()

                invoice_date = (entries['invoice_date'].get_date()
                                if DateEntry else entries['invoice_date'].get())
                due_date = (entries['due_date'].get_date()
                            if DateEntry else entries['due_date'].get())

                payment_date = None
                if entries['status'].get() == 'Paid':
                    if DateEntry:
                        payment_date = entries['payment_date'].get_date()
                    else:
                        payment_date = entries['payment_date'].get() or None

                cursor.execute("""
                    INSERT INTO invoices (customer_id, invoice_date, due_date, amount,
                                          payment_status, payment_method, payment_date, description)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                """, (
                    customer_id, invoice_date, due_date,
                    float(entries['amount'].get()),
                    entries['status'].get(),
                    entries['payment_method'].get(),
                    payment_date,
                    entries['description'].get()
                ))
                invoice_id = cursor.lastrowid
                connection.commit()
                connection.close()

                log_audit_action(self.user_data['staff_id'], self.user_data['full_name'],
                                 'INSERT', 'invoices', invoice_id, None,
                                 f"Invoice #{invoice_id} for {customer_name} - "
                                 f"GBP {entries['amount'].get()}")

                messagebox.showinfo("Success", "Invoice added successfully!")
                dialog.destroy()
                self.load_invoice_data()
            except Exception as e:
                messagebox.showerror("Error", f"Failed to add invoice: {str(e)}")

        button_frame = tk.Frame(dialog, bg='#0f1c2e', pady=10)
        button_frame.pack(fill='x')
        tk.Button(button_frame, text="Save", bg='#27ae60', fg='white',
                  command=save_invoice, relief='flat',
                  padx=20, pady=8).pack(side='left', padx=20)
        tk.Button(button_frame, text="Cancel", bg='#95a5a6', fg='white',
                  command=dialog.destroy, relief='flat',
                  padx=20, pady=8).pack(side='left', padx=5)

    def edit_invoice(self):
        selection = self.tree.selection()
        if not selection:
            messagebox.showwarning("No Selection", "Please select an invoice to edit")
            return

        item = self.tree.item(selection[0])
        invoice_id = item['values'][0]

        connection = sqlite3.connect("glen10_gym.db")
        cursor = connection.cursor()
        cursor.execute("""
            SELECT customer_id, invoice_date, due_date, amount, payment_status,
                   payment_method, payment_date, description
            FROM invoices WHERE invoice_id = ? AND is_deleted = 0
        """, (invoice_id,))
        invoice_data = cursor.fetchone()

        if not invoice_data:
            connection.close()
            messagebox.showerror("Error", "Invoice not found or has been deleted!")
            return

        cursor.execute("SELECT first_name || ' ' || last_name FROM customers WHERE customer_id = ?",
                       (invoice_data[0],))
        row = cursor.fetchone()
        customer_name = row[0] if row else ""

        cursor.execute("""
            SELECT customer_id, first_name || ' ' || last_name FROM customers
            WHERE is_deleted = 0 ORDER BY last_name
        """)
        customers = cursor.fetchall()
        connection.close()

        dialog = tk.Toplevel(self.root)
        dialog.title("Edit Invoice")
        dialog.geometry("500x500")
        dialog.configure(bg='#0f1c2e')
        dialog.transient(self.root)
        dialog.grab_set()

        fields_frame = tk.Frame(dialog, bg='#0f1c2e', padx=20, pady=20)
        fields_frame.pack(expand=True, fill='both')

        entries = {}

        tk.Label(fields_frame, text="Customer:", bg='#0f1c2e',
                 fg='white').grid(row=0, column=0, sticky='w', pady=5)
        entries['customer'] = ttk.Combobox(fields_frame,
                                           values=[name for _, name in customers])
        entries['customer'].set(customer_name)
        entries['customer'].grid(row=0, column=1, pady=5, padx=10, sticky='ew')

        tk.Label(fields_frame, text="Amount (GBP):", bg='#0f1c2e',
                 fg='white').grid(row=1, column=0, sticky='w', pady=5)
        entries['amount'] = tk.Entry(fields_frame, width=30, bg='#2c3e50',
                                     fg='white', insertbackground='white')
        entries['amount'].insert(0, str(invoice_data[3]))
        entries['amount'].grid(row=1, column=1, pady=5, padx=10, sticky='ew')

        tk.Label(fields_frame, text="Invoice Date:", bg='#0f1c2e',
                 fg='white').grid(row=2, column=0, sticky='w', pady=5)
        if DateEntry:
            entries['invoice_date'] = DateEntry(fields_frame, width=27,
                                                background='#9b59b6',
                                                foreground='white', borderwidth=2,
                                                date_pattern='yyyy-mm-dd')
            try:
                entries['invoice_date'].set_date(
                    datetime.strptime(invoice_data[1], '%Y-%m-%d'))
            except Exception:
                entries['invoice_date'].set_date(datetime.now())
        else:
            entries['invoice_date'] = tk.Entry(fields_frame, width=30, bg='#2c3e50',
                                               fg='white', insertbackground='white')
            entries['invoice_date'].insert(0, invoice_data[1])
        entries['invoice_date'].grid(row=2, column=1, pady=5, padx=10, sticky='ew')

        tk.Label(fields_frame, text="Due Date:", bg='#0f1c2e',
                 fg='white').grid(row=3, column=0, sticky='w', pady=5)
        if DateEntry:
            entries['due_date'] = DateEntry(fields_frame, width=27, background='#9b59b6',
                                            foreground='white', borderwidth=2,
                                            date_pattern='yyyy-mm-dd')
            try:
                entries['due_date'].set_date(
                    datetime.strptime(invoice_data[2], '%Y-%m-%d'))
            except Exception:
                entries['due_date'].set_date(datetime.now() + timedelta(days=30))
        else:
            entries['due_date'] = tk.Entry(fields_frame, width=30, bg='#2c3e50',
                                           fg='white', insertbackground='white')
            entries['due_date'].insert(0, invoice_data[2])
        entries['due_date'].grid(row=3, column=1, pady=5, padx=10, sticky='ew')

        tk.Label(fields_frame, text="Payment Status:", bg='#0f1c2e',
                 fg='white').grid(row=4, column=0, sticky='w', pady=5)
        entries['status'] = ttk.Combobox(
            fields_frame,
            values=['Pending', 'Paid', 'Overdue', 'Cancelled'])
        entries['status'].set(invoice_data[4])
        entries['status'].grid(row=4, column=1, pady=5, padx=10, sticky='ew')

        tk.Label(fields_frame, text="Payment Method:", bg='#0f1c2e',
                 fg='white').grid(row=5, column=0, sticky='w', pady=5)
        entries['payment_method'] = ttk.Combobox(
            fields_frame,
            values=['Cash', 'Card', 'Bank Transfer', 'Direct Debit', 'Other'])
        entries['payment_method'].set(invoice_data[5] or '')
        entries['payment_method'].grid(row=5, column=1, pady=5, padx=10, sticky='ew')

        tk.Label(fields_frame, text="Payment Date:", bg='#0f1c2e',
                 fg='white').grid(row=6, column=0, sticky='w', pady=5)
        if DateEntry:
            entries['payment_date'] = DateEntry(fields_frame, width=27,
                                                background='#9b59b6',
                                                foreground='white', borderwidth=2,
                                                date_pattern='yyyy-mm-dd')
            if invoice_data[6]:
                try:
                    entries['payment_date'].set_date(
                        datetime.strptime(invoice_data[6], '%Y-%m-%d'))
                except Exception:
                    pass
        else:
            entries['payment_date'] = tk.Entry(fields_frame, width=30, bg='#2c3e50',
                                               fg='white', insertbackground='white')
            if invoice_data[6]:
                entries['payment_date'].insert(0, invoice_data[6])
        entries['payment_date'].grid(row=6, column=1, pady=5, padx=10, sticky='ew')

        tk.Label(fields_frame, text="Description:", bg='#0f1c2e',
                 fg='white').grid(row=7, column=0, sticky='w', pady=5)
        entries['description'] = tk.Entry(fields_frame, width=30, bg='#2c3e50',
                                          fg='white', insertbackground='white')
        entries['description'].insert(0, invoice_data[7] or '')
        entries['description'].grid(row=7, column=1, pady=5, padx=10, sticky='ew')

        def update_invoice():
            try:
                old_values = (f"Customer: {customer_name}, Amount: GBP {invoice_data[3]}, "
                              f"Status: {invoice_data[4]}")

                new_customer_name = entries['customer'].get()
                new_customer_id = next((cid for cid, cname in customers
                                        if cname == new_customer_name), None)

                connection = sqlite3.connect("glen10_gym.db")
                cursor = connection.cursor()

                invoice_date = (entries['invoice_date'].get_date()
                                if DateEntry else entries['invoice_date'].get())
                due_date = (entries['due_date'].get_date()
                            if DateEntry else entries['due_date'].get())
                payment_date = None
                if entries['status'].get() == 'Paid':
                    if DateEntry:
                        payment_date = entries['payment_date'].get_date()
                    else:
                        payment_date = entries['payment_date'].get() or None

                cursor.execute("""
                    UPDATE invoices SET
                    customer_id = ?, invoice_date = ?, due_date = ?, amount = ?,
                    payment_status = ?, payment_method = ?, payment_date = ?, description = ?
                    WHERE invoice_id = ?
                """, (
                    new_customer_id, invoice_date, due_date,
                    float(entries['amount'].get()),
                    entries['status'].get(),
                    entries['payment_method'].get(),
                    payment_date,
                    entries['description'].get(),
                    invoice_id
                ))
                connection.commit()
                connection.close()

                new_values = (f"Customer: {new_customer_name}, "
                              f"Amount: GBP {entries['amount'].get()}, "
                              f"Status: {entries['status'].get()}")
                log_audit_action(self.user_data['staff_id'], self.user_data['full_name'],
                                 'UPDATE', 'invoices', invoice_id, old_values, new_values)

                messagebox.showinfo("Success", "Invoice updated successfully!")
                dialog.destroy()
                self.load_invoice_data()
            except Exception as e:
                messagebox.showerror("Error", f"Failed to update invoice: {str(e)}")

        button_frame = tk.Frame(dialog, bg='#0f1c2e', pady=10)
        button_frame.pack(fill='x')
        tk.Button(button_frame, text="Update", bg='#27ae60', fg='white',
                  command=update_invoice, relief='flat',
                  padx=20, pady=8).pack(side='left', padx=5)
        tk.Button(button_frame, text="Cancel", bg='#95a5a6', fg='white',
                  command=dialog.destroy, relief='flat',
                  padx=20, pady=8).pack(side='left', padx=5)

    def archive_invoice(self):
        selection = self.tree.selection()
        if not selection:
            messagebox.showwarning("No Selection", "Please select an invoice to archive")
            return

        item = self.tree.item(selection[0])
        invoice_id = item['values'][0]
        customer_name = item['values'][1]
        amount = item['values'][4]

        if messagebox.askyesno("Confirm Archive",
                               f"Archive invoice #{invoice_id} for {customer_name} - "
                               f"GBP {amount}?\n\nThis will move the invoice to the recycle bin "
                               f"where it can be restored later."):
            if soft_delete_record(self.user_data['staff_id'],
                                  self.user_data['full_name'], 'invoices', invoice_id):
                messagebox.showinfo("Success", "Invoice archived successfully")
                self.load_invoice_data()
            else:
                messagebox.showerror("Error", "Failed to archive invoice")

    def return_to_dashboard(self):
        for widget in self.root.winfo_children():
            widget.destroy()
        self.return_callback()


####################################################################################
# REPORTS DASHBOARD
####################################################################################

class ReportsDashboard:
    def __init__(self, root, return_callback, user_data):
        self.root = root
        self.return_callback = return_callback
        self.user_data = user_data

        for widget in self.root.winfo_children():
            widget.destroy()

        header_frame = tk.Frame(self.root, bg='#1a2b3e', height=80)
        header_frame.pack(fill='x')
        header_frame.pack_propagate(False)
        tk.Label(header_frame, text="Reports Dashboard", font=('Arial Black', 20),
                 bg='#1a2b3e', fg='white').pack(side='left', padx=20)
        tk.Button(header_frame, text="< Back to Dashboard", font=('Arial', 10),
                  bg='#3498db', fg='white', relief='flat',
                  command=self.return_to_dashboard,
                  padx=15).pack(side='right', padx=20)

        content_frame = tk.Frame(self.root, bg='#0f1c2e', padx=20, pady=20)
        content_frame.pack(expand=True, fill='both')

        stats = get_dashboard_stats()

        stats_frame = tk.Frame(content_frame, bg='#0f1c2e')
        stats_frame.pack(fill='x', pady=(0, 20))

        stat_cards = [
            ("Total Members", stats['total_members'], '#3498db'),
            ("Active Staff", stats['total_staff'], '#2ecc71'),
            ("Classes Today", stats['classes_today'], '#e74c3c'),
            ("Monthly Revenue", f"GBP {stats['monthly_revenue']:.2f}", '#f39c12'),
            ("Today's Bookings", stats['today_bookings'], '#9b59b6'),
            ("Member Status",
             f"A: {stats['active_members']} | I: {stats['inactive_members']}", '#1abc9c'),
        ]

        for i, (title, value, color) in enumerate(stat_cards):
            card_frame = tk.Frame(stats_frame, bg=color, relief='flat', bd=0)
            card_frame.grid(row=i // 3, column=i % 3, padx=10, pady=10, sticky='nsew')
            stats_frame.columnconfigure(i % 3, weight=1)
            stats_frame.rowconfigure(i // 3, weight=1)
            tk.Label(card_frame, text=title, font=('Arial', 11, 'bold'),
                     bg=color, fg='white').pack(pady=(10, 5))
            tk.Label(card_frame, text=str(value), font=('Arial', 16, 'bold'),
                     bg=color, fg='white').pack(pady=(0, 10))

        reports_frame = tk.Frame(content_frame, bg='#0f1c2e')
        reports_frame.pack(fill='both', expand=True)

        report_types = [
            ("Membership Report", self.generate_membership_report),
            ("Class Schedule", self.generate_class_schedule),
            ("Financial Report", self.generate_financial_report),
            ("Attendance Report", self.generate_attendance_report),
            ("Revenue Trends", self.generate_revenue_trends),
            ("Staff Performance", self.generate_staff_report),
            ("Deleted Items Report", self.generate_deleted_report),
            ("Audit Log Summary", self.generate_audit_summary),
        ]

        for i, (text, command) in enumerate(report_types):
            btn = tk.Button(reports_frame, text=text, font=('Arial', 11),
                            bg='#34495e', fg='white', command=command,
                            height=2, width=25, relief='flat')
            btn.grid(row=i // 2, column=i % 2, padx=10, pady=10, sticky='nsew')
            reports_frame.columnconfigure(i % 2, weight=1)
            reports_frame.rowconfigure(i // 2, weight=1)

    def _open_text_window(self, title, geometry="700x500"):
        window = tk.Toplevel(self.root)
        window.title(title)
        window.geometry(geometry)
        window.configure(bg='#0f1c2e')
        text = scrolledtext.ScrolledText(window, width=90, height=25, bg='#2c3e50',
                                         fg='white', insertbackground='white')
        text.pack(padx=10, pady=10, fill='both', expand=True)
        return text

    def generate_membership_report(self):
        connection = sqlite3.connect("glen10_gym.db")
        cursor = connection.cursor()
        cursor.execute("""
            SELECT membership_type, COUNT(*),
                   SUM(CASE WHEN membership_status = 'Active' AND is_deleted = 0 THEN 1 ELSE 0 END),
                   SUM(CASE WHEN is_deleted = 1 THEN 1 ELSE 0 END)
            FROM customers
            GROUP BY membership_type
        """)
        rows = cursor.fetchall()
        connection.close()

        text = self._open_text_window("Membership Report", "600x400")
        text.insert(tk.END, "GLEN10 GYM - MEMBERSHIP REPORT\n")
        text.insert(tk.END, "=" * 40 + "\n\n")
        text.insert(tk.END, f"Generated: {datetime.now().strftime('%d/%m/%Y %H:%M')}\n")
        text.insert(tk.END, f"Generated by: {self.user_data['full_name']}\n\n")
        text.insert(tk.END, "Membership Type Breakdown:\n")
        text.insert(tk.END, "-" * 30 + "\n")

        total = 0
        active = 0
        deleted = 0
        for membership_type, count, active_count, deleted_count in rows:
            active_count = active_count or 0
            deleted_count = deleted_count or 0
            text.insert(tk.END, f"{membership_type}:\n")
            text.insert(tk.END, f"  Total Members: {count}\n")
            text.insert(tk.END, f"  Active Members: {active_count}\n")
            inactive = count - active_count - deleted_count
            text.insert(tk.END, f"  Inactive Members: {inactive}\n")
            text.insert(tk.END, f"  Archived Members: {deleted_count}\n\n")
            total += count
            active += active_count
            deleted += deleted_count

        activation_rate = (active / total * 100) if total > 0 else 0
        text.insert(tk.END, "\nOverall Statistics:\n")
        text.insert(tk.END, f"Total Members: {total}\n")
        text.insert(tk.END, f"Active Members: {active}\n")
        text.insert(tk.END, f"Archived Members: {deleted}\n")
        text.insert(tk.END, f"Activation Rate: {activation_rate:.1f}%\n")

    def generate_class_schedule(self):
        connection = sqlite3.connect("glen10_gym.db")
        cursor = connection.cursor()
        cursor.execute("""
            SELECT class_name, class_day, class_time, duration_minutes,
                   COALESCE(s.first_name || ' ' || s.last_name, 'Not Assigned'),
                   current_enrollment, max_capacity,
                   CASE WHEN current_enrollment < max_capacity THEN 'Available' ELSE 'Full' END,
                   CASE WHEN is_active = 1 THEN 'Active' ELSE 'Inactive' END
            FROM classes c
            LEFT JOIN staff s ON c.instructor_id = s.staff_id
            WHERE c.is_deleted = 0
            ORDER BY
                CASE class_day
                    WHEN 'Monday' THEN 1 WHEN 'Tuesday' THEN 2
                    WHEN 'Wednesday' THEN 3 WHEN 'Thursday' THEN 4
                    WHEN 'Friday' THEN 5 WHEN 'Saturday' THEN 6
                    WHEN 'Sunday' THEN 7
                END, class_time
        """)
        rows = cursor.fetchall()
        connection.close()

        text = self._open_text_window("Class Schedule Report", "800x500")
        text.insert(tk.END, "GLEN10 GYM - CLASS SCHEDULE\n")
        text.insert(tk.END, "=" * 50 + "\n\n")
        text.insert(tk.END, f"Generated: {datetime.now().strftime('%d/%m/%Y %H:%M')}\n\n")

        current_day = None
        for row in rows:
            day = row[1]
            if day != current_day:
                text.insert(tk.END, f"\n{day.upper()}:\n")
                text.insert(tk.END, "-" * 40 + "\n")
                current_day = day
            text.insert(tk.END, f"{row[2]} - {row[0]} ({row[3]} mins)\n")
            text.insert(tk.END, f"  Instructor: {row[4]}\n")
            text.insert(tk.END, f"  Enrollment: {row[5]}/{row[6]} ({row[7]})\n")
            text.insert(tk.END, f"  Status: {row[8]}\n\n")

    def generate_financial_report(self):
        connection = sqlite3.connect("glen10_gym.db")
        cursor = connection.cursor()
        cursor.execute("""
            SELECT strftime('%Y-%m', invoice_date) as month,
                   SUM(CASE WHEN payment_status = 'Paid' THEN amount ELSE 0 END) as revenue,
                   COUNT(*) as total_invoices,
                   SUM(CASE WHEN payment_status = 'Pending' THEN amount ELSE 0 END) as pending_amount,
                   SUM(CASE WHEN is_deleted = 1 THEN 1 ELSE 0 END) as deleted_invoices
            FROM invoices
            WHERE invoice_date >= date('now', '-6 months')
            GROUP BY strftime('%Y-%m', invoice_date)
            ORDER BY month DESC
        """)
        rows = cursor.fetchall()
        connection.close()

        text = self._open_text_window("Financial Report", "700x500")
        text.insert(tk.END, "GLEN10 GYM - FINANCIAL REPORT\n")
        text.insert(tk.END, "=" * 45 + "\n\n")
        text.insert(tk.END, f"Generated: {datetime.now().strftime('%d/%m/%Y %H:%M')}\n\n")
        text.insert(tk.END, "Monthly Revenue (Last 6 Months):\n")
        text.insert(tk.END, "-" * 40 + "\n")

        total_revenue = 0.0
        total_pending = 0.0
        total_deleted = 0
        for month, revenue, invoices, pending, deleted in rows:
            revenue = revenue or 0
            pending = pending or 0
            deleted = deleted or 0
            text.insert(tk.END, f"{month}:\n")
            text.insert(tk.END, f"  Revenue: GBP {revenue:,.2f}\n")
            text.insert(tk.END,
                        f"  Invoices: {invoices} (Active: {invoices - deleted}, "
                        f"Archived: {deleted})\n")
            text.insert(tk.END, f"  Pending Amount: GBP {pending:,.2f}\n\n")
            total_revenue += revenue
            total_pending += pending
            total_deleted += deleted

        text.insert(tk.END, "\nSummary:\n")
        text.insert(tk.END, f"Total Revenue (6 months): GBP {total_revenue:,.2f}\n")
        text.insert(tk.END, f"Average Monthly Revenue: GBP {(total_revenue / 6):,.2f}\n")
        text.insert(tk.END, f"Total Pending Amount: GBP {total_pending:,.2f}\n")
        text.insert(tk.END, f"Archived Invoices: {total_deleted}\n")

    def generate_attendance_report(self):
        connection = sqlite3.connect("glen10_gym.db")
        cursor = connection.cursor()
        cursor.execute("""
            SELECT attendance_status, COUNT(*) FROM bookings
            WHERE is_deleted = 0
            GROUP BY attendance_status
            ORDER BY attendance_status
        """)
        rows = cursor.fetchall()

        cursor.execute("""
            SELECT cl.class_name, COUNT(*) AS attendance_count
            FROM bookings b
            JOIN classes cl ON b.class_id = cl.class_id
            WHERE b.attendance_status = 'Attended' AND b.is_deleted = 0
            GROUP BY cl.class_id
            ORDER BY attendance_count DESC
            LIMIT 5
        """)
        top_classes = cursor.fetchall()
        connection.close()

        text = self._open_text_window("Attendance Report")
        text.insert(tk.END, "GLEN10 GYM - ATTENDANCE REPORT\n")
        text.insert(tk.END, "=" * 45 + "\n\n")
        text.insert(tk.END, f"Generated: {datetime.now().strftime('%d/%m/%Y %H:%M')}\n\n")
        text.insert(tk.END, "Bookings by Status:\n")
        text.insert(tk.END, "-" * 30 + "\n")
        total = 0
        for status, count in rows:
            text.insert(tk.END, f"  {status}: {count}\n")
            total += count
        text.insert(tk.END, f"\nTotal Bookings: {total}\n\n")

        text.insert(tk.END, "Top 5 Classes by Attendance:\n")
        text.insert(tk.END, "-" * 30 + "\n")
        if top_classes:
            for class_name, attendance_count in top_classes:
                text.insert(tk.END, f"  {class_name}: {attendance_count}\n")
        else:
            text.insert(tk.END, "  (no attendance data yet)\n")

    def generate_revenue_trends(self):
        connection = sqlite3.connect("glen10_gym.db")
        cursor = connection.cursor()
        cursor.execute("""
            SELECT strftime('%Y-%m', invoice_date) AS month,
                   SUM(CASE WHEN payment_status = 'Paid' THEN amount ELSE 0 END) AS revenue
            FROM invoices
            WHERE is_deleted = 0
            GROUP BY strftime('%Y-%m', invoice_date)
            ORDER BY month DESC
            LIMIT 12
        """)
        rows = cursor.fetchall()
        connection.close()

        text = self._open_text_window("Revenue Trends Report")
        text.insert(tk.END, "GLEN10 GYM - REVENUE TRENDS (LAST 12 MONTHS)\n")
        text.insert(tk.END, "=" * 50 + "\n\n")
        text.insert(tk.END, f"Generated: {datetime.now().strftime('%d/%m/%Y %H:%M')}\n\n")

        if not rows:
            text.insert(tk.END, "No invoice data available.\n")
            return

        max_rev = max((r[1] or 0) for r in rows) or 1
        text.insert(tk.END, f"{'Month':<10}{'Revenue':>12}   Trend\n")
        text.insert(tk.END, "-" * 60 + "\n")
        for month, revenue in reversed(rows):  # show oldest -> newest
            revenue = revenue or 0
            bar_len = int((revenue / max_rev) * 30) if max_rev > 0 else 0
            bar = '#' * bar_len
            text.insert(tk.END, f"{month:<10} GBP {revenue:>8,.2f}   {bar}\n")

    def generate_staff_report(self):
        connection = sqlite3.connect("glen10_gym.db")
        cursor = connection.cursor()
        cursor.execute("""
            SELECT s.staff_id, s.first_name || ' ' || s.last_name, s.job_title,
                   COUNT(c.class_id) AS classes_assigned,
                   COALESCE(SUM(c.current_enrollment), 0) AS total_enrolled
            FROM staff s
            LEFT JOIN classes c ON c.instructor_id = s.staff_id AND c.is_deleted = 0
            WHERE s.is_deleted = 0 AND s.status = 'Active'
            GROUP BY s.staff_id
            ORDER BY classes_assigned DESC
        """)
        rows = cursor.fetchall()
        connection.close()

        text = self._open_text_window("Staff Performance Report")
        text.insert(tk.END, "GLEN10 GYM - STAFF PERFORMANCE\n")
        text.insert(tk.END, "=" * 45 + "\n\n")
        text.insert(tk.END, f"Generated: {datetime.now().strftime('%d/%m/%Y %H:%M')}\n\n")
        text.insert(tk.END,
                    f"{'Name':<25}{'Job Title':<22}{'Classes':>8}{'Enrolled':>12}\n")
        text.insert(tk.END, "-" * 70 + "\n")
        for _sid, name, title, classes_assigned, total_enrolled in rows:
            text.insert(tk.END,
                        f"{name:<25}{title:<22}{classes_assigned:>8}{total_enrolled:>12}\n")

    def generate_deleted_report(self):
        try:
            text = self._open_text_window("Deleted Items Report")
            text.insert(tk.END, "GLEN10 GYM - DELETED ITEMS REPORT\n")
            text.insert(tk.END, "=" * 45 + "\n\n")
            text.insert(tk.END, f"Generated: {datetime.now().strftime('%d/%m/%Y %H:%M')}\n\n")

            tables = ['staff', 'customers', 'classes', 'bookings', 'invoices']
            for table in tables:
                text.insert(tk.END, f"{table.upper()}:\n")
                text.insert(tk.END, "-" * 20 + "\n")
                records = get_deleted_records(table)
                text.insert(tk.END, f"Total Archived: {len(records)}\n")

                for record in records[:5]:
                    if table == 'staff':
                        text.insert(tk.END, f"  {record[1]} {record[2]} ({record[5]})\n")
                    elif table == 'customers':
                        text.insert(tk.END, f"  {record[1]} {record[2]}\n")
                    elif table == 'classes':
                        text.insert(tk.END, f"  {record[1]} - {record[8]} {record[7]}\n")
                    elif table == 'bookings':
                        text.insert(tk.END, f"  Booking #{record[0]} - GBP {record[4]}\n")
                    elif table == 'invoices':
                        # FIX: invoices column 4 is amount (not [5] which is status)
                        text.insert(tk.END, f"  Invoice #{record[0]} - GBP {record[4]}\n")

                if len(records) > 5:
                    text.insert(tk.END, f"  ... and {len(records) - 5} more\n")
                text.insert(tk.END, "\n")
        except Exception as e:
            messagebox.showerror("Error", f"Failed to generate report: {str(e)}")

    def generate_audit_summary(self):
        try:
            logs = get_audit_logs(limit=200)
            text = self._open_text_window("Audit Log Summary")
            text.insert(tk.END, "GLEN10 GYM - AUDIT LOG SUMMARY\n")
            text.insert(tk.END, "=" * 45 + "\n\n")
            text.insert(tk.END, f"Generated: {datetime.now().strftime('%d/%m/%Y %H:%M')}\n\n")

            action_counts = {}
            user_counts = {}
            table_counts = {}

            for log in logs:
                action = log[2]
                user = log[1]
                table = log[3]
                action_counts[action] = action_counts.get(action, 0) + 1
                user_counts[user] = user_counts.get(user, 0) + 1
                table_counts[table] = table_counts.get(table, 0) + 1

            text.insert(tk.END, "Activity Summary:\n")
            text.insert(tk.END, "-" * 20 + "\n")
            text.insert(tk.END, f"Total Logs: {len(logs)}\n\n")

            text.insert(tk.END, "Actions by Type:\n")
            for action, count in sorted(action_counts.items(), key=lambda x: x[1], reverse=True):
                text.insert(tk.END, f"  {action}: {count}\n")

            text.insert(tk.END, "\nMost Active Users:\n")
            for user, count in sorted(user_counts.items(),
                                      key=lambda x: x[1], reverse=True)[:5]:
                text.insert(tk.END, f"  {user}: {count} actions\n")

            text.insert(tk.END, "\nTables with Most Activity:\n")
            for table, count in sorted(table_counts.items(),
                                       key=lambda x: x[1], reverse=True):
                text.insert(tk.END, f"  {table}: {count} actions\n")

            text.insert(tk.END, "\nRecent Activity:\n")
            text.insert(tk.END, "-" * 20 + "\n")
            for log in logs[:10]:
                try:
                    timestamp = datetime.strptime(
                        log[5], '%Y-%m-%d %H:%M:%S').strftime('%d/%m %H:%M')
                except Exception:
                    timestamp = str(log[5])
                text.insert(tk.END, f"{timestamp} - {log[1]} {log[2]} {log[3]} #{log[4]}\n")
        except Exception as e:
            messagebox.showerror("Error", f"Failed to generate audit summary: {str(e)}")

    def return_to_dashboard(self):
        for widget in self.root.winfo_children():
            widget.destroy()
        self.return_callback()


####################################################################################
# MAIN APPLICATION - Glen10 Gym (with permission-aware dashboard)
####################################################################################

class Glen10GymApp:
    def __init__(self, user_data):
        self.user_data = user_data
        self.root = tk.Tk()
        self.root.title("Glen10 Gym Management System")
        self.root.geometry("1200x700")
        self.root.configure(bg='#0f1c2e')

        self.setup_logout_button()
        self.show_dashboard()

    def setup_logout_button(self):
        menubar = tk.Menu(self.root)
        self.root.config(menu=menubar)

        file_menu = tk.Menu(menubar, tearoff=0)
        menubar.add_cascade(label="File", menu=file_menu)
        file_menu.add_command(label="Logout", command=self.sign_out)
        file_menu.add_separator()
        file_menu.add_command(label="Exit", command=self.root.quit)

        help_menu = tk.Menu(menubar, tearoff=0)
        menubar.add_cascade(label="Help", menu=help_menu)
        help_menu.add_command(label="About", command=self.show_about)

    def show_about(self):
        messagebox.showinfo(
            "About Glen10 Gym System",
            "Glen10 Gym Management System\nVersion 2.0\n\nRole-Based Access Control System")

    def show_dashboard(self):
        # Clear children but preserve menubar
        for widget in self.root.winfo_children():
            if not isinstance(widget, tk.Menu):
                widget.destroy()

        header_frame = tk.Frame(self.root, bg='#1a2b3e', height=80)
        header_frame.pack(fill='x')
        header_frame.pack_propagate(False)

        if PIL_AVAILABLE:
            try:
                logo_img = Image.open(io.BytesIO(base64.b64decode(LOGO_B64)))
                logo_img = logo_img.resize((200, 65), Image.LANCZOS)
                self._dashboard_logo = ImageTk.PhotoImage(logo_img)
                tk.Label(header_frame, image=self._dashboard_logo,
                         bg='#1a2b3e').pack(side='left', padx=10, pady=7)
            except Exception as e:
                print(f"Could not load logo: {e}")
                tk.Label(header_frame, text="Glen10 Gym Dashboard",
                         font=('Arial Black', 24),
                         bg='#1a2b3e', fg='white').pack(side='left', padx=20, pady=10)
        else:
            tk.Label(header_frame, text="Glen10 Gym Dashboard",
                     font=('Arial Black', 24),
                     bg='#1a2b3e', fg='white').pack(side='left', padx=20, pady=10)

        nav_frame = tk.Frame(header_frame, bg='#1a2b3e')
        nav_frame.pack(side='right', padx=20, pady=10)

        tk.Label(nav_frame,
                 text=f"User: {self.user_data['full_name']} "
                      f"({self.user_data['username']}) - {self.user_data['job_title']}",
                 font=('Arial', 10), bg='#1a2b3e',
                 fg='#3498db').pack(side='right', padx=(10, 0))
        tk.Button(nav_frame, text="Logout", font=('Arial', 9),
                  bg='#e74c3c', fg='white', relief='flat',
                  command=self.sign_out, padx=10).pack(side='right', padx=(10, 0))

        content_frame = tk.Frame(self.root, bg='#0f1c2e', padx=20, pady=20)
        content_frame.pack(expand=True, fill='both')

        stats = get_dashboard_stats()

        stats_frame = tk.Frame(content_frame, bg='#0f1c2e')
        stats_frame.pack(fill='x', pady=(0, 20))

        stat_cards = [
            ("Total Members", stats['total_members'], '#3498db'),
            ("Total Staff", stats['total_staff'], '#2ecc71'),
            ("Classes Today", stats['classes_today'], '#e74c3c'),
            ("Today's Bookings", stats['today_bookings'], '#f39c12'),
            ("Monthly Revenue", f"GBP {stats['monthly_revenue']:.2f}", '#9b59b6'),
            ("Member Status",
             f"{stats['active_members']} Active / {stats['inactive_members']} Inactive",
             '#1abc9c'),
        ]

        for i, (title, value, color) in enumerate(stat_cards):
            card = tk.Frame(stats_frame, bg=color, relief='flat', bd=0)
            card.grid(row=i // 3, column=i % 3, padx=10, pady=10, sticky='nsew')
            stats_frame.columnconfigure(i % 3, weight=1)
            stats_frame.rowconfigure(i // 3, weight=1)

            inner_frame = tk.Frame(card, bg=color)
            inner_frame.pack(padx=15, pady=15, fill='both', expand=True)
            tk.Label(inner_frame, text=title, font=('Arial', 11, 'bold'),
                     bg=color, fg='white').pack(anchor='w', pady=(5, 0))
            tk.Label(inner_frame, text=str(value), font=('Arial', 16, 'bold'),
                     bg=color, fg='white').pack(anchor='w', pady=(5, 0))

        tk.Label(content_frame, text="Quick Actions", font=('Arial Black', 16),
                 bg='#0f1c2e', fg='white').pack(anchor='w', pady=(10, 10))

        actions_frame = tk.Frame(content_frame, bg='#0f1c2e')
        actions_frame.pack(fill='x', pady=(0, 20))

        action_buttons = [
            ("Staff Management", self.open_staff_menu, '#3498db', 'staff'),
            ("Customer Management", self.open_customer_menu, '#2ecc71', 'customers'),
            ("Class Management", self.open_class_menu, '#e74c3c', 'classes'),
            ("Booking System", self.open_booking_menu, '#f39c12', 'bookings'),
            ("Invoice System", self.open_invoice_menu, '#9b59b6', 'invoices'),
            ("Reports", self.open_reports, '#1abc9c', 'reports'),
            ("Audit Log", self.open_audit_log, '#34495e', 'audit_log'),
            ("Recycle Bin", self.open_recycle_bin, '#7f8c8d', 'recycle_bin'),
        ]

        for i, (text, command, color, _module) in enumerate(action_buttons):
            btn = tk.Button(actions_frame, text=text, font=('Arial', 11),
                            bg=color, fg='white', activebackground=color,
                            activeforeground='white', cursor='hand2',
                            command=command, height=2, width=20, relief='flat')
            btn.grid(row=i // 4, column=i % 4, padx=5, pady=5, sticky='nsew')
            actions_frame.columnconfigure(i % 4, weight=1)
            actions_frame.rowconfigure(i // 4, weight=1)

        tk.Label(content_frame, text="Recent Activity", font=('Arial Black', 16),
                 bg='#0f1c2e', fg='white').pack(anchor='w', pady=(10, 10))

        activity_frame = tk.Frame(content_frame, bg='#1a2b3e')
        activity_frame.pack(fill='both', expand=True)

        columns = ('Time', 'User', 'Action', 'Table', 'Record ID')
        activity_tree = ttk.Treeview(activity_frame, columns=columns,
                                     show='headings', height=8)

        style = ttk.Style()
        style.theme_use('clam')
        style.configure("Treeview", background="#2c3e50", foreground="white",
                        fieldbackground="#2c3e50", borderwidth=0)
        style.configure("Treeview.Heading", background="#34495e",
                        foreground="white", relief="flat")
        style.map("Treeview", background=[('selected', '#3498db')])

        for col in columns:
            activity_tree.heading(col, text=col)
            activity_tree.column(col, width=150)

        scrollbar = ttk.Scrollbar(activity_frame, orient=tk.VERTICAL,
                                  command=activity_tree.yview)
        activity_tree.configure(yscrollcommand=scrollbar.set)
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
        activity_tree.pack(side=tk.LEFT, expand=True, fill='both')

        recent_logs = get_audit_logs(limit=10)
        for log in recent_logs:
            try:
                timestamp = datetime.strptime(log[5],
                                              '%Y-%m-%d %H:%M:%S').strftime('%H:%M')
            except Exception:
                timestamp = str(log[5])
            activity_tree.insert('', tk.END, values=(
                timestamp, log[1], log[2], log[3], log[4]))

        footer_frame = tk.Frame(self.root, bg='#1a2b3e', height=40)
        footer_frame.pack(fill='x', side='bottom')
        footer_frame.pack_propagate(False)

        tk.Button(footer_frame, text="Sign Out", font=('Arial', 10),
                  bg='#e74c3c', fg='white', relief='flat',
                  command=self.sign_out, padx=15).pack(side='right', padx=20, pady=5)
        tk.Label(footer_frame, text="(c) 2026 Glen10 Gym Management System",
                 font=('Arial', 9), bg='#1a2b3e', fg='white').pack(side='left',
                                                                   padx=20, pady=10)

    def _check_view_permission(self, module, friendly_name):
        perms = self.user_data.get('permissions', {})
        if module in perms and not perms[module].get('view', False):
            messagebox.showwarning(
                "Access Denied",
                f"You don't have permission to access {friendly_name}")
            return False
        return True

    def open_staff_menu(self):
        if self._check_view_permission('staff', 'Staff Management'):
            StaffManagement(self.root, self.show_dashboard, self.user_data)

    def open_customer_menu(self):
        if self._check_view_permission('customers', 'Customer Management'):
            CustomerManagement(self.root, self.show_dashboard, self.user_data)

    def open_class_menu(self):
        if self._check_view_permission('classes', 'Class Management'):
            ClassManagement(self.root, self.show_dashboard, self.user_data)

    def open_booking_menu(self):
        if self._check_view_permission('bookings', 'Booking System'):
            BookingManagement(self.root, self.show_dashboard, self.user_data)

    def open_invoice_menu(self):
        if self._check_view_permission('invoices', 'Invoice System'):
            InvoiceManagement(self.root, self.show_dashboard, self.user_data)

    def open_reports(self):
        if self._check_view_permission('reports', 'Reports'):
            ReportsDashboard(self.root, self.show_dashboard, self.user_data)

    def open_audit_log(self):
        if self._check_view_permission('audit_log', 'Audit Log'):
            AuditLogViewer(self.root, self.show_dashboard, self.user_data)

    def open_recycle_bin(self):
        if self._check_view_permission('recycle_bin', 'Recycle Bin'):
            RecycleBin(self.root, self.show_dashboard, self.user_data)

    def sign_out(self):
        if messagebox.askyesno("Sign Out", "Are you sure you want to sign out?"):
            self.root.destroy()
            root = tk.Tk()
            LoginScreen(root)
            root.mainloop()

    def run(self):
        self.root.mainloop()


####################################################################################
# ENTRY POINT
####################################################################################

if __name__ == "__main__":
    init_database()
    root = tk.Tk()
    LoginScreen(root)
    root.mainloop()
