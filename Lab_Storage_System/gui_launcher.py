import sys
import os
sys.path.append(os.path.dirname(os.path.abspath(__file__)))
import shutil
import webbrowser
from PySide6.QtWidgets import QApplication, QMainWindow, QLabel, QPushButton, QVBoxLayout, QWidget, QMessageBox, QListWidget, QListWidgetItem, QDialog, QCalendarWidget, QLineEdit, QDateEdit, QDoubleSpinBox, QCheckBox, QComboBox, QHBoxLayout, QInputDialog
from PySide6.QtCore import Qt, QDate, QTimer
from PySide6.QtGui import QTextCharFormat, QCursor
import sqlite3
import bcrypt
from threading import Thread
import time
import schedule
from datetime import datetime
import platform
import subprocess
from config import ROLE_DISPLAY_NAMES, REPORT_DIRS
from db import db_query, execute_sql, check_and_add_column
from security import validate_pdf, secure_file_path, verify_password
from auth import require_permission
from roles import has_permission
from audit import AuditLogger

# --- Scheduler functions ---
def run_scheduler():
    while True:
        schedule.run_pending()
        time.sleep(1)

def show_maintenance_alert():
    overdue = db_query('''
        SELECT name, next_maintenance 
        FROM equipment 
        WHERE next_maintenance <= DATE('now', '+3 days')
    ''')
    if overdue:
        message = "Pending Maintenance:\n" + "\n".join([f"- {name} ({date})" for name, date in overdue])
        QMessageBox.warning(None, "Maintenance Due", message)

# --- Create DB tables ---
create_tables_sql = [
    '''CREATE TABLE IF NOT EXISTS maintenance_log (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        equipment_id INTEGER,
        task TEXT,
        scheduled_by TEXT,
        scheduled_at TEXT,
        acknowledged_by TEXT,
        acknowledged_at TEXT,
        FOREIGN KEY (equipment_id) REFERENCES equipment(id)
    )''',
    '''CREATE TABLE IF NOT EXISTS engineer_reports (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        filename TEXT NOT NULL,
        uploaded_by TEXT NOT NULL,
        uploaded_at TEXT NOT NULL,
        approved INTEGER DEFAULT 0  -- 0 = pending, 1 = approved
    )''',
    '''CREATE TABLE IF NOT EXISTS equipment (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        name TEXT NOT NULL,
        next_maintenance DATE,
        equipment_num TEXT,
        description TEXT,
        completed INTEGER DEFAULT 0
    )''',
    '''CREATE TABLE IF NOT EXISTS quotations (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        customer TEXT NOT NULL,
        service TEXT NOT NULL,
        price REAL NOT NULL,
        date DATE NOT NULL
    )''',
    '''CREATE TABLE IF NOT EXISTS specifications (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        equipment_id INTEGER NOT NULL,
        report_path TEXT NOT NULL
    )''',
    '''CREATE TABLE IF NOT EXISTS users (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        username TEXT NOT NULL,
        password_hash TEXT NOT NULL,
        role TEXT NOT NULL
    )''',
    '''CREATE TABLE IF NOT EXISTS procedures (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        title TEXT NOT NULL,
        file_path TEXT NOT NULL,
        upload_date DATE NOT NULL
    )''',
    '''CREATE TABLE IF NOT EXISTS notifications (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    message TEXT NOT NULL,
    user_role TEXT,  -- null = visible to all
    created_at TEXT NOT NULL
    )'''
]
for sql in create_tables_sql:
    db_query(sql)

try:
    db_query("ALTER TABLE users ADD COLUMN logged_in INTEGER DEFAULT 0")
except Exception:
    pass  # Column already exists

try:
    db_query("ALTER TABLE engineer_reports ADD COLUMN rejected INTEGER DEFAULT 0")
except Exception:
    pass  # Already exists
try:
    db_query("ALTER TABLE maintenance_log ADD COLUMN scheduled_for TEXT")
except Exception:
    pass  # Already exists

# --- Start scheduler thread ---
schedule.every().day.at("09:00").do(show_maintenance_alert)
Thread(target=run_scheduler, daemon=True).start()

# --- Main Application Class ---
class MainApplication(QMainWindow):
    def __init__(self, user):
        super().__init__()
        self.user = user
        self.setWindowTitle(f"Welcome {user[1]}")
        self.setMinimumSize(600, 400)
        layout = QVBoxLayout()

        label = QLabel()
        label.setText(f"""
            <div style='padding: 8px; background-color: #eef5fb; border: 1px solid #c0d3e2; border-radius: 6px; font-size: 14px;'>
                <b>Welcome, {user[1]}!</b><br>
                You are logged in as: <i>{ROLE_DISPLAY_NAMES.get(user[3], user[3])}</i>
            </div>
        """)
        label.setTextFormat(Qt.RichText)
        layout.addWidget(label)

        from PySide6.QtWidgets import QGridLayout, QCalendarWidget
        from PySide6.QtGui import QTextCharFormat
        from PySide6.QtCore import QDate


        if user[3] == 'material_lab_manager':
            grid = QWidget()
            grid_layout = QGridLayout()
            grid.setLayout(grid_layout)

            # Add simple calendar to dashboard
            calendar = QCalendarWidget()
            calendar.setGridVisible(True)
            layout.addWidget(QLabel("📅 Current Calendar"))
            layout.addWidget(calendar)

            maintenance_data = db_query("SELECT scheduled_for FROM maintenance_log")
            for row in maintenance_data:
                date_str = row[0]
                qdate = QDate.fromString(date_str, "yyyy-MM-dd")
                if qdate.isValid():
                    fmt = QTextCharFormat()
                    fmt.setForeground(Qt.red)
                    calendar.setDateTextFormat(qdate, fmt)

            actions = [
                ("📋 Assign Equipment Number", self.assign_equipment_number),
                ("📄 View Equipment List", self.view_equipment_list),
                ("🛠️ Assign Maintenance Schedule", self.assign_maintenance_schedule_with_tasks),
                ("📅 View Maintenance Schedule", self.view_maintenance_schedule),
                ("📓 View Maintenance Log", self.view_maintenance_log),
                ("📤 Upload Reports / Standards / DVPRs", self.upload_storage_file),
                ("📁 View Uploaded Reports", self.view_uploaded_reports),
                ("📂 Create New Folder", self.create_new_folder),
                ("🧾 Upload Procedures / Instructions", self.upload_procedure_file_with_folders),
                ("📚 View Uploaded Procedures", self.view_uploaded_procedures_with_folders),
                ("🧪 Review Pending Test Reports", self.review_pending_test_reports),
                ("📊 Export Maintenance Log", self.export_maintenance_log_to_csv),
                ("🔔 View Notifications", self.view_notifications),
                ("📁 View Approved Reports", self.view_approved_test_reports)
            ]

            for index, (text, handler) in enumerate(actions):
                btn = QPushButton(text)
                btn.setStyleSheet("""
                    QPushButton {
                        padding: 10px;
                        font-size: 10pt;
                        background-color: #f5f5f5;
                        border: 1px solid #ccc;
                        border-radius: 6px;
                        text-align: left;
                    }
                    QPushButton:hover {
                        background-color: #e6f2ff;
                        border: 1px solid #007acc;
                    }
                """)
                btn.clicked.connect(handler)
                row = index // 2
                col = index % 2
                grid_layout.addWidget(btn, row, col)

            layout.addWidget(grid)

        elif user[3] == 'lab_engineer':
            from PySide6.QtWidgets import QGridLayout
            grid = QWidget()
            grid_layout = QGridLayout()
            grid.setLayout(grid_layout)

            actions = [
                ("📅 View Maintenance Schedule", self.view_maintenance_schedule),
                ("📆 Acknowledge Maintenance via Calendar", self.acknowledge_maintenance_task_calendar),
                ("📁 View Uploaded Reports", self.view_uploaded_reports),
                ("📚 View Uploaded Procedures", self.view_uploaded_procedures_with_folders),
                ("📤 Submit New Test Report", self.submit_test_report),
                ("🔔 View Notifications", self.view_notifications),
            ]

            for index, (text, handler) in enumerate(actions):
                btn = QPushButton(text)
                btn.setStyleSheet("""
                    QPushButton {
                        padding: 10px;
                        font-size: 10pt;
                        background-color: #f5f5f5;
                        border: 1px solid #ccc;
                        border-radius: 6px;
                        text-align: left;
                    }
                    QPushButton:hover {
                        background-color: #e6f2ff;
                        border: 1px solid #007acc;
                    }
                """)
                btn.clicked.connect(handler)
                row = index // 2
                col = index % 2
                grid_layout.addWidget(btn, row, col)

            layout.addWidget(grid)


        container = QWidget()
        container.setLayout(layout)
        self.setCentralWidget(container)

    def assign_equipment_number(self):
        dialog = QDialog(self)
        dialog.setWindowTitle("Assign Equipment Number")
        layout = QVBoxLayout()

        name_label = QLabel("Equipment Name:")
        name_entry = QLineEdit()
        layout.addWidget(name_label)
        layout.addWidget(name_entry)

        number_label = QLabel("Equipment Number:")
        number_entry = QLineEdit()
        layout.addWidget(number_label)
        layout.addWidget(number_entry)

        save_button = QPushButton("Save")
        save_button.clicked.connect(lambda: self.save_equipment_number(name_entry.text(), number_entry.text(), dialog))
        layout.addWidget(save_button)

        dialog.setLayout(layout)
        dialog.exec()

    def save_equipment_number(self, name, number, dialog):
        db_query('INSERT INTO equipment (name, equipment_num) VALUES (?, ?)', (name, number))
        dialog.accept()
        QMessageBox.information(self, "Saved", "Equipment registered successfully.")
    def view_equipment_list(self):
        dialog = QDialog(self)
        dialog.setWindowTitle("Equipment List")
        layout = QVBoxLayout()

        equipment_list = QListWidget()
        records = db_query('SELECT equipment_num, name, next_maintenance FROM equipment ORDER BY equipment_num')
        for number, name, date in records:
            item = f"[{number}] {name} - Next Maintenance: {date if date else 'N/A'}"
            equipment_list.addItem(item)

        layout.addWidget(equipment_list)
        dialog.setLayout(layout)
        dialog.exec()

    def view_maintenance_schedule(self):
        dialog = QDialog(self)
        dialog.setWindowTitle("Maintenance Schedule")
        layout = QVBoxLayout()

        list_widget = QListWidget()

        # ❗ Only fetch unacknowledged tasks
        records = db_query("""
            SELECT ml.id, eq.equipment_num, eq.name, ml.scheduled_for, ml.task, ml.acknowledged_by, ml.acknowledged_at
            FROM maintenance_log ml
            LEFT JOIN equipment eq ON ml.equipment_id = eq.id
            WHERE ml.acknowledged_by IS NULL
            ORDER BY ml.scheduled_for
        """)

        for record in records:
            log_id, eq_num, eq_name, scheduled_for, task, ack_by, ack_at = record
            status = "Pending"
            display_text = f"[{eq_num}] {eq_name} — Due: {scheduled_for} | {status}"
            item = QListWidgetItem(display_text)
            item.setData(Qt.UserRole, record)
            list_widget.addItem(item)

        def show_task_details(item):
            log_id, eq_num, eq_name, scheduled_for, task, ack_by, ack_at = item.data(Qt.UserRole)

            task_dialog = QDialog(self)
            task_dialog.setWindowTitle(f"{eq_name} — {scheduled_for}")
            task_layout = QVBoxLayout()

            task_label = QLabel(f"Task Description: {task if task else 'No description provided.'}")
            task_layout.addWidget(task_label)

            acknowledge_box = QCheckBox("Acknowledge Maintenance Performed")
            task_layout.addWidget(acknowledge_box)

            def update_ack():
                if acknowledge_box.isChecked():
                    now = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
                    db_query("""
                        UPDATE maintenance_log 
                        SET acknowledged_by = ?, acknowledged_at = ? 
                        WHERE id = ?
                    """, (self.user[1], now, log_id))
                    QMessageBox.information(task_dialog, "Updated", "Maintenance task acknowledged.")
                    task_dialog.accept()
                    dialog.accept()  # Close the main schedule view to refresh list

            save_button = QPushButton("Save")
            save_button.clicked.connect(update_ack)
            task_layout.addWidget(save_button)

            task_dialog.setLayout(task_layout)
            task_dialog.exec()

        list_widget.itemDoubleClicked.connect(show_task_details)
        layout.addWidget(list_widget)
        dialog.setLayout(layout)
        dialog.setMinimumSize(600, 500)
        dialog.exec()
        
    def assign_maintenance_schedule(self):
        dialog = QDialog(self)
        dialog.setWindowTitle("Assign Maintenance Schedule")
        layout = QVBoxLayout()

        equipment_label = QLabel("Equipment Number:")
        equipment_entry = QLineEdit()
        layout.addWidget(equipment_label)
        layout.addWidget(equipment_entry)

        date_label = QLabel("Next Maintenance Date:")
        date_edit = QDateEdit()
        date_edit.setCalendarPopup(True)
        layout.addWidget(date_label)
        layout.addWidget(date_edit)

        save_button = QPushButton("Assign")
        save_button.clicked.connect(lambda: self.save_maintenance_schedule(equipment_entry.text(), date_edit.date().toString(Qt.ISODate), dialog))
        layout.addWidget(save_button)

        dialog.setLayout(layout)
        dialog.exec()

    def save_maintenance_schedule(self, number, date, dialog):
        db_query('UPDATE equipment SET next_maintenance = ? WHERE equipment_num = ?', (date, number))
        dialog.accept()
        QMessageBox.information(self, "Scheduled", "Maintenance date assigned.")

    def upload_storage_file(self):
        dialog = QDialog(self)
        dialog.setWindowTitle("Upload Completed Reports / Standards / DVPR")
        layout = QVBoxLayout()

        instruction_label = QLabel("Select target folder and drag PDF files to upload")
        layout.addWidget(instruction_label)

        folder_dropdown = QComboBox()
        report_root = 'uploaded_reports'
        os.makedirs(report_root, exist_ok=True)
        folders = [f for f in os.listdir(report_root) if os.path.isdir(os.path.join(report_root, f))]
        folder_dropdown.addItem("Base Directory")  # Default
        folder_dropdown.addItems(folders)
        folder_dropdown.addItem("+ Create New Folder")

        def handle_folder_selection(index):
            if folder_dropdown.itemText(index) == "+ Create New Folder":
                new_folder_dialog = QDialog(self)
                new_folder_dialog.setWindowTitle("New Folder")
                input_layout = QVBoxLayout()
                folder_input = QLineEdit()
                folder_input.setPlaceholderText("Enter new folder name")
                input_layout.addWidget(folder_input)

                def create_new_folder():
                    folder_name = folder_input.text().strip()
                    if folder_name:
                        new_path = os.path.join(report_root, folder_name)
                        if not os.path.exists(new_path):
                            os.makedirs(new_path)
                            folder_dropdown.insertItem(folder_dropdown.count() - 1, folder_name)
                            folder_dropdown.setCurrentText(folder_name)
                            QMessageBox.information(self, "Success", f"Folder '{folder_name}' created.")
                            new_folder_dialog.accept()
                        else:
                            QMessageBox.warning(self, "Exists", f"Folder '{folder_name}' already exists.")

                create_button = QPushButton("Create")
                create_button.clicked.connect(create_new_folder)
                input_layout.addWidget(create_button)
                new_folder_dialog.setLayout(input_layout)
                new_folder_dialog.exec()

        folder_dropdown.currentIndexChanged.connect(handle_folder_selection)
        layout.addWidget(folder_dropdown)

        class DropListWidget(QListWidget):
            def __init__(self, parent=None):
                super().__init__(parent)
                self.setAcceptDrops(True)

            def dragEnterEvent(self, event):
                if event.mimeData().hasUrls():
                    event.accept()
                else:
                    event.ignore()

            def dragMoveEvent(self, event):
                if event.mimeData().hasUrls():
                    event.acceptProposedAction()
                else:
                    event.ignore()

            def dropEvent(inner_self, event):
                urls = event.mimeData().urls()
                selected_folder = folder_dropdown.currentText()
                if selected_folder == "Base Directory":
                    target_dir = report_root
                else:
                    target_dir = os.path.join(report_root, selected_folder)
                os.makedirs(target_dir, exist_ok=True)

                success_count = 0
                fail_count = 0

                for url in urls:
                    file_path = url.toLocalFile()
                    if file_path.lower().endswith('.pdf'):
                        target_file = os.path.join(target_dir, os.path.basename(file_path))
                        try:
                            shutil.copy(file_path, target_file)
                            inner_self.addItem(os.path.basename(file_path))
                            success_count += 1

                            # Log in DB
                            conn = sqlite3.connect('storage.db')
                            cursor = conn.cursor()
                            cursor.execute("INSERT INTO upload_log (filename, folder, uploaded_by, uploaded_at) VALUES (?, ?, ?, ?)", (
                                os.path.basename(file_path),
                                selected_folder,
                                self.user[1],
                                datetime.now().strftime('%Y-%m-%d %H:%M:%S')
                            ))
                            conn.commit()
                            conn.close()
                        except Exception:
                            fail_count += 1
                    else:
                        fail_count += 1  # unsupported file type

                # Combined message at the end
                QMessageBox.information(inner_self, "Upload Summary",
                    f"✅ Successfully uploaded: {success_count} file(s)\n❌ Failed to upload: {fail_count} file(s)")

        upload_area = DropListWidget()
        layout.addWidget(upload_area)

        dialog.setLayout(layout)
        dialog.setMinimumSize(400, 350)

        # Create upload_log table if it doesn't exist
        conn = sqlite3.connect('storage.db')
        cursor = conn.cursor()
        cursor.execute('''CREATE TABLE IF NOT EXISTS upload_log (
                            id INTEGER PRIMARY KEY AUTOINCREMENT,
                            filename TEXT,
                            folder TEXT,
                            uploaded_by TEXT,
                            uploaded_at TEXT
                        )''')
        conn.commit()
        conn.close()

        dialog.exec()


    def view_uploaded_reports(self):
        dialog = QDialog(self)
        dialog.setWindowTitle("Uploaded Reports / Standards / DVPRs")
        layout = QVBoxLayout()

        folder_list = QListWidget()
        report_root = 'uploaded_reports'
        os.makedirs(report_root, exist_ok=True)

        folders = [f for f in os.listdir(report_root) if os.path.isdir(os.path.join(report_root, f))]
        for folder in folders:
            folder_list.addItem(folder)

        def open_folder(item):
            folder_path = os.path.join(report_root, item.text())
            file_dialog = QDialog(self)
            file_dialog.setWindowTitle(f"Files in {item.text()}")
            file_layout = QVBoxLayout()

            file_list = QListWidget()
            for file_name in os.listdir(folder_path):
                if file_name.lower().endswith('.pdf'):
                    file_list.addItem(file_name)

            def delete_file():
                selected_item = file_list.currentItem()
                if selected_item:
                    file_path = os.path.join(folder_path, selected_item.text())
                    if os.path.exists(file_path):
                        os.remove(file_path)
                        file_list.takeItem(file_list.currentRow())
                        QMessageBox.information(self, "File Deleted", f"Deleted: {selected_item.text()}")

            delete_button = QPushButton("Delete Selected File")
            delete_button.clicked.connect(delete_file)

            file_list.itemDoubleClicked.connect(
                lambda item: self.open_report_file(os.path.join(folder_path, item.text()))
            )

            file_layout.addWidget(file_list)
            file_layout.addWidget(delete_button)
            file_dialog.setLayout(file_layout)
            file_dialog.setMinimumSize(400, 300)
            file_dialog.exec()

        #folder_list.itemDoubleClicked.connect(open_folder)

        layout.addWidget(QLabel("Double-click a folder to view its files"))
        layout.addWidget(folder_list)

        folder_list.itemDoubleClicked.connect(open_folder)

        layout.addWidget(QLabel("Double-click a folder to view its files"))
        layout.addWidget(folder_list)
        dialog.setLayout(layout)
        dialog.setMinimumSize(400, 300)
        dialog.exec()

    def assign_maintenance_schedule_with_tasks(self):
        scheduled_by = self.user[1]
        dialog = QDialog(self)
        dialog.setWindowTitle("Assign Maintenance Schedule")
        layout = QVBoxLayout()

        equipment_label = QLabel("Select Equipment:")
        layout.addWidget(equipment_label)

        equipment_dropdown = QComboBox()
        equipment_data = db_query("SELECT id, name FROM equipment")
        equipment_map = {}
        for eid, name in equipment_data:
            equipment_map[name] = eid
            equipment_dropdown.addItem(name)
        layout.addWidget(equipment_dropdown)

        date_label = QLabel("Next Maintenance Date:")
        layout.addWidget(date_label)
        date_picker = QDateEdit()
        date_picker.setCalendarPopup(True)
        layout.addWidget(date_picker)

        task_label = QLabel("Maintenance Tasks/Instructions:")
        layout.addWidget(task_label)
        task_input = QLineEdit()
        task_input.setPlaceholderText("e.g. Check calibration, replace filter")
        layout.addWidget(task_input)

        assign_button = QPushButton("Assign")
        def assign():
            selected_name = equipment_dropdown.currentText()
            equipment_id = equipment_map.get(selected_name)
            date = date_picker.date().toString(Qt.ISODate)
            task_description = task_input.text().strip()
            db_query("UPDATE equipment SET next_maintenance = ?, description = ? WHERE id = ?", (date, task_description, equipment_id))
            db_query("""
    INSERT INTO maintenance_log (equipment_id, task, scheduled_by, scheduled_at, scheduled_for)
    VALUES (?, ?, ?, ?, ?)
""", (
    equipment_id,
    task_description,
    scheduled_by,
    datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
    date_picker.date().toString(Qt.ISODate)
))
            QMessageBox.information(self, "Success", f"Scheduled maintenance for '{selected_name}' on {date} with task: {task_description}")
            dialog.accept()

        assign_button.clicked.connect(assign)
        layout.addWidget(assign_button)
        dialog.setLayout(layout)
        dialog.exec()

    def acknowledge_maintenance_task_calendar(self):
        dialog = QDialog(self)
        dialog.setWindowTitle("Acknowledge Maintenance via Calendar")
        dialog.setMinimumSize(500, 500)
        layout = QVBoxLayout()

        calendar = QCalendarWidget()
        calendar.setGridVisible(True)
        layout.addWidget(calendar)

        # Updated to pull from maintenance_log instead of equipment
        maintenance_data = db_query("""
            SELECT ml.id, eq.name, ml.scheduled_for, ml.task, ml.acknowledged_by
            FROM maintenance_log ml
            LEFT JOIN equipment eq ON ml.equipment_id = eq.id
        """)

        date_to_tasks = {}
        for log_id, name, scheduled_for, task, ack_by in maintenance_data:
            qdate = QDate.fromString(scheduled_for, "yyyy-MM-dd")
            if qdate.isValid():
                if qdate not in date_to_tasks:
                    date_to_tasks[qdate] = []
                date_to_tasks[qdate].append((log_id, name, task, bool(ack_by)))

        for qdate in date_to_tasks:
            fmt = QTextCharFormat()
            fmt.setForeground(Qt.red)
            calendar.setDateTextFormat(qdate, fmt)

        def show_tasks_for_date(selected_date):
            task_list = QListWidget()
            tasks = date_to_tasks.get(selected_date, [])
            if not tasks:
                QMessageBox.information(dialog, "No Tasks", "No maintenance tasks scheduled for this date.")
                return

            task_dialog = QDialog(dialog)
            task_dialog.setWindowTitle(f"Tasks on {selected_date.toString('yyyy-MM-dd')}")
            task_layout = QVBoxLayout()

            for log_id, name, task, acknowledged in tasks:
                item_text = f"{name}: {task}"
                checkbox = QCheckBox(item_text)
                checkbox.setChecked(acknowledged)

                def update_acknowledgement(state, log_id=log_id):
                    if state == Qt.Checked:
                        now = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
                        db_query("""
                            UPDATE maintenance_log 
                            SET acknowledged_by = ?, acknowledged_at = ? 
                            WHERE id = ?
                        """, (self.user[1], now, log_id))

                checkbox.stateChanged.connect(update_acknowledgement)
                task_layout.addWidget(checkbox)

            task_dialog.setLayout(task_layout)
            task_dialog.exec()

        calendar.clicked.connect(show_tasks_for_date)
        dialog.setLayout(layout)
        dialog.exec()

    def create_new_folder(self):
        dialog = QDialog(self)
        dialog.setWindowTitle("Create New Folder")
        layout = QVBoxLayout()

        folder_name_input = QLineEdit()
        folder_name_input.setPlaceholderText("Enter folder name")
        layout.addWidget(folder_name_input)

        create_button = QPushButton("Create")

        def create_folder():
            folder_name = folder_name_input.text().strip()
            if folder_name:
                new_path = os.path.join('uploaded_reports', folder_name)
                if not os.path.exists(new_path):
                    os.makedirs(new_path)
                    QMessageBox.information(self, "Folder Created", f"Folder '{folder_name}' created successfully.")
                    dialog.accept()
                else:
                    QMessageBox.warning(self, "Exists", f"Folder '{folder_name}' already exists.")

        create_button.clicked.connect(create_folder)
        layout.addWidget(create_button)

        dialog.setLayout(layout)
        dialog.exec()


    def view_maintenance_log(self):
        dialog = QDialog(self)
        dialog.setWindowTitle("Maintenance Log")
        layout = QVBoxLayout()

        log_list = QListWidget()
        records = db_query("""
            SELECT ml.id, eq.equipment_num, eq.name, ml.task, ml.scheduled_by,
                   ml.scheduled_at, ml.acknowledged_by, ml.acknowledged_at
            FROM maintenance_log ml
            LEFT JOIN equipment eq ON ml.equipment_id = eq.id
            ORDER BY ml.scheduled_at DESC
        """)

        for log_id, eq_num, eq_name, task, sched_by, sched_at, ack_by, ack_at in records:
            lines = [
                f"[{eq_num}] {eq_name}",
                f"Task: {task}",
                f"Scheduled by: {sched_by} at {sched_at}",
                f"Acknowledged by: {ack_by} at {ack_at}" if ack_by else "Acknowledged: [Pending]"
            ]
            log_list.addItem("\n".join(lines))

        layout.addWidget(log_list)
        dialog.setLayout(layout)
        dialog.setMinimumSize(500, 400)
        dialog.exec()

    def upload_procedure_file(self):
        dialog = QDialog(self)
        dialog.setWindowTitle("Upload Procedures / Instructions")
        layout = QVBoxLayout()

        instruction_label = QLabel("Drag and drop procedure files here (PDF, Word, Excel, PowerPoint, etc.)")
        layout.addWidget(instruction_label)

        allowed_extensions = ['.pdf', '.doc', '.docx', '.xls', '.xlsx', '.ppt', '.pptx']
        target_dir = 'uploaded_procedures'
        os.makedirs(target_dir, exist_ok=True)

        class DropListWidget(QListWidget):
            def __init__(inner_self, parent=None):
                super().__init__(parent)
                inner_self.setAcceptDrops(True)

            def dragEnterEvent(inner_self, event):
                if event.mimeData().hasUrls():
                    event.acceptProposedAction()

            def dragMoveEvent(inner_self, event):
                event.acceptProposedAction()

            def dropEvent(inner_self, event):
                urls = event.mimeData().urls()
                for url in urls:
                    file_path = url.toLocalFile()
                    ext = os.path.splitext(file_path)[1].lower()
                    if ext in allowed_extensions:
                        try:
                            target_file = os.path.join(target_dir, os.path.basename(file_path))
                            shutil.copy(file_path, target_file)
                            inner_self.addItem(os.path.basename(file_path))
                            QMessageBox.information(inner_self, "Uploaded", f"Successfully uploaded: {os.path.basename(file_path)}")
                        except Exception as e:
                            QMessageBox.critical(inner_self, "Error", f"Upload failed: {e}")
                    else:
                        QMessageBox.warning(inner_self, "Invalid Format", f"Unsupported file type: {ext}")

        upload_area = DropListWidget()
        layout.addWidget(upload_area)

        dialog.setLayout(layout)
        dialog.setMinimumSize(600, 500)
        dialog.exec()
    
    

    def acknowledge_maintenance_task(self):
        QMessageBox.information(self, "Coming Soon", "Acknowledgement system is under development.")

    def submit_test_report(self):
        QMessageBox.information(self, "Coming Soon", "Test report submission is under development.")

    def upload_procedure_file_with_folders(self):
        dialog = QDialog(self)
        dialog.setWindowTitle("Upload Procedures / Instructions")
        layout = QVBoxLayout()

        layout.addWidget(QLabel("Select folder and drag files (PDF, Word, Excel, etc.) to upload"))

        procedures_root = 'uploaded_procedures'
        os.makedirs(procedures_root, exist_ok=True)

        folder_dropdown = QComboBox()
        folders = [f for f in os.listdir(procedures_root) if os.path.isdir(os.path.join(procedures_root, f))]
        folder_dropdown.addItem("Base Directory")
        folder_dropdown.addItems(folders)
        folder_dropdown.addItem("+ Create New Folder")
        layout.addWidget(folder_dropdown)

        def handle_folder_selection(index):
            if folder_dropdown.itemText(index) == "+ Create New Folder":
                new_folder_dialog = QDialog(dialog)
                new_folder_dialog.setWindowTitle("Create Folder")
                input_layout = QVBoxLayout()
                folder_input = QLineEdit()
                folder_input.setPlaceholderText("Enter folder name")
                input_layout.addWidget(folder_input)

                def create_folder():
                    name = folder_input.text().strip()
                    if name:
                        path = os.path.join(procedures_root, name)
                        if not os.path.exists(path):
                            os.makedirs(path)
                            folder_dropdown.insertItem(folder_dropdown.count() - 1, name)
                            folder_dropdown.setCurrentText(name)
                            QMessageBox.information(dialog, "Created", f"Folder '{name}' created.")
                            new_folder_dialog.accept()
                        else:
                            QMessageBox.warning(dialog, "Exists", "Folder already exists.")

                create_btn = QPushButton("Create")
                create_btn.clicked.connect(create_folder)
                input_layout.addWidget(create_btn)
                new_folder_dialog.setLayout(input_layout)
                new_folder_dialog.exec()

        folder_dropdown.currentIndexChanged.connect(handle_folder_selection)

        allowed_ext = ['.pdf', '.doc', '.docx', '.xls', '.xlsx', '.ppt', '.pptx']

        class DropListWidget(QListWidget):
            def __init__(self, parent=None):
                super().__init__(parent)
                self.setAcceptDrops(True)
                self.setMinimumHeight(150)
                self.setStyleSheet("""
                    QListWidget {
                        border: 2px dashed #aaa;
                        background-color: #f9f9f9;
                        padding: 10px;
                        font-style: italic;
                        color: #555;
                    }
                """)

            def dragEnterEvent(inner_self, event):
                if event.mimeData().hasUrls():
                    event.acceptProposedAction()
                else:
                    event.ignore()

            def dragMoveEvent(inner_self, event):
                if event.mimeData().hasUrls():
                    event.acceptProposedAction()
                else:
                    event.ignore()

            def dropEvent(inner_self, event):
                urls = event.mimeData().urls()
                selected_folder = folder_dropdown.currentText()
                procedures_root = 'uploaded_procedures'  # ensure local access
                if selected_folder == "Base Directory":
                    target_dir = procedures_root
                else:
                    target_dir = os.path.join(procedures_root, selected_folder)

                os.makedirs(target_dir, exist_ok=True)

                success_count = 0
                failure_count = 0

                for url in urls:
                    file_path = url.toLocalFile()
                    ext = os.path.splitext(file_path)[1].lower()
                    if ext in ['.pdf', '.doc', '.docx', '.xls', '.xlsx', '.ppt', '.pptx']:
                        try:
                            filename = os.path.basename(file_path)
                            target_file = os.path.join(target_dir, filename)
                            shutil.copy(file_path, target_file)
                            inner_self.addItem(filename)
                            success_count += 1
                        except Exception as e:
                            failure_count += 1
                    else:
                        failure_count += 1

                QMessageBox.information(inner_self, "Upload Summary",
                                        f"✅ Uploaded: {success_count}\n❌ Failed: {failure_count}")
        upload_area = DropListWidget()
        layout.addWidget(upload_area)

        dialog.setLayout(layout)
        dialog.setMinimumSize(600, 400)
        dialog.exec()

    def view_uploaded_procedures_with_folders(self):
        dialog = QDialog(self)
        dialog.setWindowTitle("View Uploaded Procedures / Instructions")
        layout = QVBoxLayout()

        procedures_root = "uploaded_procedures"
        os.makedirs(procedures_root, exist_ok=True)

        folder_list = QListWidget()
        folder_list.addItem("Base Directory")

        folders = [f for f in os.listdir(procedures_root) if os.path.isdir(os.path.join(procedures_root, f))]
        for folder in folders:
            folder_list.addItem(folder)

        def open_folder(item):
            folder_path = procedures_root if item.text() == "Base Directory" else os.path.join(procedures_root, item.text())
            file_dialog = QDialog(self)
            file_dialog.setWindowTitle(f"Contents of {item.text()}")
            file_layout = QVBoxLayout()

            file_list = QListWidget()
            for entry in os.listdir(folder_path):
                file_list.addItem(entry)

            def open_file():
                selected = file_list.currentItem()
                if selected:
                    path = os.path.join(folder_path, selected.text())
                    if os.path.isdir(path):
                        # Recurse into subfolder
                        sub_item = QListWidgetItem(selected.text())
                        open_folder(sub_item)
                    elif os.path.isfile(path):
                        if platform.system() == 'Windows':
                            os.startfile(path)
                        elif platform.system() == 'Darwin':
                            subprocess.Popen(['open', path])
                        else:
                            subprocess.Popen(['xdg-open', path])

            file_list.itemDoubleClicked.connect(open_file)

            # ✅ Button: Create New Subfolder
            create_folder_button = QPushButton("Create New Folder Here")

            def create_new_subfolder():
                name_input, ok = QInputDialog.getText(file_dialog, "New Folder", "Enter folder name:")
                if ok and name_input.strip():
                    new_folder_path = os.path.join(folder_path, name_input.strip())
                    if os.path.exists(new_folder_path):
                        QMessageBox.warning(file_dialog, "Exists", "A folder with this name already exists.")
                    else:
                        try:
                            os.makedirs(new_folder_path)
                            file_list.addItem(name_input.strip())
                            QMessageBox.information(file_dialog, "Created", f"Folder '{name_input.strip()}' created.")
                        except Exception as e:
                            QMessageBox.critical(file_dialog, "Error", f"Failed to create folder: {e}")

            create_folder_button.clicked.connect(create_new_subfolder)

            file_layout.addWidget(file_list)
            file_layout.addWidget(create_folder_button)
            file_dialog.setLayout(file_layout)
            file_dialog.setMinimumSize(400, 300)
            file_dialog.exec()

        folder_list.itemDoubleClicked.connect(open_folder)

        layout.addWidget(QLabel("Double-click a folder to view its contents"))
        layout.addWidget(folder_list)

        # 📁 Create folder in top-level procedure folder
        create_folder_button = QPushButton("Create New Top-Level Folder")

        def create_folder_dialog():
            create_dialog = QDialog(self)
            create_dialog.setWindowTitle("Create New Folder")
            create_layout = QVBoxLayout()

            folder_name_input = QLineEdit()
            folder_name_input.setPlaceholderText("Enter folder name")
            create_layout.addWidget(folder_name_input)

            def create_folder():
                folder_name = folder_name_input.text().strip()
                if folder_name:
                    new_path = os.path.join(procedures_root, folder_name)
                    if not os.path.exists(new_path):
                        os.makedirs(new_path)
                        folder_list.addItem(folder_name)
                        QMessageBox.information(self, "Folder Created", f"Folder '{folder_name}' created.")
                        create_dialog.accept()
                    else:
                        QMessageBox.warning(self, "Exists", f"Folder '{folder_name}' already exists.")

            create_button = QPushButton("Create")
            create_button.clicked.connect(create_folder)
            create_layout.addWidget(create_button)

            create_dialog.setLayout(create_layout)
            create_dialog.exec()

        create_folder_button.clicked.connect(create_folder_dialog)
        layout.addWidget(create_folder_button)
        dialog.setLayout(layout)
        dialog.setMinimumSize(600, 400)
        dialog.exec()
    

    def review_pending_test_reports(self):
        dialog = QDialog(self)
        dialog.setWindowTitle("Review Pending Test Reports")
        layout = QVBoxLayout()

        report_list = QListWidget()
        records = db_query("SELECT id, filename, uploaded_by, uploaded_at FROM engineer_reports WHERE approved = 0")

        for report_id, filename, uploaded_by, uploaded_at in records:
            item = QListWidgetItem(f"{filename} | Uploaded by: {uploaded_by} on {uploaded_at}")
            item.setData(Qt.UserRole, (report_id, filename, uploaded_by))
            report_list.addItem(item)

        def open_selected_file():
            item = report_list.currentItem()
            if not item:
                QMessageBox.warning(dialog, "No Selection", "Please select a report to open.")
                return

            _, filename, _ = item.data(Qt.UserRole)
            file_path = os.path.join("engineer_reports", filename)
            if os.path.exists(file_path):
                if platform.system() == 'Windows':
                    os.startfile(file_path)
                elif platform.system() == 'Darwin':
                    subprocess.Popen(['open', file_path])
                else:
                    subprocess.Popen(['xdg-open', file_path])
            else:
                QMessageBox.warning(dialog, "File Missing", f"The file {filename} does not exist.")

        def approve_selected():
            item = report_list.currentItem()
            if not item:
                QMessageBox.warning(dialog, "No Selection", "Please select a report to approve.")
                return

            report_id, filename, uploaded_by = item.data(Qt.UserRole)
            db_query("UPDATE engineer_reports SET approved = 1 WHERE id = ?", (report_id,))
            report_list.takeItem(report_list.currentRow())

            approved_root = os.path.join("engineer_reports", "approved")
            os.makedirs(approved_root, exist_ok=True)

            existing_folders = [f for f in os.listdir(approved_root) if os.path.isdir(os.path.join(approved_root, f))]

            folder_name, ok = QInputDialog.getItem(
                dialog,
                "Choose or Create Folder",
                "Select a folder to move the approved report into:",
                existing_folders + ["[Create New Folder]"],
                editable=True
            )

            if ok and folder_name:
                if folder_name == "[Create New Folder]" or folder_name.strip() == "":
                    folder_name, ok = QInputDialog.getText(dialog, "New Folder", "Enter folder name:")

                if ok and folder_name:
                    target_dir = os.path.join(approved_root, folder_name.strip())
                    os.makedirs(target_dir, exist_ok=True)
                    src_path = os.path.join("engineer_reports", filename)
                    dest_path = os.path.join(target_dir, filename)

                    try:
                        shutil.move(src_path, dest_path)
                        QMessageBox.information(dialog, "Moved", f"Approved report moved to: {dest_path}")

                        # ✅ Notify engineers about approval
                        db_query("""
                            INSERT INTO notifications (message, user_role, created_at)
                            VALUES (?, ?, ?)
                        """, (
                            f"✅ The test report '{filename}' was approved by {self.user[1]}.",
                            "lab_engineer",
                            datetime.now().strftime('%Y-%m-%d %H:%M:%S')
                        ))

                    except Exception as e:
                        QMessageBox.critical(dialog, "Error", f"Failed to move approved report: {e}")

        def reject_selected():
            item = report_list.currentItem()
            if not item:
                QMessageBox.warning(dialog, "No Selection", "Please select a report to reject.")
                return

            report_id, filename, uploaded_by = item.data(Qt.UserRole)
            reason, ok = QInputDialog.getText(dialog, "Reject Report", "Reason for rejection:")
            if ok and reason.strip():
                db_query("DELETE FROM engineer_reports WHERE id = ?", (report_id,))
                report_list.takeItem(report_list.currentRow())

                # Notify engineer about rejection
                db_query("""
                    INSERT INTO notifications (message, user_role, created_at)
                    VALUES (?, ?, ?)
                """, (
                    f"❌ The test report '{filename}' was rejected by {self.user[1]}. Reason: {reason.strip()}",
                    "lab_engineer",
                    datetime.now().strftime('%Y-%m-%d %H:%M:%S')
                ))

                QMessageBox.information(dialog, "Rejected", "Report has been rejected and engineer notified.")

        approve_button = QPushButton("✅ Approve Selected Report")
        approve_button.clicked.connect(approve_selected)

        reject_button = QPushButton("❌ Reject Selected Report")
        reject_button.clicked.connect(reject_selected)

        open_button = QPushButton("📂 Open Selected Report")
        open_button.clicked.connect(open_selected_file)

        layout.addWidget(report_list)
        layout.addWidget(open_button)
        layout.addWidget(approve_button)
        layout.addWidget(reject_button)
        dialog.setLayout(layout)
        dialog.setMinimumSize(600, 400)
        dialog.exec()

    def export_maintenance_log_to_csv(self):
        from PySide6.QtWidgets import QFileDialog
        import csv

        path, _ = QFileDialog.getSaveFileName(self, "Save Maintenance Log", "maintenance_log.csv", "CSV Files (*.csv)")
        if not path:
            return

        records = db_query("""
            SELECT eq.equipment_num, eq.name, ml.task, ml.scheduled_by, ml.scheduled_at, ml.acknowledged_by, ml.acknowledged_at
            FROM maintenance_log ml
            LEFT JOIN equipment eq ON ml.equipment_id = eq.id
            ORDER BY ml.scheduled_at DESC
        """)

        try:
            with open(path, mode='w', newline='', encoding='utf-8') as file:
                writer = csv.writer(file)
                writer.writerow(["Equipment Number", "Equipment Name", "Task", "Scheduled By", "Scheduled At", "Acknowledged By", "Acknowledged At"])
                for row in records:
                    writer.writerow(row)
            QMessageBox.information(self, "Export Complete", f"Maintenance log saved to {path}")
        except Exception as e:
            QMessageBox.critical(self, "Export Failed", f"Error exporting log: {e}")

    def view_notifications(self):
        dialog = QDialog(self)
        dialog.setWindowTitle("Notifications")
        layout = QVBoxLayout()

        notification_list = QListWidget()
        notifications = db_query("""
            SELECT message, created_at FROM notifications
            WHERE user_role = ? OR user_role IS NULL
            ORDER BY created_at DESC
        """, (self.user[3],))

        for message, created_at in notifications:
            notification_list.addItem(f"{created_at}: {message}")

        layout.addWidget(notification_list)
        dialog.setLayout(layout)
        dialog.setMinimumSize(500, 300)
        dialog.exec()

    def submit_test_report(self):
        from PySide6.QtWidgets import QFileDialog
        dialog = QDialog(self)
        dialog.setWindowTitle("Submit New Test Report")
        layout = QVBoxLayout()

        file_button = QPushButton("Choose Report File")
        file_path_label = QLabel("No file selected")
        layout.addWidget(file_button)
        layout.addWidget(file_path_label)

        def choose_file():
            file_path, _ = QFileDialog.getOpenFileName(dialog, "Select Test Report", "", "PDF Files (*.pdf);;All Files (*)")
            if file_path:
                file_path_label.setText(file_path)
                dialog.selected_file_path = file_path

        file_button.clicked.connect(choose_file)

        submit_button = QPushButton("Submit Report")
        layout.addWidget(submit_button)

        def submit():
            file_path = getattr(dialog, 'selected_file_path', None)
            if not file_path:
                QMessageBox.warning(dialog, "Missing File", "Please choose a file to submit.")
                return

            filename = os.path.basename(file_path)
            target_dir = "engineer_reports"
            os.makedirs(target_dir, exist_ok=True)
            target_path = os.path.join(target_dir, filename)
            try:
                shutil.copy(file_path, target_path)
                db_query("INSERT INTO engineer_reports (filename, uploaded_by, uploaded_at) VALUES (?, ?, ?)", (
                    filename,
                    self.user[1],
                    datetime.now().strftime('%Y-%m-%d %H:%M:%S')
                ))
                db_query("""
                    INSERT INTO notifications (message, user_role, created_at)
                    VALUES (?, ?, ?)
                """, (
                    f"{self.user[1]} submitted a new test report.",
                    "material_lab_manager",
                    datetime.now().strftime('%Y-%m-%d %H:%M:%S')
                ))
                QMessageBox.information(dialog, "Success", "Test report submitted successfully.")
                dialog.accept()
            except Exception as e:
                QMessageBox.critical(dialog, "Error", f"Failed to submit report: {e}")

        submit_button.clicked.connect(submit)

        dialog.setLayout(layout)
        dialog.setMinimumSize(400, 200)
        dialog.exec()

    
      
    def view_approved_test_reports(self):
        dialog = QDialog(self)
        dialog.setWindowTitle("Approved Test Reports")
        layout = QVBoxLayout()

        approved_root = "engineer_reports/approved"
        os.makedirs(approved_root, exist_ok=True)

        folder_list = QListWidget()
        folder_list.addItem("Base Directory")

        folders = [f for f in os.listdir(approved_root) if os.path.isdir(os.path.join(approved_root, f))]
        for folder in folders:
            folder_list.addItem(folder)

        def open_folder(item):
            folder_path = approved_root if item.text() == "Base Directory" else os.path.join(approved_root, item.text())
            file_dialog = QDialog(self)
            file_dialog.setWindowTitle(f"Files in {item.text()}")
            file_layout = QVBoxLayout()

            file_list = QListWidget()
            if os.path.exists(folder_path):
                for file in os.listdir(folder_path):
                    file_list.addItem(file)

            def open_file():
                selected = file_list.currentItem()
                if selected:
                    path = os.path.join(folder_path, selected.text())
                    if os.path.exists(path):
                        if platform.system() == 'Windows':
                            os.startfile(path)
                        elif platform.system() == 'Darwin':
                            subprocess.Popen(['open', path])
                        else:
                            subprocess.Popen(['xdg-open', path])

            file_list.itemDoubleClicked.connect(open_file)
            file_layout.addWidget(file_list)
            file_dialog.setLayout(file_layout)
            file_dialog.setMinimumSize(400, 300)
            file_dialog.exec()

        folder_list.itemDoubleClicked.connect(open_folder)

        layout.addWidget(QLabel("Double-click a folder to view its files"))
        layout.addWidget(folder_list)

        # Folder creation button
        create_folder_button = QPushButton("Create New Folder")

        def create_folder_dialog():
            create_dialog = QDialog(self)
            create_dialog.setWindowTitle("Create New Folder")
            create_layout = QVBoxLayout()

            folder_name_input = QLineEdit()
            folder_name_input.setPlaceholderText("Enter folder name")
            create_layout.addWidget(folder_name_input)

            def create_folder():
                folder_name = folder_name_input.text().strip()
                if folder_name:
                    new_path = os.path.join(approved_root, folder_name)
                    if not os.path.exists(new_path):
                        os.makedirs(new_path)
                        folder_list.addItem(folder_name)
                        QMessageBox.information(self, "Folder Created", f"Folder '{folder_name}' created.")
                        create_dialog.accept()
                    else:
                        QMessageBox.warning(self, "Exists", f"Folder '{folder_name}' already exists.")

            create_button = QPushButton("Create")
            create_button.clicked.connect(create_folder)
            create_layout.addWidget(create_button)

            create_dialog.setLayout(create_layout)
            create_dialog.exec()

        create_folder_button.clicked.connect(create_folder_dialog)
        layout.addWidget(create_folder_button)

        dialog.setLayout(layout)
        dialog.setMinimumSize(600, 400)
        dialog.exec()

    def open_report_file(self, file_path):
        if os.path.exists(file_path):
            if platform.system() == 'Windows':
                os.startfile(file_path)
            elif platform.system() == 'Darwin':
                subprocess.Popen(['open', file_path])
            else:
                subprocess.Popen(['xdg-open', file_path])
        else:
            QMessageBox.warning(self, "File Not Found", "The selected file does not exist.")

    def logout(self):
    # Reset login status in DB
        db_query("UPDATE users SET logged_in = 0 WHERE id = ?", (self.user[0],))
        self.close()
        self.login_window = LoginWindow()
        self.login_window.show()

    def closeEvent(self, event):
        db_query("UPDATE users SET logged_in = 0 WHERE id = ?", (self.user[0],))
        event.accept()
    

# --- Login Window ---
class LoginWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Lab System Login")
        self.setMinimumSize(300, 150)
        central_widget = QWidget()
        self.setCentralWidget(central_widget)
        layout = QVBoxLayout()

        self.username_entry = QLineEdit()
        self.username_entry.setPlaceholderText("Username")
        layout.addWidget(self.username_entry)

        self.password_entry = QLineEdit()
        self.password_entry.setPlaceholderText("Password")
        self.password_entry.setEchoMode(QLineEdit.Password)
        layout.addWidget(self.password_entry)

        button_layout = QHBoxLayout()
        login_button = QPushButton("Login")
        login_button.clicked.connect(self.login)
        button_layout.addWidget(login_button)

        exit_button = QPushButton("Exit")
        exit_button.clicked.connect(QApplication.quit)
        button_layout.addWidget(exit_button)

        layout.addLayout(button_layout)
        central_widget.setLayout(layout)

    def login(self):
        username = self.username_entry.text()
        password = self.password_entry.text()

        user = db_query(
            'SELECT id, username, password_hash, role, logged_in FROM users WHERE username = ?',
            (username,),
            fetchone=True
        )

        if user:
            if user[4] == 1:  # already logged in
                QMessageBox.warning(self, "Already Logged In", "This account is already logged in on another device.")
                return

            if verify_password(user[2], password):
                db_query("UPDATE users SET logged_in = 1 WHERE id = ?", (user[0],))
                self.audit = AuditLogger(user[0])
                self.close()
                self.main_app = MainApplication(user)
                self.main_app.show()
                return

        QMessageBox.critical(self, "Login Failed", "Invalid username or password.")

# --- App Execution ---
if __name__ == "__main__":
    import traceback
    try:
        app = QApplication(sys.argv)
        login_window = LoginWindow()
        login_window.show()
        app.exec()
    except Exception as e:
        with open("error_log.txt", "w") as f:
            traceback.print_exc(file=f)
        print("An error occurred. See 'error_log.txt' for details.")
        input("Press Enter to exit...")
