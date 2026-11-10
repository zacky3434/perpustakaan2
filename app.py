from flask import Flask, render_template, request, redirect, url_for, session, flash
import sqlite3
import os
from werkzeug.security import generate_password_hash, check_password_hash
from datetime import datetime, timedelta

from db import init_db, DB_PATH

app = Flask(__name__)
app.secret_key = 'kunci_rahasia_perpustakaan_pro'

init_db()

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
UPLOAD_FOLDER = os.path.join(BASE_DIR, 'static/uploads/covers')
app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER
os.makedirs(UPLOAD_FOLDER, exist_ok=True)


def get_db_connection():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


@app.context_processor
def inject_globals():
    unread_count = 0
    wishlist_count = 0
    if 'user_id' in session:
        conn = get_db_connection()
        count_row = conn.execute('SELECT COUNT(*) FROM notifications WHERE user_id = ? AND is_read = 0',
                                 (session['user_id'],)).fetchone()
        if count_row:
            unread_count = count_row[0]
        w_row = conn.execute('SELECT COUNT(*) FROM wishlists WHERE user_id = ?', (session['user_id'],)).fetchone()
        if w_row:
            wishlist_count = w_row[0]
        conn.close()
    return dict(unread_notifications=unread_count, wishlist_count=wishlist_count)


# ==========================================
# AUTHENTICATION
# ==========================================
@app.route('/')
def index():
    if 'user_id' in session:
        if session.get('role') == 'admin':
            return redirect(url_for('admin_dashboard'))
        return redirect(url_for('user_dashboard'))
    return redirect(url_for('login'))


@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password']
        conn = get_db_connection()
        user = conn.execute('SELECT * FROM users WHERE username = ?', (username,)).fetchone()
        conn.close()

        if user and check_password_hash(user['password'], password):
            session['user_id'] = user['id']
            session['username'] = user['username']
            session['role'] = user['role']
            session['full_name'] = user['full_name']
            return redirect(url_for('index'))
        else:
            flash('Username atau password salah!', 'error')
    return render_template('login.html')


@app.route('/register', methods=['GET', 'POST'])
def register():
    if request.method == 'POST':
        username = request.form['username']
        password = generate_password_hash(request.form['password'])
        full_name = request.form['full_name']
        email = request.form['email']
        conn = get_db_connection()
        try:
            conn.execute('INSERT INTO users (username, password, role, email, full_name) VALUES (?, ?, ?, ?, ?)',
                         (username, password, 'pengunjung', email, full_name))
            conn.commit()
            flash('Registrasi berhasil! Silakan login.', 'success')
            return redirect(url_for('login'))
        except sqlite3.IntegrityError:
            flash('Username sudah digunakan!', 'error')
        finally:
            conn.close()
    return render_template('register.html')


@app.route('/logout')
def logout():
    session.clear()
    return redirect(url_for('login'))


# ==========================================
# FITUR PENGUNJUNG (KATALOG, POPULER, REKOMENDASI, WISHLIST, ULASAN)
# ==========================================
@app.route('/user/dashboard')
def user_dashboard():
    if session.get('role') != 'pengunjung':
        return redirect(url_for('login'))

    search_query = request.args.get('q', '')
    cat_filter = request.args.get('cat', '')

    conn = get_db_connection()
    categories = conn.execute('SELECT * FROM categories').fetchall()

    # Daftar ID buku di wishlist user
    w_rows = conn.execute('SELECT book_id FROM wishlists WHERE user_id = ?', (session['user_id'],)).fetchall()
    wishlist_ids = [r['book_id'] for r in w_rows]

    # Buku Populer (Paling sering dipinjam + rata-rata rating)
    popular_books = conn.execute('''
                                 SELECT books.*,
                                        categories.name               as category_name,
                                        COUNT(DISTINCT borrowings.id) as borrow_count,
                                        ROUND(AVG(reviews.rating), 1) as avg_rating
                                 FROM books
                                          LEFT JOIN categories ON books.category_id = categories.id
                                          LEFT JOIN borrowings ON books.id = borrowings.book_id
                                          LEFT JOIN reviews ON books.id = reviews.book_id
                                 GROUP BY books.id
                                 ORDER BY borrow_count DESC, avg_rating DESC LIMIT 4
                                 ''').fetchall()

    # Rekomendasi Buku Berdasarkan Kategori yang Pernah Dipinjam / Wishlist User
    fav_cat = conn.execute('''
                           SELECT books.category_id
                           FROM borrowings
                                    JOIN books ON borrowings.book_id = books.id
                           WHERE borrowings.user_id = ?
                           GROUP BY books.category_id
                           ORDER BY COUNT(*) DESC LIMIT 1
                           ''', (session['user_id'],)).fetchone()

    if fav_cat and fav_cat['category_id']:
        recommended_books = conn.execute('''
                                         SELECT books.*,
                                                categories.name               as category_name,
                                                ROUND(AVG(reviews.rating), 1) as avg_rating
                                         FROM books
                                                  LEFT JOIN categories ON books.category_id = categories.id
                                                  LEFT JOIN reviews ON books.id = reviews.book_id
                                         WHERE books.category_id = ?
                                         GROUP BY books.id LIMIT 4
                                         ''', (fav_cat['category_id'],)).fetchall()
    else:
        recommended_books = conn.execute('''
                                         SELECT books.*,
                                                categories.name               as category_name,
                                                ROUND(AVG(reviews.rating), 1) as avg_rating
                                         FROM books
                                                  LEFT JOIN categories ON books.category_id = categories.id
                                                  LEFT JOIN reviews ON books.id = reviews.book_id
                                         GROUP BY books.id
                                         ORDER BY RANDOM() LIMIT 4
                                         ''').fetchall()

    # Query Katalog Utama
    query = '''
            SELECT books.*, categories.name as category_name, ROUND(AVG(reviews.rating), 1) as avg_rating
            FROM books
                     LEFT JOIN categories ON books.category_id = categories.id
                     LEFT JOIN reviews ON books.id = reviews.book_id \
            '''
    params = []

    if search_query:
        query += ' WHERE books.title LIKE ? OR books.author LIKE ? OR categories.name LIKE ?'
        params.extend(['%' + search_query + '%', '%' + search_query + '%', '%' + search_query + '%'])
    elif cat_filter:
        query += ' WHERE books.category_id = ?'
        params.append(cat_filter)

    query += ' GROUP BY books.id ORDER BY books.id DESC'
    books = conn.execute(query, params).fetchall()
    conn.close()

    return render_template('user_dashboard.html',
                           books=books,
                           popular_books=popular_books,
                           recommended_books=recommended_books,
                           wishlist_ids=wishlist_ids,
                           search_query=search_query,
                           categories=categories,
                           current_cat=cat_filter)


@app.route('/book/<int:id>')
def book_detail(id):
    if 'user_id' not in session:
        return redirect(url_for('login'))
    conn = get_db_connection()
    book = conn.execute('''
                        SELECT books.*,
                               categories.name               as category_name,
                               COUNT(DISTINCT borrowings.id) as borrow_count
                        FROM books
                                 LEFT JOIN categories ON books.category_id = categories.id
                                 LEFT JOIN borrowings ON books.id = borrowings.book_id
                        WHERE books.id = ?
                        GROUP BY books.id
                        ''', (id,)).fetchone()

    if not book:
        conn.close()
        return redirect(url_for('user_dashboard'))

    # Ambil ulasan & rating
    reviews = conn.execute('''
                           SELECT reviews.*, users.full_name, users.username
                           FROM reviews
                                    JOIN users ON reviews.user_id = users.id
                           WHERE reviews.book_id = ?
                           ORDER BY reviews.id DESC
                           ''', (id,)).fetchall()

    rating_stat = conn.execute('SELECT ROUND(AVG(rating), 1) as avg_r, COUNT(*) as cnt FROM reviews WHERE book_id = ?',
                               (id,)).fetchone()
    avg_rating = rating_stat['avg_r'] or 0
    review_count = rating_stat['cnt'] or 0

    # Rekomendasi buku sejenis berdasarkan kategori
    recommendations = conn.execute('''
                                   SELECT books.*,
                                          categories.name               as category_name,
                                          ROUND(AVG(reviews.rating), 1) as avg_rating
                                   FROM books
                                            LEFT JOIN categories ON books.category_id = categories.id
                                            LEFT JOIN reviews ON books.id = reviews.book_id
                                   WHERE books.category_id = ?
                                     AND books.id != ?
                                   GROUP BY books.id
                                       LIMIT 4
                                   ''', (book['category_id'], id)).fetchall()

    # Cek apakah ada di wishlist
    in_wishlist = conn.execute('SELECT 1 FROM wishlists WHERE user_id = ? AND book_id = ?',
                               (session['user_id'], id)).fetchone() is not None
    conn.close()

    today_date = datetime.now().strftime("%Y-%m-%d")
    default_return_date = (datetime.now() + timedelta(days=7)).strftime("%Y-%m-%d")

    return render_template('book_detail.html',
                           book=book,
                           reviews=reviews,
                           avg_rating=avg_rating,
                           review_count=review_count,
                           recommendations=recommendations,
                           in_wishlist=in_wishlist,
                           today_date=today_date,
                           default_return_date=default_return_date)


@app.route('/book/<int:book_id>/review', methods=['POST'])
def add_review(book_id):
    if session.get('role') != 'pengunjung':
        return redirect(url_for('login'))
    rating = int(request.form.get('rating', 5))
    comment = request.form.get('comment', '').strip()

    conn = get_db_connection()
    existing = conn.execute('SELECT id FROM reviews WHERE user_id = ? AND book_id = ?',
                            (session['user_id'], book_id)).fetchone()
    if existing:
        conn.execute('UPDATE reviews SET rating = ?, comment = ? WHERE id = ?', (rating, comment, existing['id']))
        flash('Ulasan Anda berhasil diperbarui!', 'success')
    else:
        conn.execute('INSERT INTO reviews (user_id, book_id, rating, comment) VALUES (?, ?, ?, ?)',
                     (session['user_id'], book_id, rating, comment))
        flash('Terima kasih atas rating dan ulasan Anda!', 'success')
    conn.commit()
    conn.close()
    return redirect(url_for('book_detail', id=book_id))


@app.route('/wishlist/toggle/<int:book_id>', methods=['POST'])
def toggle_wishlist(book_id):
    if session.get('role') != 'pengunjung':
        return redirect(url_for('login'))
    conn = get_db_connection()
    existing = conn.execute('SELECT id FROM wishlists WHERE user_id = ? AND book_id = ?',
                            (session['user_id'], book_id)).fetchone()
    if existing:
        conn.execute('DELETE FROM wishlists WHERE id = ?', (existing['id'],))
        flash('Buku dihapus dari Wishlist.', 'info')
    else:
        conn.execute('INSERT INTO wishlists (user_id, book_id) VALUES (?, ?)', (session['user_id'], book_id))
        flash('Buku disimpan ke Wishlist!', 'success')
    conn.commit()
    conn.close()
    return redirect(request.referrer or url_for('user_dashboard'))


@app.route('/user/wishlist')
def user_wishlist():
    if session.get('role') != 'pengunjung':
        return redirect(url_for('login'))
    conn = get_db_connection()
    books = conn.execute('''
                         SELECT books.*, categories.name as category_name, ROUND(AVG(reviews.rating), 1) as avg_rating
                         FROM wishlists
                                  JOIN books ON wishlists.book_id = books.id
                                  LEFT JOIN categories ON books.category_id = categories.id
                                  LEFT JOIN reviews ON books.id = reviews.book_id
                         WHERE wishlists.user_id = ?
                         GROUP BY books.id
                         ORDER BY wishlists.id DESC
                         ''', (session['user_id'],)).fetchall()
    conn.close()
    return render_template('user_wishlist.html', books=books)


@app.route('/borrow/<int:book_id>', methods=['POST'])
def borrow_book(book_id):
    if session.get('role') != 'pengunjung':
        return redirect(url_for('login'))

    borrow_date = request.form.get('borrow_date') or datetime.now().strftime("%Y-%m-%d")
    return_due_date = request.form.get('return_due_date') or (datetime.now() + timedelta(days=7)).strftime("%Y-%m-%d")

    conn = get_db_connection()
    book = conn.execute('SELECT * FROM books WHERE id = ?', (book_id,)).fetchone()
    existing = conn.execute(
        "SELECT * FROM borrowings WHERE user_id = ? AND book_id = ? AND status IN ('menunggu', 'dipinjam', 'menunggu pengembalian')",
        (session['user_id'], book_id)).fetchone()

    if not book or not book['is_available']:
        flash('Buku tidak tersedia.', 'error')
    elif existing:
        flash('Anda sudah mengajukan atau sedang meminjam buku ini.', 'error')
    else:
        now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        conn.execute('''
                     INSERT INTO borrowings (user_id, book_id, request_date, borrow_date, return_due_date, status)
                     VALUES (?, ?, ?, ?, ?, 'menunggu')
                     ''', (session['user_id'], book_id, now, borrow_date, return_due_date))

        conn.execute("INSERT INTO notifications (user_id, message, created_at) VALUES (?, ?, ?)",
                     (session['user_id'],
                      f"Pengajuan pinjam '{book['title']}' ({borrow_date} s/d {return_due_date}) terkirim. Menunggu persetujuan admin.",
                      now))
        conn.commit()
        flash('Pengajuan peminjaman beserta jadwal berhasil dikirim!', 'success')
    conn.close()
    return redirect(url_for('user_history'))


@app.route('/return/<int:borrow_id>', methods=['POST'])
def return_book(borrow_id):
    if session.get('role') != 'pengunjung':
        return redirect(url_for('login'))
    conn = get_db_connection()
    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    conn.execute("UPDATE borrowings SET status = 'menunggu pengembalian' WHERE id = ? AND user_id = ?",
                 (borrow_id, session['user_id']))
    conn.execute("INSERT INTO notifications (user_id, message, created_at) VALUES (?, ?, ?)",
                 (session['user_id'],
                  "Pengajuan pengembalian buku terkirim. Silakan serahkan fisik buku ke meja pustakawan.", now))
    conn.commit()
    conn.close()
    flash('Pengajuan pengembalian dikirim ke pustakawan!', 'success')
    return redirect(url_for('user_history'))


@app.route('/user/history')
def user_history():
    if session.get('role') != 'pengunjung':
        return redirect(url_for('login'))
    conn = get_db_connection()
    borrowings = conn.execute('''
                              SELECT borrowings.*, books.title, books.author
                              FROM borrowings
                                       JOIN books ON borrowings.book_id = books.id
                              WHERE borrowings.user_id = ?
                              ORDER BY borrowings.id DESC
                              ''', (session['user_id'],)).fetchall()
    conn.close()
    today_date = datetime.now().strftime("%Y-%m-%d")
    return render_template('user_history.html', borrowings=borrowings, today_date=today_date)


@app.route('/user/notifications')
def user_notifications():
    if session.get('role') != 'pengunjung':
        return redirect(url_for('login'))
    conn = get_db_connection()
    notifs = conn.execute('SELECT * FROM notifications WHERE user_id = ? ORDER BY id DESC',
                          (session['user_id'],)).fetchall()
    conn.execute('UPDATE notifications SET is_read = 1 WHERE user_id = ? AND is_read = 0', (session['user_id'],))
    conn.commit()
    conn.close()
    return render_template('notifications.html', notifications=notifs)


@app.route('/user/profile', methods=['GET', 'POST'])
def user_profile():
    if 'user_id' not in session:
        return redirect(url_for('login'))
    conn = get_db_connection()
    if request.method == 'POST':
        action_type = request.form.get('action_type', 'profile')
        if action_type == 'password':
            new_password = request.form.get('new_password', '')
            if len(new_password) >= 4:
                hashed = generate_password_hash(new_password)
                conn.execute('UPDATE users SET password = ? WHERE id = ?', (hashed, session['user_id']))
                conn.commit()
                flash('Password berhasil diperbarui!', 'success')
            else:
                flash('Password minimal 4 karakter.', 'error')
        else:
            full_name = request.form['full_name']
            email = request.form['email']
            conn.execute('UPDATE users SET full_name = ?, email = ? WHERE id = ?',
                         (full_name, email, session['user_id']))
            conn.commit()
            session['full_name'] = full_name
            flash('Profil berhasil diperbarui!', 'success')

    user = conn.execute('SELECT * FROM users WHERE id = ?', (session['user_id'],)).fetchone()

    # Statistik pengguna untuk tampilan profil modern
    total_borrowed = \
    conn.execute('SELECT COUNT(*) FROM borrowings WHERE user_id = ?', (session['user_id'],)).fetchone()[0]
    active_borrowed = conn.execute(
        "SELECT COUNT(*) FROM borrowings WHERE user_id = ? AND status IN ('dipinjam', 'menunggu', 'menunggu pengembalian')",
        (session['user_id'],)).fetchone()[0]
    wishlist_total = conn.execute('SELECT COUNT(*) FROM wishlists WHERE user_id = ?', (session['user_id'],)).fetchone()[
        0]
    reviews_total = conn.execute('SELECT COUNT(*) FROM reviews WHERE user_id = ?', (session['user_id'],)).fetchone()[0]
    total_fines = conn.execute('SELECT SUM(fine) FROM borrowings WHERE user_id = ?', (session['user_id'],)).fetchone()[
                      0] or 0
    conn.close()

    stats = {
        'total_borrowed': total_borrowed,
        'active_borrowed': active_borrowed,
        'wishlist_total': wishlist_total,
        'reviews_total': reviews_total,
        'total_fines': total_fines
    }
    return render_template('profile.html', user=user, stats=stats)


# ==========================================
# FITUR ADMIN (DASBOR, BUKU, TRANSAKSI, LAPORAN)
# ==========================================
@app.route('/admin/dashboard')
def admin_dashboard():
    if session.get('role') != 'admin':
        return redirect(url_for('login'))
    conn = get_db_connection()
    total_books = conn.execute('SELECT COUNT(*) FROM books').fetchone()[0]
    total_users = conn.execute('SELECT COUNT(*) FROM users WHERE role="pengunjung"').fetchone()[0]
    pending_req = conn.execute(
        "SELECT COUNT(*) FROM borrowings WHERE status='menunggu' OR status='menunggu pengembalian'").fetchone()[0]

    books = conn.execute('''
                         SELECT books.*, categories.name as category_name
                         FROM books
                                  LEFT JOIN categories ON books.category_id = categories.id
                         ''').fetchall()
    categories = conn.execute('SELECT * FROM categories').fetchall()
    conn.close()
    return render_template('admin_dashboard.html', books=books, categories=categories,
                           total_books=total_books, total_users=total_users, pending_req=pending_req)


@app.route('/admin/book/add', methods=['POST'])
def add_book():
    if session.get('role') != 'admin':
        return redirect(url_for('login'))
    conn = get_db_connection()
    conn.execute('INSERT INTO books (title, author, category_id, description) VALUES (?, ?, ?, ?)',
                 (request.form['title'], request.form['author'], request.form['category_id'],
                  request.form['description']))
    conn.commit()
    conn.close()
    flash('Buku berhasil ditambahkan ke katalog!', 'success')
    return redirect(url_for('admin_dashboard'))


@app.route('/admin/book/delete/<int:id>')
def delete_book(id):
    if session.get('role') != 'admin':
        return redirect(url_for('login'))
    conn = get_db_connection()
    conn.execute('DELETE FROM books WHERE id = ?', (id,))
    conn.commit()
    conn.close()
    flash('Buku berhasil dihapus!', 'success')
    return redirect(url_for('admin_dashboard'))


@app.route('/admin/borrowings')
def admin_borrowings():
    if session.get('role') != 'admin':
        return redirect(url_for('login'))
    conn = get_db_connection()
    transactions = conn.execute('''
                                SELECT borrowings.*, books.title as book_title, users.full_name as user_name
                                FROM borrowings
                                         JOIN books ON borrowings.book_id = books.id
                                         JOIN users ON borrowings.user_id = users.id
                                ORDER BY borrowings.id DESC
                                ''').fetchall()
    conn.close()
    return render_template('admin_borrowings.html', transactions=transactions)


@app.route('/admin/borrow/action/<int:borrow_id>/<action>')
def admin_borrow_action(borrow_id, action):
    if session.get('role') != 'admin':
        return redirect(url_for('login'))
    conn = get_db_connection()
    now = datetime.now()

    borrow_data = conn.execute('SELECT * FROM borrowings WHERE id = ?', (borrow_id,)).fetchone()
    book_id = borrow_data['book_id']
    user_id = borrow_data['user_id']

    if action == 'approve':
        b_date = borrow_data['borrow_date'] or now.strftime("%Y-%m-%d")
        d_date = borrow_data['return_due_date'] or (now + timedelta(days=7)).strftime("%Y-%m-%d")
        conn.execute("UPDATE borrowings SET status='dipinjam', borrow_date=?, return_due_date=? WHERE id=?",
                     (b_date, d_date, borrow_id))
        conn.execute("UPDATE books SET is_available=0 WHERE id=?", (book_id,))
        conn.execute("INSERT INTO notifications (user_id, message, created_at) VALUES (?, ?, ?)",
                     (user_id, f"Peminjaman buku disetujui! Jadwal pinjam: {b_date} s/d {d_date}.",
                      now.strftime("%Y-%m-%d %H:%M:%S")))
        flash('Peminjaman disetujui!', 'success')

    elif action == 'reject':
        conn.execute("UPDATE borrowings SET status='ditolak' WHERE id=?", (borrow_id,))
        conn.execute("INSERT INTO notifications (user_id, message, created_at) VALUES (?, ?, ?)",
                     (user_id, "Pengajuan peminjaman buku Anda ditolak oleh pustakawan.",
                      now.strftime("%Y-%m-%d %H:%M:%S")))
        flash('Peminjaman ditolak.', 'info')

    elif action == 'return':
        actual_return_date = now.strftime("%Y-%m-%d")
        due_date_str = borrow_data['return_due_date']
        fine_amount = 0

        if due_date_str:
            due_date = datetime.strptime(due_date_str, "%Y-%m-%d")
            if now > due_date:
                days_late = (now - due_date).days
                fine_amount = days_late * 5000

        conn.execute("UPDATE borrowings SET status='dikembalikan', actual_return_date=?, fine=? WHERE id=?",
                     (actual_return_date, fine_amount, borrow_id))
        conn.execute("UPDATE books SET is_available=1 WHERE id=?", (book_id,))

        msg = "Buku telah dikembalikan dan dicatat oleh pustakawan."
        if fine_amount > 0:
            msg += f" Keterlambatan tercatat, total denda: Rp{fine_amount:,}."

        conn.execute("INSERT INTO notifications (user_id, message, created_at) VALUES (?, ?, ?)",
                     (user_id, msg, now.strftime("%Y-%m-%d %H:%M:%S")))

        if fine_amount > 0:
            flash(f'Pengembalian selesai. Terkena denda keterlambatan: Rp{fine_amount:,}', 'warning')
        else:
            flash('Pengembalian buku berhasil dikonfirmasi!', 'success')

    conn.commit()
    conn.close()
    return redirect(url_for('admin_borrowings'))


@app.route('/admin/reports')
def admin_reports():
    if session.get('role') != 'admin':
        return redirect(url_for('login'))

    conn = get_db_connection()
    total_fines = conn.execute("SELECT SUM(fine) FROM borrowings WHERE fine > 0").fetchone()[0] or 0
    total_completed = conn.execute("SELECT COUNT(*) FROM borrowings WHERE status='dikembalikan'").fetchone()[0]

    report_data = conn.execute('''
                               SELECT borrowings.*, books.title as book_title, users.full_name as user_name
                               FROM borrowings
                                        JOIN books ON borrowings.book_id = books.id
                                        JOIN users ON borrowings.user_id = users.id
                               ORDER BY borrowings.id DESC
                               ''').fetchall()
    conn.close()

    return render_template('admin_reports.html', report_data=report_data, total_fines=total_fines,
                           total_completed=total_completed)


if __name__ == '__main__':
    app.run(debug=True)