import sqlite3
import bcrypt
import schedule
import time
from datetime import datetime, timedelta
from threading import Thread
from rich.console import Console
from rich.prompt import Prompt, Confirm
from getpass import getpass
from db import db_query


console = Console()
current_user = None

# --- Authentication ---
def login():
    username = Prompt.ask("Username")
    password = getpass("Password: ")
    
    user = db_query('SELECT * FROM users WHERE username = ?', (username,), fetchone=True)
    if user and bcrypt.checkpw(password.encode('utf-8'), user[2]):
        return user  # (id, username, password_hash, role)
    console.print("[bold red]Invalid credentials![/]")
    return None

# --- Decorators ---
def require_role(allowed_roles):
    def decorator(func):
        def wrapper(*args, **kwargs):
            if current_user[3] in allowed_roles:
                return func(*args, **kwargs)
            console.print("[bold red]Permission denied![/]")
        return wrapper
    return decorator

# --- Core Features ---
@require_role(['admin', 'named_user'])
def log_test():
    equipment = db_query('SELECT id, name FROM equipment')
    if not equipment:
        console.print("[yellow]No equipment found![/]")
        return
    
    console.print("[bold]Select Equipment:[/]")
    for idx, (e_id, name) in enumerate(equipment, 1):
        console.print(f"{idx}. {name}")
    
    choice = int(Prompt.ask("Enter number", choices=[str(i) for i in range(1, len(equipment)+1)])) - 1
    e_id = equipment[choice][0]
    result = Prompt.ask("Test Result")
    
    db_query('INSERT INTO tests (equipment_id, test_date, result) VALUES (?, ?, ?)',
             (e_id, datetime.now().date(), result))
    console.print("[green]Test logged successfully![/]")

@require_role(['admin'])
def schedule_maintenance():
    equipment = db_query('SELECT id, name FROM equipment')
    if not equipment:
        console.print("[yellow]No equipment found![/]")
        return
    
    # Let user pick equipment
    console.print("[bold]Select Equipment:[/]")
    for idx, (equip_id, name) in enumerate(equipment, 1):  # Renamed to avoid confusion
        console.print(f"{idx}. {name}")
    
    choice = int(Prompt.ask("Enter number", choices=[str(i) for i in range(1, len(equipment)+1)])) - 1
    selected_equipment_id = equipment[choice][0]  # Get ID from the selected equipment
    
    # Ask for interval
    interval = int(Prompt.ask("Maintenance interval (days)"))
    next_date = datetime.now().date() + timedelta(days=interval)
    
    # Update database (critical fix: use selected_equipment_id)
    db_query('''
        UPDATE equipment 
        SET last_maintenance=?, next_maintenance=?, maintenance_interval=?
        WHERE id=?
    ''', (datetime.now().date(), next_date, interval, selected_equipment_id))  # Fix here
    
    console.print(f"[green]Maintenance scheduled for {next_date}![/]")

# --- Scheduler Thread ---
def check_reminders():
    while True:
        schedule.run_pending()
        time.sleep(1)

def reminder_job():
    overdue = db_query('''
        SELECT name, next_maintenance 
        FROM equipment 
        WHERE next_maintenance <= DATE('now', '+3 days')
    ''')
    for name, date in overdue:
        console.print(f"\n[bold yellow]REMINDER: {name} maintenance due on {date}[/]")

schedule.every().day.at("09:00").do(reminder_job)
Thread(target=check_reminders, daemon=True).start()

# --- Menu System ---
def admin_menu():
    while True:
        choice = Prompt.ask('''
[bold cyan]Admin Menu[/]
1. Schedule Maintenance
2. View Audits
3. Manage Users
4. Generate Quotes
5. Log Out
''', choices=['1', '2', '3', '4', '5'])
        
        if choice == '1': schedule_maintenance()
        elif choice == '5': break

def user_menu():
    while True:
        choice = Prompt.ask('''
[bold cyan]User Menu[/]
1. Log Test Data
2. View Schedule
3. Request Quote
4. Log Out
''', choices=['1', '2', '3', '4'])
        
        if choice == '1': log_test()
        elif choice == '4': break

# --- Main App ---
if __name__ == "__main__":
    console.print("[bold green]\n=== Lab Management System ===[/]")
    
    while True:
        user = login()
        if not user:
            if Confirm.ask("Try again?"):
                continue
            break
            
        current_user = user
        console.print(f"\n[bold]Logged in as: [cyan]{user[1]}[/] ([yellow]{user[3]}[/])[/]")
        
        if user[3] == 'admin':
            admin_menu()
        elif user[3] == 'named_user':
            user_menu()
        else:
            console.print("[bold]Guest View[/]\n1. View Equipment\n2. Exit")
            # ... Add view-only logic

        current_user = None
        console.print("[green]Logged out![/]\n")