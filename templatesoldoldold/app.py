from flask import Flask, render_template, request, redirect, url_for, session
import sqlite3
from datetime import datetime
import hashlib

app = Flask(__name__)
app.secret_key = 'supersecretkey123'  # Замените на свой секретный ключ


# ===================== ИНИЦИАЛИЗАЦИЯ БАЗЫ ДАННЫХ =====================
def init_db():
    conn = sqlite3.connect('database_helpdesk.db')
    c = conn.cursor()

    # Таблица заявок
    c.execute('''CREATE TABLE IF NOT EXISTS tickets (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        user_name TEXT NOT NULL,
        user_email TEXT NOT NULL,
        subject TEXT NOT NULL,
        description TEXT NOT NULL,
        status TEXT DEFAULT 'Новая',
        operator_answer TEXT,
        created_at TEXT NOT NULL,
        updated_at TEXT
    )''')

    # Таблица операторов (в демо-целях простой логин/пароль)
    c.execute('''CREATE TABLE IF NOT EXISTS operators (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        username TEXT NOT NULL,
        password TEXT NOT NULL
    )''')

    # Добавляем тестового оператора (логин: admin, пароль: admin123)
    hashed_pwd = hashlib.sha256('admin123'.encode()).hexdigest()
    c.execute("INSERT OR IGNORE INTO operators (id, username, password) VALUES (1, 'admin', ?)", (hashed_pwd,))

    conn.commit()
    conn.close()


# ===================== ВСПОМОГАТЕЛЬНЫЕ ФУНКЦИИ =====================
def get_db_connection():
    conn = sqlite3.connect('database_helpdesk.db')
    conn.row_factory = sqlite3.Row
    return conn


def operator_required(f):
    def decorated_function(*args, **kwargs):
        if not session.get('operator_logged_in'):
            return redirect(url_for('operator_login'))
        return f(*args, **kwargs)

    decorated_function.__name__ = f.__name__
    return decorated_function


# ===================== ПОЛЬЗОВАТЕЛЬСКАЯ ЧАСТЬ =====================
@app.route('/')
def index():
    return render_template('user_form.html')


@app.route('/create_ticket', methods=['POST'])
def create_ticket():
    user_name = request.form['user_name']
    user_email = request.form['user_email']
    subject = request.form['subject']
    description = request.form['description']
    created_at = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    conn = get_db_connection()
    conn.execute('INSERT INTO tickets (user_name, user_email, subject, description, created_at) VALUES (?, ?, ?, ?, ?)',
                 (user_name, user_email, subject, description, created_at))
    conn.commit()
    ticket_id = conn.execute('SELECT last_insert_rowid()').fetchone()[0]
    conn.close()

    return f'''
    <html>
    <head><link href="https://cdn.jsdelivr.net/npm/bootstrap@5.1.3/dist/css/bootstrap.min.css" rel="stylesheet"></head>
    <body>
        <div class="container mt-5">
            <div class="alert alert-success">
                <h4>Заявка #{ticket_id} успешно создана!</h4>
                <p>Ваш номер заявки: <strong>{ticket_id}</strong></p>
                <p>Статус заявки вы можете проверить <a href="/check_ticket?ticket_id={ticket_id}&email={user_email}">здесь</a></p>
                <a href="/" class="btn btn-primary">Создать новую заявку</a>
            </div>
        </div>
    </body>
    </html>
    '''


@app.route('/check_ticket')
def check_ticket():
    ticket_id = request.args.get('ticket_id')
    email = request.args.get('email')

    if not ticket_id or not email:
        return render_template('check_ticket_form.html')

    conn = get_db_connection()
    ticket = conn.execute('SELECT * FROM tickets WHERE id = ? AND user_email = ?', (ticket_id, email)).fetchone()
    conn.close()

    if ticket:
        return render_template('ticket_status.html', ticket=ticket)
    else:
        return '<div class="alert alert-danger">Заявка не найдена. Проверьте номер и email.</div>'


# ===================== ОПЕРАТОРСКАЯ ЧАСТЬ =====================
@app.route('/operator/login', methods=['GET', 'POST'])
def operator_login():
    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password']
        hashed_pwd = hashlib.sha256(password.encode()).hexdigest()

        conn = get_db_connection()
        operator = conn.execute('SELECT * FROM operators WHERE username = ? AND password = ?',
                                (username, hashed_pwd)).fetchone()
        conn.close()

        if operator:
            session['operator_logged_in'] = True
            session['operator_name'] = username
            return redirect(url_for('operator_dashboard'))
        else:
            return '<div class="alert alert-danger">Неверный логин или пароль</div>'

    return render_template('operator_login.html')


@app.route('/operator/dashboard')
@operator_required
def operator_dashboard():
    conn = get_db_connection()
    tickets = conn.execute('''SELECT * FROM tickets ORDER BY
    CASE
    status
    WHEN \'Новая\' THEN 1
    WHEN \'В работе\' THEN 2
    WHEN \'Закрыта\' THEN 3
    END, id
    DESC
    ''').fetchall()
    conn.close()
    return render_template('operator_dashboard.html', tickets=tickets)

@app.route('/operator/ticket/<int:ticket_id>', methods=['GET', 'POST'])
@operator_required
def operator_ticket(ticket_id):
    conn = get_db_connection()

    if request.method == 'POST':
        status = request.form['status']
        answer = request.form['answer']
        updated_at = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

        conn.execute('UPDATE tickets SET status = ?, operator_answer = ?, updated_at = ? WHERE id = ?',
                     (status, answer, updated_at, ticket_id))
        conn.commit()
        conn.close()
        return redirect(url_for('operator_dashboard'))

    ticket = conn.execute('SELECT * FROM tickets WHERE id = ?', (ticket_id,)).fetchone()
    conn.close()
    return render_template('operator_ticket.html', ticket=ticket)

@app.route('/operator/logout')
def operator_logout():
    session.clear()
    return redirect(url_for('operator_login'))

if __name__ == '__main__':
    init_db()
    app.run(debug=True)