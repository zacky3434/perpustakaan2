import sqlite3
import os
from werkzeug.security import generate_password_hash

# Mengunci lokasi file perpustakaan.db di folder yang sama dengan script
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DB_PATH = os.path.join(BASE_DIR, 'perpustakaan.db')


def init_db():
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()

    # 1. Tabel Users
    cursor.execute('''
                   CREATE TABLE IF NOT EXISTS users
                   (
                       id
                       INTEGER
                       PRIMARY
                       KEY
                       AUTOINCREMENT,
                       username
                       TEXT
                       UNIQUE
                       NOT
                       NULL,
                       password
                       TEXT
                       NOT
                       NULL,
                       role
                       TEXT
                       NOT
                       NULL,
                       email
                       TEXT,
                       full_name
                       TEXT
                   )
                   ''')

    # 2. Tabel Categories
    cursor.execute('''
                   CREATE TABLE IF NOT EXISTS categories
                   (
                       id
                       INTEGER
                       PRIMARY
                       KEY
                       AUTOINCREMENT,
                       name
                       TEXT
                       NOT
                       NULL
                   )
                   ''')

    # 3. Tabel Books
    cursor.execute('''
                   CREATE TABLE IF NOT EXISTS books
                   (
                       id
                       INTEGER
                       PRIMARY
                       KEY
                       AUTOINCREMENT,
                       title
                       TEXT
                       NOT
                       NULL,
                       author
                       TEXT
                       NOT
                       NULL,
                       category_id
                       INTEGER,
                       description
                       TEXT,
                       cover_image
                       TEXT,
                       qr_code
                       TEXT,
                       is_available
                       BOOLEAN
                       DEFAULT
                       1,
                       FOREIGN
                       KEY
                   (
                       category_id
                   ) REFERENCES categories
                   (
                       id
                   )
                       )
                   ''')

    # 4. Tabel Borrowings
    cursor.execute('''
                   CREATE TABLE IF NOT EXISTS borrowings
                   (
                       id
                       INTEGER
                       PRIMARY
                       KEY
                       AUTOINCREMENT,
                       user_id
                       INTEGER,
                       book_id
                       INTEGER,
                       request_date
                       TEXT
                       NOT
                       NULL,
                       borrow_date
                       TEXT,
                       return_due_date
                       TEXT,
                       actual_return_date
                       TEXT,
                       status
                       TEXT
                       DEFAULT
                       'menunggu',
                       fine
                       INTEGER
                       DEFAULT
                       0,
                       FOREIGN
                       KEY
                   (
                       user_id
                   ) REFERENCES users
                   (
                       id
                   ),
                       FOREIGN KEY
                   (
                       book_id
                   ) REFERENCES books
                   (
                       id
                   )
                       )
                   ''')

    # 5. Tabel Wishlists
    cursor.execute('''
                   CREATE TABLE IF NOT EXISTS wishlists
                   (
                       id
                       INTEGER
                       PRIMARY
                       KEY
                       AUTOINCREMENT,
                       user_id
                       INTEGER,
                       book_id
                       INTEGER,
                       FOREIGN
                       KEY
                   (
                       user_id
                   ) REFERENCES users
                   (
                       id
                   ),
                       FOREIGN KEY
                   (
                       book_id
                   ) REFERENCES books
                   (
                       id
                   )
                       )
                   ''')

    # 6. Tabel Reviews
    cursor.execute('''
                   CREATE TABLE IF NOT EXISTS reviews
                   (
                       id
                       INTEGER
                       PRIMARY
                       KEY
                       AUTOINCREMENT,
                       user_id
                       INTEGER,
                       book_id
                       INTEGER,
                       rating
                       INTEGER
                       CHECK
                   (
                       rating
                       >=
                       1
                       AND
                       rating
                       <=
                       5
                   ),
                       comment TEXT,
                       FOREIGN KEY
                   (
                       user_id
                   ) REFERENCES users
                   (
                       id
                   ),
                       FOREIGN KEY
                   (
                       book_id
                   ) REFERENCES books
                   (
                       id
                   )
                       )
                   ''')

    # 7. Tabel Notifications
    cursor.execute('''
                   CREATE TABLE IF NOT EXISTS notifications
                   (
                       id
                       INTEGER
                       PRIMARY
                       KEY
                       AUTOINCREMENT,
                       user_id
                       INTEGER,
                       message
                       TEXT
                       NOT
                       NULL,
                       is_read
                       BOOLEAN
                       DEFAULT
                       0,
                       created_at
                       TEXT
                       NOT
                       NULL,
                       FOREIGN
                       KEY
                   (
                       user_id
                   ) REFERENCES users
                   (
                       id
                   )
                       )
                   ''')

    # Masukkan Akun Admin Bawaan
    admin_pass = generate_password_hash('admin123')
    cursor.execute('''
                   INSERT
                   OR IGNORE INTO users (username, password, role, full_name, email) 
        VALUES (?, ?, 'admin', 'Administrator', 'admin@perpus.com')
                   ''', ('admin', admin_pass))

    # Masukkan Kategori Dummy
    cursor.execute(
        "INSERT OR IGNORE INTO categories (id, name) VALUES (1, 'Teknologi'), (2, 'Sains'), (3, 'Fiksi'), (4, 'Pengembangan Diri')")

    conn.commit()
    conn.close()


if __name__ == '__main__':
    init_db()
    print("Database berhasil dibuat secara manual!")