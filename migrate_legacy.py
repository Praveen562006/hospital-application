"""Import the original PHP project's SQLite database into the Python app.

Usage:
    python migrate_legacy.py /path/to/old/database/has.sqlite
"""
import os, sys, sqlite3
from app import DB_PATH, init_db

def main():
    if len(sys.argv) != 2:
        print('Usage: python migrate_legacy.py /path/to/old/database/has.sqlite')
        raise SystemExit(2)
    source = os.path.abspath(sys.argv[1])
    if not os.path.exists(source):
        raise SystemExit(f'Legacy database not found: {source}')
    init_db()
    old = sqlite3.connect(source); old.row_factory = sqlite3.Row
    new = sqlite3.connect(DB_PATH); new.execute('PRAGMA foreign_keys=ON')
    # Import in dependency order. Existing seeded records are retained if IDs collide.
    for row in old.execute('SELECT ID, Name FROM branch'):
        new.execute('INSERT OR IGNORE INTO branches(id,name) VALUES (?,?)', (row['ID'], row['Name'].title()))
    for row in old.execute('SELECT ID, Name, BranchID FROM doctor'):
        new.execute('INSERT OR IGNORE INTO doctors(id,name,branch_id) VALUES (?,?,?)', (row['ID'], row['Name'], row['BranchID']))
    for row in old.execute('SELECT ID, Username, Password FROM patient'):
        new.execute('INSERT OR IGNORE INTO patients(id,username,password_hash) VALUES (?,?,?)', (row['ID'], row['Username'], row['Password'].lower()))
    # Legacy appointment times are preserved, but historical appointments remain historical.
    for row in old.execute('SELECT Time, DoctorID, PatientID FROM appointment'):
        new.execute('INSERT OR IGNORE INTO appointments(appointment_time,doctor_id,patient_id) VALUES (?,?,?)', (row['Time'].replace(' ', 'T'), row['DoctorID'], row['PatientID']))
    new.commit(); old.close(); new.close()
    print(f'Migrated legacy data into {DB_PATH}')

if __name__ == '__main__': main()
