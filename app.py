from flask import Flask, render_template, request, redirect, url_for, session, flash
import sqlite3
from datetime import datetime
import hashlib
import os
import re

app = Flask(__name__)
app.secret_key = 'your-secret-key-change-this-in-production-12345'


# ===================== ИНИЦИАЛИЗАЦИЯ БАЗЫ ДАННЫХ =====================
def init_db():
    if not os.path.exists('databases'):
        os.makedirs('databases')

    db_path = 'databases/database_helpdesk.db'

    # Проверяем, существует ли база данных
    db_exists = os.path.exists(db_path)

    conn = sqlite3.connect(db_path)
    c = conn.cursor()
    # Таблица администраторов
    c.execute('''CREATE TABLE IF NOT EXISTS admins (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            username TEXT UNIQUE NOT NULL,
            password TEXT NOT NULL,
            last_name TEXT,
            first_name TEXT,
            middle_name TEXT,
            email TEXT UNIQUE,
            created_at TEXT NOT NULL
        )''')

    # Добавляем тестового администратора
    c.execute("SELECT COUNT(*) FROM admins")
    if c.fetchone()[0] == 0:
        hashed_pwd_admin = hashlib.sha256('admin123'.encode()).hexdigest()
        c.execute(
            "INSERT INTO admins (username, password, last_name, first_name, email, created_at) VALUES (?, ?, ?, ?, ?, ?)",
            ('admin', hashed_pwd_admin, 'Администраторов', 'Админ', 'admin@helpdesk.ru',
             datetime.now().strftime("%Y-%m-%d %H:%M:%S")))
        print("✅ Добавлен администратор: admin / admin123")

    # Таблица пользователей
    c.execute('''CREATE TABLE IF NOT EXISTS users (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        username TEXT UNIQUE NOT NULL,
        email TEXT UNIQUE NOT NULL,
        password TEXT NOT NULL,
        last_name TEXT,
        first_name TEXT,
        middle_name TEXT,
        post TEXT,
        phone TEXT,
        created_at TEXT NOT NULL,
        is_admin INTEGER DEFAULT 0
    )''')

    # Таблица заявок
    c.execute('''CREATE TABLE IF NOT EXISTS tickets (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        user_id INTEGER NOT NULL,
        subject TEXT,
        description TEXT NOT NULL,
        status TEXT DEFAULT 'new',
        priority TEXT DEFAULT 'medium',
        operator_answer TEXT,
        created_at TEXT NOT NULL,
        updated_at TEXT,
        completed_at TEXT,
        assigned_to INTEGER,
        category TEXT,
        problem_type TEXT,
        location TEXT,
        office TEXT,
        assistant_id TEXT,
        printer_manufacturer TEXT,
        printer_model TEXT,
        printer_problem TEXT,
        FOREIGN KEY (user_id) REFERENCES users (id),
        FOREIGN KEY (assigned_to) REFERENCES operators (id)
    )''')

    # Добавляем колонку subject, если её нет (для старых баз)
    try:
        c.execute("ALTER TABLE tickets ADD COLUMN subject TEXT")
        print("✅ Добавлена колонка subject в таблицу tickets")
    except sqlite3.OperationalError:
        print("Колонка subject уже существует")

    # Добавляем другие колонки, если их нет
    for column in ['completed_at', 'assigned_to', 'category', 'problem_type', 'location', 'office', 'assistant_id']:
        try:
            c.execute(f"ALTER TABLE tickets ADD COLUMN {column} TEXT")
            print(f"✅ Добавлена колонка {column}")
        except sqlite3.OperationalError:
            pass  # Колонка уже существует

    # Таблица операторов
    c.execute('''CREATE TABLE IF NOT EXISTS operators (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        username TEXT NOT NULL UNIQUE,
        password TEXT NOT NULL,
        last_name TEXT,
        first_name TEXT,
        middle_name TEXT,
        post TEXT,
        phone TEXT
    )''')

    # Добавляем тестового оператора (только если таблица пустая)
    c.execute("SELECT COUNT(*) FROM operators")
    if c.fetchone()[0] == 0:
        hashed_pwd_admin = hashlib.sha256('admin123'.encode()).hexdigest()
        c.execute(
            "INSERT INTO operators (username, password, last_name, first_name, middle_name, post) VALUES (?, ?, ?, ?, ?, ?)",
            ('admin', hashed_pwd_admin, 'Иванов', 'Иван', 'Иванович', 'Главный специалист IT отдела'))
        print("✅ Добавлен оператор: admin / admin123")

    # Добавляем тестового пользователя (только если таблица пустая)
    c.execute("SELECT COUNT(*) FROM users")
    if c.fetchone()[0] == 0:
        hashed_pwd_user = hashlib.sha256('user123'.encode()).hexdigest()
        c.execute(
            "INSERT INTO users (username, email, password, last_name, first_name, middle_name, post, phone, created_at) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
            ('user', 'user@example.com', hashed_pwd_user, 'Петров', 'Петр', 'Петрович',
             'Врач-терапевт', '79012345678', datetime.now().strftime("%Y-%m-%d %H:%M:%S")))
        print("✅ Добавлен пользователь: user / user123")

    conn.commit()
    conn.close()
    print("🎉 База данных готова!")


def get_db_connection():
    conn = sqlite3.connect('databases/database_helpdesk.db')
    conn.row_factory = sqlite3.Row
    return conn


def login_required(f):
    def decorated_function(*args, **kwargs):
        if not session.get('user_id'):
            flash('Пожалуйста, войдите в систему', 'warning')
            return redirect(url_for('login'))
        return f(*args, **kwargs)

    decorated_function.__name__ = f.__name__
    return decorated_function


def operator_required(f):
    def decorated_function(*args, **kwargs):
        if not session.get('operator_logged_in'):
            flash('Доступ только для операторов', 'danger')
            return redirect(url_for('operator_login'))
        return f(*args, **kwargs)

    decorated_function.__name__ = f.__name__
    return decorated_function


# ===================== ГЛАВНОЕ МЕНЮ =====================
@app.route('/')
def index():
    if session.get('user_id'):
        return redirect(url_for('dashboard'))
    return render_template('index.html')


@app.route('/info')
def info():
    """Страница с информацией о работе техподдержки"""
    return render_template('info.html')


@app.route('/offices')
def offices():
    """Страница с кабинетами IT-отдела"""
    return render_template('offices.html')


# ===================== РЕГИСТРАЦИЯ =====================
@app.route('/register', methods=['GET', 'POST'])
def register():
    if request.method == 'POST':
        username = request.form['username']
        email = request.form['email']
        password = request.form['password']
        last_name = request.form['last_name']
        first_name = request.form['first_name']
        middle_name = request.form.get('middle_name', '')
        post = request.form['post']
        phone = request.form['phone']

        # ============ ПРОВЕРКА ПАРОЛЯ ============
        errors = []

        # Проверка длины пароля (минимум 7 символов)
        if len(password) < 7:
            errors.append('❌ Пароль должен содержать минимум 7 символов (пароли от 1 до 6 символов запрещены)')

        # Дополнительные проверки для надежности
        if not any(c.isupper() for c in password):
            errors.append('❌ Пароль должен содержать хотя бы одну заглавную букву')

        if not any(c.islower() for c in password):
            errors.append('❌ Пароль должен содержать хотя бы одну строчную букву')

        if not any(c.isdigit() for c in password):
            errors.append('❌ Пароль должен содержать хотя бы одну цифру')

        # Проверка на простые пароли
        simple_passwords = ['1234567', '12345678', 'qwerty', 'password', 'admin123', 'user123']
        if password.lower() in simple_passwords:
            errors.append('❌ Пароль слишком простой. Придумайте более надежный пароль')

        # Если есть ошибки - показываем их
        if errors:
            for error in errors:
                flash(error, 'danger')
            return render_template('register.html',
                                   username=username, email=email,
                                   last_name=last_name, first_name=first_name,
                                   middle_name=middle_name, post=post, phone=phone)

        # Валидация телефона
        phone = re.sub(r'\D', '', phone)
        if not re.match(r'^[78]\d{10}$', phone):
            flash('Введите корректный российский номер телефона (10 цифр после 7 или 8)', 'danger')
            return render_template('register.html', username=username, email=email,
                                   last_name=last_name, first_name=first_name,
                                   middle_name=middle_name, post=post, phone=phone)

        # Валидация ФИО
        for name in [last_name, first_name]:
            if not re.match(r'^[А-ЯЁ][а-яё]*(?:-[А-ЯЁ][а-яё]*)?$', name):
                flash('Фамилия и имя должны начинаться с заглавной буквы и содержать только русские буквы', 'danger')
                return render_template('register.html', username=username, email=email,
                                       last_name=last_name, first_name=first_name,
                                       middle_name=middle_name, post=post, phone=phone)

        hashed_pwd = hashlib.sha256(password.encode()).hexdigest()
        created_at = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

        conn = get_db_connection()

        # ============ ПРОВЕРКА НА СУЩЕСТВОВАНИЕ НОМЕРА ТЕЛЕФОНА ============
        existing_phone = conn.execute('SELECT phone FROM users WHERE phone = ?', (phone,)).fetchone()
        if existing_phone:
            flash('❌ Пользователь с таким номером телефона уже зарегистрирован', 'danger')
            conn.close()
            return render_template('register.html', username=username, email=email,
                                   last_name=last_name, first_name=first_name,
                                   middle_name=middle_name, post=post, phone=phone)

        try:
            conn.execute('''INSERT INTO users 
                (username, email, password, last_name, first_name, middle_name, post, phone, created_at) 
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)''',
                         (username, email, hashed_pwd, last_name, first_name, middle_name, post, phone, created_at))
            conn.commit()
            flash('✅ Регистрация успешна! Теперь вы можете войти', 'success')
            return redirect(url_for('login'))
        except sqlite3.IntegrityError as e:
            # Проверяем, какое именно ограничение нарушено
            if 'username' in str(e):
                flash('❌ Пользователь с таким логином уже существует', 'danger')
            elif 'email' in str(e):
                flash('❌ Пользователь с таким email уже существует', 'danger')
            else:
                flash('❌ Пользователь с таким именем или email уже существует', 'danger')
            return render_template('register.html', username=username, email=email,
                                   last_name=last_name, first_name=first_name,
                                   middle_name=middle_name, post=post, phone=phone)
        finally:
            conn.close()

    return render_template('register.html')


@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        username_or_email = request.form['username'].strip()
        password = request.form['password']
        hashed_pwd = hashlib.sha256(password.encode()).hexdigest()

        conn = get_db_connection()

        # Проверяем, что ввел пользователь: логин или email
        # Если есть @ - значит email, иначе логин
        if '@' in username_or_email:
            # Вход по email
            user = conn.execute('SELECT * FROM users WHERE email = ? AND password = ?',
                                (username_or_email, hashed_pwd)).fetchone()
        else:
            # Вход по логину
            user = conn.execute('SELECT * FROM users WHERE username = ? AND password = ?',
                                (username_or_email, hashed_pwd)).fetchone()

        conn.close()

        if user:
            session['user_id'] = user['id']
            session['username'] = user['username']
            session['full_name'] = f"{user['last_name']} {user['first_name']} {user['middle_name'] or ''}"
            flash(f'Добро пожаловать, {session["full_name"]}!', 'success')
            return redirect(url_for('dashboard'))
        else:
            flash('Неверный логин/email или пароль', 'danger')

    return render_template('login.html')


@app.route('/logout')
def logout():
    session.clear()
    flash('Вы вышли из системы', 'info')
    return redirect(url_for('index'))


@app.route('/dashboard')
@login_required
def dashboard():
    conn = get_db_connection()
    tickets = conn.execute('SELECT * FROM tickets WHERE user_id = ? ORDER BY id DESC',
                           (session['user_id'],)).fetchall()
    conn.close()
    return render_template('profile.html', tickets=tickets)


# ===================== АДМИН ПАНЕЛЬ =====================

def admin_required(f):
    def decorated_function(*args, **kwargs):
        if not session.get('admin_logged_in'):
            flash('Доступ только для администраторов', 'danger')
            return redirect(url_for('admin_login'))
        return f(*args, **kwargs)

    decorated_function.__name__ = f.__name__
    return decorated_function


@app.route('/admin/login', methods=['GET', 'POST'])
def admin_login():
    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password']
        hashed_pwd = hashlib.sha256(password.encode()).hexdigest()

        conn = get_db_connection()
        admin = conn.execute('SELECT * FROM admins WHERE username = ? AND password = ?',
                             (username, hashed_pwd)).fetchone()
        conn.close()

        if admin:
            session['admin_logged_in'] = True
            session['admin_id'] = admin['id']
            session['admin_username'] = admin['username']
            full_name = f"{admin['last_name'] or ''} {admin['first_name'] or ''} {admin['middle_name'] or ''}".strip()
            session['admin_full_name'] = full_name if full_name else admin['username']
            flash('Добро пожаловать в панель администратора!', 'success')
            return redirect(url_for('admin_dashboard'))
        else:
            flash('Неверный логин или пароль', 'danger')

    return render_template('admins/admin_login.html')


@app.route('/admin/dashboard')
@admin_required
def admin_dashboard():
    conn = get_db_connection()

    # Статистика
    total_users = conn.execute('SELECT COUNT(*) FROM users').fetchone()[0]
    total_operators = conn.execute('SELECT COUNT(*) FROM operators').fetchone()[0]
    total_tickets = conn.execute('SELECT COUNT(*) FROM tickets').fetchone()[0]
    new_tickets = conn.execute('SELECT COUNT(*) FROM tickets WHERE status = "new"').fetchone()[0]
    in_progress = conn.execute('SELECT COUNT(*) FROM tickets WHERE status = "in_progress"').fetchone()[0]
    resolved = conn.execute('SELECT COUNT(*) FROM tickets WHERE status IN ("resolved", "closed")').fetchone()[0]

    # Последние заявки
    recent_tickets = conn.execute('''
        SELECT t.*, u.last_name, u.first_name 
        FROM tickets t 
        JOIN users u ON t.user_id = u.id 
        ORDER BY t.id DESC LIMIT 10
    ''').fetchall()

    conn.close()

    return render_template('admins/admin_dashboard.html',
                           total_users=total_users,
                           total_operators=total_operators,
                           total_tickets=total_tickets,
                           new_tickets=new_tickets,
                           in_progress=in_progress,
                           resolved=resolved,
                           recent_tickets=recent_tickets)


@app.route('/admin/users')
@admin_required
def admin_users():
    conn = get_db_connection()
    users = conn.execute('SELECT * FROM users ORDER BY id DESC').fetchall()
    conn.close()
    return render_template('admins/admin_users.html', users=users)


@app.route('/admin/operators')
@admin_required
def admin_operators():
    conn = get_db_connection()
    operators = conn.execute('SELECT * FROM operators ORDER BY id DESC').fetchall()
    conn.close()
    return render_template('admins/admin_operators.html', operators=operators)


@app.route('/admin/tickets')
@admin_required
def admin_tickets():
    conn = get_db_connection()
    tickets = conn.execute('''
        SELECT t.*, u.last_name, u.first_name, u.username,
               o.last_name as op_last_name, o.first_name as op_first_name
        FROM tickets t 
        JOIN users u ON t.user_id = u.id 
        LEFT JOIN operators o ON t.assigned_to = o.id
        ORDER BY t.id DESC
    ''').fetchall()
    conn.close()
    return render_template('admins/admin_tickets.html', tickets=tickets)


@app.route('/admin/settings')
@admin_required
def admin_settings():
    return render_template('admins/admin_settings.html')


@app.route('/admin/profile')
@admin_required
def admin_profile():
    conn = get_db_connection()
    admin = conn.execute('SELECT * FROM admins WHERE id = ?', (session['admin_id'],)).fetchone()
    conn.close()
    return render_template('admins/admin_profile.html', admin=admin)


@app.route('/admin/logout')
def admin_logout():
    session.pop('admin_logged_in', None)
    session.pop('admin_id', None)
    session.pop('admin_username', None)
    session.pop('admin_full_name', None)
    flash('Вы вышли из панели администратора', 'info')
    return redirect(url_for('admin_login'))


# ===================== РЕДАКТИРОВАНИЕ ПОЛЬЗОВАТЕЛЕЙ (АДМИН) =====================

@app.route('/admin/user/edit/<int:user_id>', methods=['GET', 'POST'])
@admin_required
def admin_user_edit(user_id):
    conn = get_db_connection()

    if request.method == 'POST':
        last_name = request.form['last_name']
        first_name = request.form['first_name']
        middle_name = request.form.get('middle_name', '')
        email = request.form['email']
        post = request.form['post']
        phone = request.form['phone']

        # Валидация телефона
        phone = re.sub(r'\D', '', phone)

        conn.execute('''
            UPDATE users 
            SET last_name = ?, first_name = ?, middle_name = ?, email = ?, post = ?, phone = ?
            WHERE id = ?
        ''', (last_name, first_name, middle_name, email, post, phone, user_id))
        conn.commit()
        flash('Пользователь успешно обновлен', 'success')
        conn.close()
        return redirect(url_for('admin_users'))

    user = conn.execute('SELECT * FROM users WHERE id = ?', (user_id,)).fetchone()
    conn.close()

    if not user:
        flash('Пользователь не найден', 'danger')
        return redirect(url_for('admin_users'))

    return render_template('admins/admin_user_edit.html', user=user)


@app.route('/admin/user/delete/<int:user_id>')
@admin_required
def admin_user_delete(user_id):
    conn = get_db_connection()
    conn.execute('DELETE FROM tickets WHERE user_id = ?', (user_id,))
    conn.execute('DELETE FROM users WHERE id = ?', (user_id,))
    conn.commit()
    conn.close()
    flash('Пользователь и все его заявки удалены', 'success')
    return redirect(url_for('admin_users'))


# ===================== РЕДАКТИРОВАНИЕ ОПЕРАТОРОВ (АДМИН) =====================

@app.route('/admin/operator/edit/<int:operator_id>', methods=['GET', 'POST'])
@admin_required
def admin_operator_edit(operator_id):
    conn = get_db_connection()

    if request.method == 'POST':
        last_name = request.form['last_name']
        first_name = request.form['first_name']
        middle_name = request.form.get('middle_name', '')
        post = request.form['post']
        phone = request.form['phone']

        # Валидация телефона
        phone = re.sub(r'\D', '', phone)

        conn.execute('''
            UPDATE operators 
            SET last_name = ?, first_name = ?, middle_name = ?, post = ?, phone = ?
            WHERE id = ?
        ''', (last_name, first_name, middle_name, post, phone, operator_id))
        conn.commit()
        flash('Оператор успешно обновлен', 'success')
        conn.close()
        return redirect(url_for('admin_operators'))

    operator = conn.execute('SELECT * FROM operators WHERE id = ?', (operator_id,)).fetchone()
    conn.close()

    if not operator:
        flash('Оператор не найден', 'danger')
        return redirect(url_for('admin_operators'))

    return render_template('admins/admin_operator_edit.html', operator=operator)


@app.route('/admin/operator/delete/<int:operator_id>')
@admin_required
def admin_operator_delete(operator_id):
    conn = get_db_connection()
    conn.execute('UPDATE tickets SET assigned_to = NULL WHERE assigned_to = ?', (operator_id,))
    conn.execute('DELETE FROM operators WHERE id = ?', (operator_id,))
    conn.commit()
    conn.close()
    flash('Оператор удален', 'success')
    return redirect(url_for('admin_operators'))


# ===================== РЕДАКТИРОВАНИЕ ЗАЯВОК (АДМИН) =====================

@app.route('/admin/ticket/edit/<int:ticket_id>', methods=['GET', 'POST'])
@admin_required
def admin_ticket_edit(ticket_id):
    conn = get_db_connection()

    if request.method == 'POST':
        status = request.form['status']
        priority = request.form['priority']
        operator_answer = request.form.get('operator_answer', '')
        assigned_to = request.form.get('assigned_to')

        if assigned_to and assigned_to != '':
            assigned_to = int(assigned_to)
        else:
            assigned_to = None

        updated_at = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

        conn.execute('''
            UPDATE tickets 
            SET status = ?, priority = ?, operator_answer = ?, assigned_to = ?, updated_at = ?
            WHERE id = ?
        ''', (status, priority, operator_answer, assigned_to, updated_at, ticket_id))
        conn.commit()
        flash('Заявка успешно обновлена', 'success')
        conn.close()
        return redirect(url_for('admin_tickets'))

    ticket = conn.execute('''
        SELECT t.*, u.last_name, u.first_name, u.middle_name, u.post, u.phone, u.username, u.email
        FROM tickets t 
        JOIN users u ON t.user_id = u.id 
        WHERE t.id = ?
    ''', (ticket_id,)).fetchone()

    operators = conn.execute('SELECT id, last_name, first_name FROM operators ORDER BY last_name').fetchall()
    conn.close()

    if not ticket:
        flash('Заявка не найдена', 'danger')
        return redirect(url_for('admin_tickets'))

    return render_template('admins/admin_ticket_edit.html', ticket=ticket, operators=operators)


@app.route('/admin/ticket/delete/<int:ticket_id>')
@admin_required
def admin_ticket_delete(ticket_id):
    conn = get_db_connection()
    conn.execute('DELETE FROM tickets WHERE id = ?', (ticket_id,))
    conn.commit()
    conn.close()
    flash('Заявка удалена', 'success')
    return redirect(url_for('admin_tickets'))

# ===================== СОЗДАНИЕ ЗАЯВКИ =====================
@app.route('/create_ticket', methods=['GET', 'POST'])
@login_required
def create_ticket():
    if request.method == 'POST':
        # Получаем описание
        description = request.form.get('description', '')
        description = description.strip()

        # Создаем тему из первых 50 символов описания
        subject = description[:50] + '...' if len(description) > 50 else description
        if not subject:
            subject = 'Заявка в техподдержку'

        priority = request.form.get('priority', 'medium')
        created_at = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

        # Получаем остальные поля
        category = request.form.get('category', 'IT')
        problem_type = request.form.get('problem_type', '')
        location = request.form.get('location', '')
        office = request.form.get('office', '')
        assistant_id = request.form.get('assistant_id', '')
        printer_manufacturer = request.form.get('printer_manufacturer', '')
        printer_model = request.form.get('printer_model', '')
        printer_problem = request.form.get('printer_problem', '')

        conn = get_db_connection()
        try:
            conn.execute('''INSERT INTO tickets 
                (user_id, subject, description, priority, created_at, status, 
                 category, problem_type, location, office, assistant_id,
                 printer_manufacturer, printer_model, printer_problem) 
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)''',
                         (session['user_id'], subject, description, priority, created_at, 'new',
                          category, problem_type, location, office, assistant_id,
                          printer_manufacturer, printer_model, printer_problem))
            conn.commit()
            ticket_id = conn.execute('SELECT last_insert_rowid()').fetchone()[0]
            flash(f'Заявка #{ticket_id} успешно создана!', 'success')
            return redirect(url_for('ticket_status', ticket_id=ticket_id))
        except Exception as e:
            flash(f'Ошибка при создании заявки: {str(e)}', 'danger')
            print(f"Ошибка: {e}")
        finally:
            conn.close()

    return render_template('create_ticket.html')

@app.template_filter('nl2br')
def nl2br_filter(s):
    """Преобразует переносы строк в <br> теги"""
    if not s:
        return ''
    return s.replace('\r\n', '<br>').replace('\n', '<br>').replace('\r', '<br>')


@app.template_filter('clean_text')
def clean_text_filter(s):
    """Агрессивная очистка текста от лишних пробелов и переносов"""
    if not s:
        return ''
    import re

    # Убираем все маркеры и разделители
    s = re.sub(r'^[-=*_]{3,}$', '', s, flags=re.MULTILINE)

    # Разбиваем на строки
    lines = s.split('\n')
    cleaned_lines = []

    for line in lines:
        # Убираем пробелы в начале и конце строки
        clean_line = line.strip()
        # Пропускаем пустые строки и строки-маркеры
        if clean_line and not re.match(r'^[-=*_]{3,}$', clean_line):
            cleaned_lines.append(clean_line)

    # Соединяем с одним переносом
    result = '\n'.join(cleaned_lines)

    # Убираем множественные пробелы внутри
    result = re.sub(r'[ \t]+', ' ', result)

    return result.strip()

@app.template_filter('trim_text')
def trim_text_filter(s):
    """Удаляет все виды пробелов в начале и конце текста"""
    if not s:
        return ''
    # Удаляем все пробельные символы в начале и конце
    return s.strip()

@app.route('/ticket/<int:ticket_id>')
@login_required
def ticket_status(ticket_id):
    conn = get_db_connection()
    ticket = conn.execute('''
        SELECT t.*, u.last_name, u.first_name, u.middle_name, u.post, u.phone, u.username
        FROM tickets t 
        JOIN users u ON t.user_id = u.id 
        WHERE t.id = ? AND t.user_id = ?
    ''', (ticket_id, session['user_id'])).fetchone()
    conn.close()

    if not ticket:
        flash('Заявка не найдена', 'danger')
        return redirect(url_for('dashboard'))

    return render_template('ticket_status.html', ticket=ticket)


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
            session['operator_id'] = operator['id']

            # Получаем данные оператора
            last_name = operator['last_name'] or ''
            first_name = operator['first_name'] or ''
            middle_name = operator['middle_name'] or ''
            post = operator['post'] or 'Оператор технической поддержки'

            # Полное ФИО
            full_name = f"{last_name} {first_name} {middle_name}".strip()

            session['operator_full_name'] = full_name if full_name else operator['username']
            session['operator_name'] = full_name if full_name else operator['username']
            session['operator_post'] = post  # Добавляем должность в сессию

            flash(f'Добро пожаловать, {full_name}!', 'success')
            return redirect(url_for('operator_dashboard'))
        else:
            flash('Неверный логин или пароль', 'danger')

    return render_template('operators/operator_login.html')


@app.route('/operator/dashboard')
@operator_required
def operator_dashboard():
    status_filter = request.args.get('status', 'all')
    conn = get_db_connection()

    try:
        if status_filter == 'all':
            # Активные заявки (ИСКЛЮЧАЕМ resolved и closed)
            tickets = conn.execute('''
                SELECT t.*, u.last_name, u.first_name, u.middle_name, u.post, u.phone, u.username,
                       o.last_name as op_last_name, o.first_name as op_first_name,
                       julianday('now') - julianday(t.created_at) as hours_since_created
                FROM tickets t 
                JOIN users u ON t.user_id = u.id 
                LEFT JOIN operators o ON t.assigned_to = o.id
                WHERE t.status NOT IN ('resolved', 'closed')
                ORDER BY 
                    CASE t.status 
                        WHEN 'new' THEN 1
                        WHEN 'in_progress' THEN 2
                        ELSE 3
                    END, t.id DESC
            ''').fetchall()
        elif status_filter == 'resolved':
            # Решенные и закрытые заявки
            tickets = conn.execute('''
                SELECT t.*, u.last_name, u.first_name, u.middle_name, u.post, u.phone, u.username,
                       o.last_name as op_last_name, o.first_name as op_first_name,
                       julianday('now') - julianday(t.created_at) as hours_since_created
                FROM tickets t 
                JOIN users u ON t.user_id = u.id 
                LEFT JOIN operators o ON t.assigned_to = o.id
                WHERE t.status IN ('resolved', 'closed')
                ORDER BY t.id DESC
            ''').fetchall()
        elif status_filter == 'new':
            tickets = conn.execute('''
                SELECT t.*, u.last_name, u.first_name, u.middle_name, u.post, u.phone, u.username,
                       o.last_name as op_last_name, o.first_name as op_first_name,
                       julianday('now') - julianday(t.created_at) as hours_since_created
                FROM tickets t 
                JOIN users u ON t.user_id = u.id 
                LEFT JOIN operators o ON t.assigned_to = o.id
                WHERE t.status = 'new'
                ORDER BY t.id DESC
            ''').fetchall()
        elif status_filter == 'in_progress':
            tickets = conn.execute('''
                SELECT t.*, u.last_name, u.first_name, u.middle_name, u.post, u.phone, u.username,
                       o.last_name as op_last_name, o.first_name as op_first_name,
                       julianday('now') - julianday(t.created_at) as hours_since_created
                FROM tickets t 
                JOIN users u ON t.user_id = u.id 
                LEFT JOIN operators o ON t.assigned_to = o.id
                WHERE t.status = 'in_progress'
                ORDER BY t.id DESC
            ''').fetchall()
        else:
            # По умолчанию - активные
            tickets = conn.execute('''
                SELECT t.*, u.last_name, u.first_name, u.middle_name, u.post, u.phone, u.username,
                       o.last_name as op_last_name, o.first_name as op_first_name,
                       julianday('now') - julianday(t.created_at) as hours_since_created
                FROM tickets t 
                JOIN users u ON t.user_id = u.id 
                LEFT JOIN operators o ON t.assigned_to = o.id
                WHERE t.status NOT IN ('resolved', 'closed')
                ORDER BY t.id DESC
            ''').fetchall()
    except sqlite3.OperationalError as e:
        print(f"Ошибка БД: {e}")
        tickets = []
    finally:
        conn.close()

    return render_template('operators/operator_dashboard.html', tickets=tickets, current_filter=status_filter)


@app.route('/operator/ticket/<int:ticket_id>', methods=['GET', 'POST'])
@operator_required
def operator_ticket(ticket_id):
    conn = get_db_connection()

    if request.method == 'POST':
        status = request.form['status']
        answer = request.form['answer']
        updated_at = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

        if status == 'in_progress' and not \
                conn.execute('SELECT assigned_to FROM tickets WHERE id = ?', (ticket_id,)).fetchone()['assigned_to']:
            conn.execute('UPDATE tickets SET assigned_to = ?, updated_at = ? WHERE id = ?',
                         (session['operator_id'], updated_at, ticket_id))

        if status == 'resolved':
            completed_at = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            conn.execute(
                'UPDATE tickets SET status = ?, operator_answer = ?, updated_at = ?, completed_at = ? WHERE id = ?',
                (status, answer, updated_at, completed_at, ticket_id))
        elif status == 'closed':
            # Закрытие заявки - она пропадет из основного списка
            closed_at = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            conn.execute(
                'UPDATE tickets SET status = ?, operator_answer = ?, updated_at = ?, completed_at = ? WHERE id = ?',
                (status, answer, updated_at, closed_at, ticket_id))
        else:
            conn.execute('UPDATE tickets SET status = ?, operator_answer = ?, updated_at = ? WHERE id = ?',
                         (status, answer, updated_at, ticket_id))

        conn.commit()
        flash('Заявка обновлена', 'success')
        conn.close()
        return redirect(url_for('operator_dashboard'))

    ticket = conn.execute('''
        SELECT t.*, u.last_name, u.first_name, u.middle_name, u.post, u.phone, u.username,
               o.last_name as op_last_name, o.first_name as op_first_name, o.middle_name as op_middle_name, o.post as op_post,
               julianday('now') - julianday(t.created_at) as hours_since_created
        FROM tickets t 
        JOIN users u ON t.user_id = u.id 
        LEFT JOIN operators o ON t.assigned_to = o.id
        WHERE t.id = ?
    ''', (ticket_id,)).fetchone()
    conn.close()

    if not ticket:
        flash('Заявка не найдена', 'danger')
        return redirect(url_for('operator_dashboard'))

    return render_template('operators/operator_ticket.html', ticket=ticket)


@app.route('/profile')
@login_required
def profile():
    """Страница профиля пользователя"""
    conn = get_db_connection()
    user = conn.execute('SELECT * FROM users WHERE id = ?', (session['user_id'],)).fetchone()
    conn.close()

    if not user:
        flash('Пользователь не найден', 'danger')
        return redirect(url_for('logout'))

    return render_template('user_profile.html', user=user)


@app.route('/operator/profile')
@operator_required
def operator_profile():
    """Страница профиля оператора"""
    conn = get_db_connection()
    operator = conn.execute('SELECT * FROM operators WHERE id = ?', (session['operator_id'],)).fetchone()
    conn.close()

    return render_template('operators/operator_profile.html', operator=operator)


@app.route('/profile/edit', methods=['GET', 'POST'])
@login_required
def edit_profile():
    """Редактирование профиля пользователя"""
    conn = get_db_connection()

    if request.method == 'POST':
        phone = request.form['phone']
        email = request.form['email']
        post = request.form['post']

        # Валидация телефона
        phone = re.sub(r'\D', '', phone)
        if not re.match(r'^[78]\d{10}$', phone):
            flash('Введите корректный номер телефона', 'danger')
            return redirect(url_for('edit_profile'))
            # Получаем текущего пользователя
        current_user = conn.execute('SELECT phone, email FROM users WHERE id = ?',
                                    (session['user_id'],)).fetchone()
        if phone != current_user['phone']:
            existing_phone = conn.execute('SELECT id FROM users WHERE phone = ? AND id != ?',
                                          (phone, session['user_id'])).fetchone()
            if existing_phone:
                flash('❌ Этот номер телефона уже используется другим пользователем', 'danger')
                return redirect(url_for('edit_profile'))

        # Валидация email
        if not re.match(r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$', email):
            flash('Введите корректный email', 'danger')
            return redirect(url_for('edit_profile'))

        # Проверка, что email не принадлежит другому пользователю
        existing_email = conn.execute('SELECT id FROM users WHERE email = ? AND id != ?',
                                      (email, session['user_id'])).fetchone()
        if existing_email:
            flash('❌ Этот email уже используется другим пользователем', 'danger')
            return redirect(url_for('edit_profile'))

        # Обновляем все поля
        conn.execute('UPDATE users SET phone = ?, email = ?, post = ? WHERE id = ?',
                     (phone, email, post, session['user_id']))
        conn.commit()

        # Обновляем имя в сессии
        user = conn.execute('SELECT last_name, first_name, middle_name FROM users WHERE id = ?',
                            (session['user_id'],)).fetchone()
        session['full_name'] = f"{user['last_name']} {user['first_name']} {user['middle_name'] or ''}"

        flash('✅ Профиль успешно обновлен!', 'success')
        conn.close()
        return redirect(url_for('profile'))

    user = conn.execute('SELECT * FROM users WHERE id = ?', (session['user_id'],)).fetchone()
    conn.close()

    return render_template('edit_profile.html', user=user)


# ===================== КОНТЕКСТНЫЙ ПРОЦЕССОР (ДЛЯ ВСЕХ ШАБЛОНОВ) =====================
@app.context_processor
def inject_user():
    """Добавляет информацию о пользователе во все шаблоны"""
    user_info = {}

    if session.get('user_id'):
        conn = get_db_connection()
        user = conn.execute('SELECT * FROM users WHERE id = ?', (session['user_id'],)).fetchone()
        conn.close()

        if user:
            user_info = {
                'id': user['id'],
                'username': user['username'],
                'email': user['email'],
                'full_name': f"{user['last_name']} {user['first_name']} {user['middle_name'] or ''}",
                'first_name': user['first_name'],
                'last_name': user['last_name'],
                'middle_name': user['middle_name'],
                'post': user['post'],
                'phone': user['phone'],
                'is_admin': user['is_admin']
            }

    return {'user': user_info}

@app.route('/operator/logout')
def operator_logout():
    session.pop('operator_logged_in', None)
    session.pop('operator_id', None)
    session.pop('operator_name', None)
    flash('Вы вышли из панели оператора', 'info')
    return redirect(url_for('operator_login'))


if __name__ == '__main__':
    init_db()
    app.run(debug=True)