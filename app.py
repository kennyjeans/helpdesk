from flask import Flask, render_template, request, redirect, url_for, session, flash
import sqlite3
from datetime import datetime
import hashlib
import os
from functools import wraps
import re
import pandas as pd
from flask import Flask, render_template, request, redirect, url_for, session, flash, jsonify, send_file

app = Flask(__name__)
app.secret_key = 'mysecretkey_vrkb_System210101'


# ===================== ИНИЦИАЛИЗАЦИЯ БАЗЫ ДАННЫХ =====================
def init_db():
    if not os.path.exists('databases'):
        os.makedirs('databases')

    db_path = 'databases/database_helpdesk.db'

    # Проверяем, существует ли база данных
    db_exists = os.path.exists(db_path)

    conn = sqlite3.connect(db_path)
    c = conn.cursor()
    # Таблица уведомлений
    c.execute('''CREATE TABLE IF NOT EXISTS notifications (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        user_id INTEGER,
                        operator_id INTEGER,
                        admin_id INTEGER,
                        title TEXT NOT NULL,
                        message TEXT NOT NULL,
                        type TEXT DEFAULT 'info',
                        is_read INTEGER DEFAULT 0,
                        link TEXT,
                        created_at TEXT NOT NULL,
                        FOREIGN KEY (user_id) REFERENCES users (id),
                        FOREIGN KEY (operator_id) REFERENCES operators (id),
                        FOREIGN KEY (admin_id) REFERENCES admins (id)
                    )''')
    # функции comments:
    c.execute('''CREATE TABLE IF NOT EXISTS comments (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        ticket_id INTEGER NOT NULL,
        user_id INTEGER,
        operator_id INTEGER,
        comment TEXT NOT NULL,
        created_at TEXT NOT NULL,
        is_read INTEGER DEFAULT 0,
        FOREIGN KEY (ticket_id) REFERENCES tickets (id),
        FOREIGN KEY (user_id) REFERENCES users (id),
        FOREIGN KEY (operator_id) REFERENCES operators (id)
    )''')

    # функция answer_templates:
    c.execute('''CREATE TABLE IF NOT EXISTS answer_templates (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        name TEXT NOT NULL,
        category TEXT,
        content TEXT NOT NULL,
        created_at TEXT NOT NULL
    )''')

    # Добавьте тестовые шаблоны
    c.execute("SELECT COUNT(*) FROM answer_templates")
    if c.fetchone()[0] == 0:
        templates = [
            ('Проблема с ЕМИАС', 'IT',
             'Здравствуйте! По проблеме с ЕМИАС рекомендуем:\n1. Очистить кэш браузера\n2. Проверить интернет-соединение\n3. Перезагрузить компьютер\nЕсли проблема не решилась, свяжитесь с нами повторно.'),
            ('Проблема с принтером', 'IT',
             'Здравствуйте! По проблеме с принтером:\n1. Проверьте подключение к сети\n2. Перезагрузите принтер\n3. Проверьте наличие бумаги и картриджа\nЕсли не помогло, вызовем мастера.'),
            ('Проблема с ЭЦП', 'IT',
             'Здравствуйте! По проблеме с ЭЦП:\n1. Проверьте срок действия сертификата\n2. Переустановите КриптоПро\n3. Обратитесь в IT-отдел для перенастройки'),
            ('Проблема с интернетом', 'IT',
             'Здравствуйте! Проверьте:\n1. Кабели подключения\n2. Перезагрузите роутер\n3. Проверьте настройки сети\nЕсли не работает - сообщите дополнительную информацию.'),
            ('Медицинское оборудование', 'MED',
             'Здравствуйте! Ваша заявка по медицинскому оборудованию принята. Специалист свяжется с вами в ближайшее время.'),
            ('Общий ответ', 'common',
             'Здравствуйте! Ваша заявка принята в работу. IT-отдел свяжется с вами в ближайшее время.'),
        ]
        for name, category, content in templates:
            c.execute("INSERT INTO answer_templates (name, category, content, created_at) VALUES (?, ?, ?, ?)",
                      (name, category, content, datetime.now().strftime("%Y-%m-%d %H:%M:%S")))
        print("✅ Добавлены шаблоны ответов")
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

    # Таблица пользователей (с добавленным department)
    c.execute('''CREATE TABLE IF NOT EXISTS users (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        username TEXT UNIQUE NOT NULL,
        email TEXT UNIQUE NOT NULL,
        password TEXT NOT NULL,
        last_name TEXT,
        first_name TEXT,
        middle_name TEXT,
        post TEXT,
        department TEXT,
        phone TEXT,
        created_at TEXT NOT NULL,
        is_admin INTEGER DEFAULT 0
    )''')
    # Добавляем колонку department для старых баз
    try:
        c.execute("ALTER TABLE users ADD COLUMN department TEXT")
        print("✅ Добавлена колонка department в таблицу users")
    except sqlite3.OperationalError:
        print("Колонка department уже существует")

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
        hashed_pwd_operator = hashlib.sha256('operator123'.encode()).hexdigest()
        c.execute(
            "INSERT INTO operators (username, password, last_name, first_name, middle_name, post) VALUES (?, ?, ?, ?, ?, ?)",
            ('operator', hashed_pwd_operator, 'Технический', 'Оператор', 'IT-отдела', 'Специалист IT отдела'))
        print("✅ Добавлен оператор: operator / operator123")

    # Добавляем тестового пользователя (только если таблица пустая)
    c.execute("SELECT COUNT(*) FROM users")
    if c.fetchone()[0] == 0:
        hashed_pwd_user = hashlib.sha256('user123'.encode()).hexdigest()
        c.execute(
            "INSERT INTO users (username, email, password, last_name, first_name, middle_name, post, phone, created_at) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
            ('user', 'user@example.com', hashed_pwd_user, 'Петров', 'Петр', 'Петрович',
             'Врач-терапевт', '79012345678', datetime.now().strftime("%Y-%m-%d %H:%M:%S")))
        print("✅ Добавлен пользователь: user / user123")

        # ============ ТАБЛИЦЫ ДЛЯ РОЛЕЙ И ПРАВ ============

        # Таблица ролей
        c.execute('''CREATE TABLE IF NOT EXISTS roles (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT UNIQUE NOT NULL,
            description TEXT,
            created_at TEXT NOT NULL
        )''')

        # Таблица разрешений
        c.execute('''CREATE TABLE IF NOT EXISTS permissions (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT UNIQUE NOT NULL,
            description TEXT
        )''')

        # Таблица связей ролей и разрешений
        c.execute('''CREATE TABLE IF NOT EXISTS role_permissions (
            role_id INTEGER,
            permission_id INTEGER,
            FOREIGN KEY (role_id) REFERENCES roles (id),
            FOREIGN KEY (permission_id) REFERENCES permissions (id),
            PRIMARY KEY (role_id, permission_id)
        )''')

        # Таблица назначения ролей пользователям
        c.execute('''CREATE TABLE IF NOT EXISTS user_roles (
            user_id INTEGER,
            role_id INTEGER,
            FOREIGN KEY (user_id) REFERENCES users (id),
            FOREIGN KEY (role_id) REFERENCES roles (id),
            PRIMARY KEY (user_id, role_id)
        )''')


        # Добавляем базовые роли
        c.execute("SELECT COUNT(*) FROM roles")
        if c.fetchone()[0] == 0:
            roles_data = [
                ('super_admin', 'Полный доступ ко всем функциям системы'),
                ('admin', 'Доступ к управлению пользователями, операторами, заявками'),
                ('operator', 'Доступ к обработке заявок'),
                ('user', 'Базовый доступ: создание и просмотр своих заявок')
            ]
            for name, desc in roles_data:
                c.execute("INSERT INTO roles (name, description, created_at) VALUES (?, ?, ?)",
                          (name, desc, datetime.now().strftime("%Y-%m-%d %H:%M:%S")))
            print("✅ Добавлены базовые роли")

        # Добавляем разрешения (используем другое имя переменной)
        c.execute("SELECT COUNT(*) FROM permissions")
        if c.fetchone()[0] == 0:
            permissions_data = [
                ('users_view', 'Просмотр списка пользователей'),
                ('users_edit', 'Редактирование пользователей'),
                ('users_delete', 'Удаление пользователей'),
                ('users_create', 'Создание пользователей'),
                ('operators_view', 'Просмотр списка операторов'),
                ('operators_edit', 'Редактирование операторов'),
                ('operators_delete', 'Удаление операторов'),
                ('operators_create', 'Создание операторов'),
                ('tickets_view_all', 'Просмотр всех заявок'),
                ('tickets_edit_all', 'Редактирование всех заявок'),
                ('tickets_delete_all', 'Удаление всех заявок'),
                ('settings_view', 'Просмотр настроек'),
                ('settings_edit', 'Редактирование настроек'),
                ('backup_manage', 'Управление резервными копиями'),
                ('export_data', 'Экспорт данных')
            ]
            for name, desc in permissions_data:
                c.execute("INSERT INTO permissions (name, description) VALUES (?, ?)", (name, desc))
            print("✅ Добавлены базовые разрешения")

        # Назначаем разрешения для ролей
        # super_admin - все права
        super_admin_id = c.execute("SELECT id FROM roles WHERE name = 'super_admin'").fetchone()
        if super_admin_id:
            super_admin_id = super_admin_id[0]
            for perm in permissions_data:
                perm_id = c.execute("SELECT id FROM permissions WHERE name = ?", (perm[0],)).fetchone()
                if perm_id:
                    c.execute("INSERT OR IGNORE INTO role_permissions (role_id, permission_id) VALUES (?, ?)",
                              (super_admin_id, perm_id[0]))

        # admin - основные права
        admin_id = c.execute("SELECT id FROM roles WHERE name = 'admin'").fetchone()
        if admin_id:
            admin_id = admin_id[0]
            admin_perms = ['users_view', 'users_edit', 'users_delete', 'users_create',
                           'operators_view', 'operators_edit', 'operators_delete', 'operators_create',
                           'tickets_view_all', 'tickets_edit_all', 'settings_view', 'settings_edit',
                           'backup_manage', 'export_data']
            for perm_name in admin_perms:
                perm_id = c.execute("SELECT id FROM permissions WHERE name = ?", (perm_name,)).fetchone()
                if perm_id:
                    c.execute("INSERT OR IGNORE INTO role_permissions (role_id, permission_id) VALUES (?, ?)",
                              (admin_id, perm_id[0]))

        # operator - права оператора
        operator_id = c.execute("SELECT id FROM roles WHERE name = 'operator'").fetchone()
        if operator_id:
            operator_id = operator_id[0]
            operator_perms = ['tickets_view_all', 'tickets_edit_all']
            for perm_name in operator_perms:
                perm_id = c.execute("SELECT id FROM permissions WHERE name = ?", (perm_name,)).fetchone()
                if perm_id:
                    c.execute("INSERT OR IGNORE INTO role_permissions (role_id, permission_id) VALUES (?, ?)",
                              (operator_id, perm_id[0]))


        conn.commit()
        conn.close()
        print("🎉 База данных готова!")


def get_db_connection():
    conn = sqlite3.connect('databases/database_helpdesk.db', timeout=20)
    conn.row_factory = sqlite3.Row
    # Включаем WAL режим (Write-Ahead Logging)
    conn.execute('PRAGMA journal_mode=WAL')
    conn.execute('PRAGMA synchronous=NORMAL')
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

def has_permission(user_id, permission_name):
    """Проверка наличия разрешения у пользователя"""
    conn = get_db_connection()
    result = conn.execute('''
        SELECT 1 FROM user_roles ur
        JOIN role_permissions rp ON ur.role_id = rp.role_id
        JOIN permissions p ON rp.permission_id = p.id
        WHERE ur.user_id = ? AND p.name = ?
    ''', (user_id, permission_name)).fetchone()
    conn.close()
    return result is not None

def permission_required(permission_name):
    """Декоратор для проверки разрешений"""
    def decorator(f):
        @wraps(f)
        def decorated_function(*args, **kwargs):
            if not session.get('user_id'):
                flash('Пожалуйста, войдите в систему', 'warning')
                return redirect(url_for('login'))
            if not has_permission(session['user_id'], permission_name):
                flash('У вас нет прав для выполнения этого действия', 'danger')
                return redirect(url_for('dashboard'))
            return f(*args, **kwargs)
        return decorated_function
    return decorator

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

        # Проверяем логин или email
        if '@' in username_or_email:
            user = conn.execute('SELECT * FROM users WHERE email = ? AND password = ?',
                                (username_or_email, hashed_pwd)).fetchone()
        else:
            user = conn.execute('SELECT * FROM users WHERE username = ? AND password = ?',
                                (username_or_email, hashed_pwd)).fetchone()

        conn.close()

        if user:
            session['user_id'] = user['id']
            session['username'] = user['username']
            # Полное ФИО (с отчеством)
            full_name_parts = []
            if user['last_name']:
                full_name_parts.append(user['last_name'])
            if user['first_name']:
                full_name_parts.append(user['first_name'])
            if user['middle_name']:
                full_name_parts.append(user['middle_name'])
            session['full_name'] = ' '.join(full_name_parts)
            session['user_email'] = user['email']
            session['user_post'] = user['post']
            session['user_department'] = user['department']

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


# ===================== УПРАВЛЕНИЕ АДМИНИСТРАТОРАМИ =====================

@app.route('/admin/admins/list')
@admin_required
def admin_admins_list():
    """Список всех администраторов"""
    conn = get_db_connection()
    admins = conn.execute('''
        SELECT id, username, last_name, first_name, email, created_at 
        FROM admins 
        ORDER BY id
    ''').fetchall()
    conn.close()

    return jsonify({'admins': [dict(a) for a in admins]})


@app.route('/admin/admins/add', methods=['POST'])
@admin_required
def admin_admins_add():
    """Добавление нового администратора"""
    data = request.json
    username = data.get('username', '').strip()
    password = data.get('password', '')
    email = data.get('email', '').strip()
    last_name = data.get('last_name', '').strip()
    first_name = data.get('first_name', '').strip()
    middle_name = data.get('middle_name', '').strip()

    # Валидация
    errors = []
    if not username:
        errors.append('Логин обязателен')
    if len(password) < 6:
        errors.append('Пароль должен быть не менее 6 символов')
    if not email:
        errors.append('Email обязателен')

    if errors:
        return jsonify({'success': False, 'errors': errors})

    conn = get_db_connection()

    # Проверка уникальности логина
    existing = conn.execute('SELECT id FROM admins WHERE username = ?', (username,)).fetchone()
    if existing:
        conn.close()
        return jsonify({'success': False, 'errors': ['Администратор с таким логином уже существует']})

    # Проверка уникальности email
    existing_email = conn.execute('SELECT id FROM admins WHERE email = ?', (email,)).fetchone()
    if existing_email:
        conn.close()
        return jsonify({'success': False, 'errors': ['Администратор с таким email уже существует']})

    hashed_pwd = hashlib.sha256(password.encode()).hexdigest()
    created_at = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    conn.execute('''
        INSERT INTO admins (username, password, last_name, first_name, middle_name, email, created_at)
        VALUES (?, ?, ?, ?, ?, ?, ?)
    ''', (username, hashed_pwd, last_name, first_name, middle_name, email, created_at))
    conn.commit()
    conn.close()

    return jsonify({'success': True})


@app.route('/admin/admins/delete/<int:admin_id>', methods=['DELETE'])
@admin_required
def admin_admins_delete(admin_id):
    """Удаление администратора"""
    # Нельзя удалить самого себя
    if admin_id == session.get('admin_id'):
        return jsonify({'success': False, 'error': 'Нельзя удалить самого себя'})

    conn = get_db_connection()
    conn.execute('DELETE FROM admins WHERE id = ?', (admin_id,))
    conn.commit()
    conn.close()

    return jsonify({'success': True})


@app.route('/admin/admins/reset_password/<int:admin_id>', methods=['POST'])
@admin_required
def admin_admins_reset_password(admin_id):
    """Сброс пароля администратора"""
    data = request.json
    new_password = data.get('password', '')

    if len(new_password) < 6:
        return jsonify({'success': False, 'error': 'Пароль должен быть не менее 6 символов'})

    hashed_pwd = hashlib.sha256(new_password.encode()).hexdigest()

    conn = get_db_connection()
    conn.execute('UPDATE admins SET password = ? WHERE id = ?', (hashed_pwd, admin_id))
    conn.commit()
    conn.close()

    return jsonify({'success': True})

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
    status_filter = request.args.get('status', 'all')
    conn = get_db_connection()

    if status_filter == 'all':
        tickets = conn.execute('''
            SELECT t.*, u.last_name, u.first_name, u.username, u.email, u.post, u.phone,
                   o.last_name as op_last_name, o.first_name as op_first_name
            FROM tickets t 
            JOIN users u ON t.user_id = u.id 
            LEFT JOIN operators o ON t.assigned_to = o.id
            ORDER BY t.id DESC
        ''').fetchall()
    else:
        tickets = conn.execute('''
            SELECT t.*, u.last_name, u.first_name, u.username, u.email, u.post, u.phone,
                   o.last_name as op_last_name, o.first_name as op_first_name
            FROM tickets t 
            JOIN users u ON t.user_id = u.id 
            LEFT JOIN operators o ON t.assigned_to = o.id
            WHERE t.status = ?
            ORDER BY t.id DESC
        ''', (status_filter,)).fetchall()

    conn.close()
    return render_template('admins/admin_tickets.html', tickets=tickets)



@app.route('/admin/settings')
@admin_required
def admin_settings():
    return render_template('admins/admin_settings.html')


# ===================== УПРАВЛЕНИЕ РОЛЯМИ И ПРАВАМИ =====================

@app.route('/admin/roles')
@admin_required
def admin_roles():
    """Страница управления ролями"""
    conn = get_db_connection()
    roles = conn.execute('SELECT * FROM roles ORDER BY id').fetchall()
    permissions = conn.execute('SELECT * FROM permissions ORDER BY id').fetchall()

    # Получаем разрешения для каждой роли
    role_perms = {}
    for role in roles:
        perms = conn.execute('''
            SELECT p.id, p.name FROM permissions p
            JOIN role_permissions rp ON p.id = rp.permission_id
            WHERE rp.role_id = ?
        ''', (role['id'],)).fetchall()
        role_perms[role['id']] = [p['id'] for p in perms]

    conn.close()
    return render_template('admins/admin_roles.html',
                           roles=roles,
                           permissions=permissions,
                           role_perms=role_perms)


@app.route('/admin/roles/update', methods=['POST'])
@admin_required
def admin_roles_update():
    """Обновление прав роли"""
    data = request.json
    role_id = data.get('role_id')
    permission_ids = data.get('permissions', [])

    conn = get_db_connection()

    # Удаляем старые права
    conn.execute('DELETE FROM role_permissions WHERE role_id = ?', (role_id,))

    # Добавляем новые
    for perm_id in permission_ids:
        conn.execute('INSERT INTO role_permissions (role_id, permission_id) VALUES (?, ?)',
                     (role_id, perm_id))

    conn.commit()
    conn.close()

    return jsonify({'success': True})


@app.route('/admin/users/roles/<int:user_id>')
@admin_required
def admin_user_roles(user_id):
    """Получение ролей пользователя"""
    conn = get_db_connection()
    user_roles = conn.execute('''
        SELECT r.id, r.name FROM roles r
        JOIN user_roles ur ON r.id = ur.role_id
        WHERE ur.user_id = ?
    ''', (user_id,)).fetchall()
    all_roles = conn.execute('SELECT * FROM roles ORDER BY id').fetchall()
    conn.close()

    return jsonify({
        'user_roles': [dict(r) for r in user_roles],
        'all_roles': [dict(r) for r in all_roles]
    })


@app.route('/admin/users/roles/update', methods=['POST'])
@admin_required
def admin_user_roles_update():
    """Обновление ролей пользователя"""
    data = request.json
    user_id = data.get('user_id')
    role_ids = data.get('roles', [])

    conn = get_db_connection()

    # Удаляем старые роли
    conn.execute('DELETE FROM user_roles WHERE user_id = ?', (user_id,))

    # Добавляем новые
    for role_id in role_ids:
        conn.execute('INSERT INTO user_roles (user_id, role_id) VALUES (?, ?)',
                     (user_id, role_id))

    conn.commit()
    conn.close()

    return jsonify({'success': True})

# ===================== НАСТРОЙКИ СИСТЕМЫ =====================

@app.route('/admin/settings/organization', methods=['POST'])
@admin_required
def save_org_settings():
    """Сохранение настроек организации"""
    data = request.json
    # Сохраняем в файл или БД
    import json
    settings = {
        'org_name': data.get('org_name', ''),
        'org_phone': data.get('org_phone', ''),
        'org_email': data.get('org_email', ''),
        'org_address': data.get('org_address', '')
    }
    with open('databases/settings.json', 'w', encoding='utf-8') as f:
        json.dump(settings, f, ensure_ascii=False, indent=2)
    return jsonify({'success': True})


@app.route('/admin/settings/organization', methods=['GET'])
@admin_required
def get_org_settings():
    """Получение настроек организации"""
    import json
    import os
    default = {
        'org_name': 'ВРКБ - Видновская районная клиническая больница',
        'org_phone': '+7 (901) 796-16-64',
        'org_email': 'ITGBUZ@mosreg.ru',
        'org_address': 'г. Видное, Московская область'
    }
    if os.path.exists('databases/settings.json'):
        with open('databases/settings.json', 'r', encoding='utf-8') as f:
            settings = json.load(f)
            default.update(settings)
    return jsonify(default)


@app.route('/admin/settings/notifications', methods=['POST'])
@admin_required
def save_notification_settings():
    """Сохранение настроек уведомлений"""
    data = request.json
    import json
    with open('databases/notifications.json', 'w', encoding='utf-8') as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
    return jsonify({'success': True})


@app.route('/admin/settings/notifications', methods=['GET'])
@admin_required
def get_notification_settings():
    """Получение настроек уведомлений"""
    import json
    import os
    default = {
        'email_enabled': True,
        'email_host': 'smtp.gmail.com',
        'email_port': 587,
        'email_user': '',
        'email_password': '',
        'notify_new_ticket': True,
        'notify_status_change': True,
        'notify_comment': True
    }
    if os.path.exists('databases/notifications.json'):
        with open('databases/notifications.json', 'r', encoding='utf-8') as f:
            settings = json.load(f)
            default.update(settings)
    return jsonify(default)


@app.route('/admin/settings/export_tickets', methods=['GET'])
@admin_required
def export_tickets():
    """Экспорт заявок в Excel"""
    import pandas as pd
    from io import BytesIO

    conn = get_db_connection()
    tickets = conn.execute('''
        SELECT t.id, t.subject, t.description, t.status, t.priority, t.created_at, t.category,
               u.last_name, u.first_name, u.middle_name, u.post, u.department, u.phone,
               o.last_name as op_last_name, o.first_name as op_first_name
        FROM tickets t 
        JOIN users u ON t.user_id = u.id 
        LEFT JOIN operators o ON t.assigned_to = o.id
        ORDER BY t.id DESC
    ''').fetchall()
    conn.close()

    data = []
    for t in tickets:
        data.append({
            'ID': t['id'],
            'Статус': t['status'],
            'Приоритет': t['priority'],
            'Категория': t['category'] if t['category'] else '',
            'Описание': t['description'],
            'Создана': t['created_at'],
            'ФИО пользователя': f"{t['last_name']} {t['first_name']} {t['middle_name'] or ''}",
            'Должность': t['post'],
            'Подразделение': t['department'] or '',
            'Телефон': t['phone'],
            'Оператор': f"{t['op_last_name'] or ''} {t['op_first_name'] or ''}".strip() or 'Не назначен'
        })

    df = pd.DataFrame(data)
    output = BytesIO()
    with pd.ExcelWriter(output, engine='openpyxl') as writer:
        df.to_excel(writer, sheet_name='Заявки', index=False)

    output.seek(0)
    return send_file(output, as_attachment=True,
                     download_name=f'tickets_export_{datetime.now().strftime("%Y%m%d_%H%M%S")}.xlsx',
                     mimetype='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet')


@app.route('/admin/backup')
@admin_required
def admin_backup():
    """Резервное копирование базы данных в папку databases"""
    import shutil
    import os
    from datetime import datetime

    db_path = 'databases/database_helpdesk.db'
    backup_folder = 'databases/backups/'

    # Создаем папку для бэкапов если её нет
    if not os.path.exists(backup_folder):
        os.makedirs(backup_folder)

    backup_name = f"backup_{datetime.now().strftime('%Y%m%d_%H%M%S')}.db"
    backup_path = os.path.join(backup_folder, backup_name)

    if os.path.exists(db_path):
        shutil.copy(db_path, backup_path)
        flash(f'✅ Резервная копия создана: {backup_name}', 'success')
    else:
        flash('❌ Файл базы данных не найден', 'danger')

    return redirect(url_for('admin_settings'))


@app.route('/admin/backup/list')
@admin_required
def admin_backup_list():
    """Список резервных копий"""
    import os
    import glob
    from datetime import datetime

    backup_folder = 'databases/backups/'
    backups = []

    if os.path.exists(backup_folder):
        for file in glob.glob(os.path.join(backup_folder, 'backup_*.db')):
            stat = os.stat(file)
            backups.append({
                'name': os.path.basename(file),
                'size': f"{stat.st_size / 1024:.1f} KB",
                'date': datetime.fromtimestamp(stat.st_mtime).strftime('%Y-%m-%d %H:%M:%S'),
                'path': file
            })

    backups.sort(key=lambda x: x['date'], reverse=True)
    return jsonify({'backups': backups})


@app.route('/admin/backup/restore/<filename>')
@admin_required
def admin_backup_restore(filename):
    """Восстановление из резервной копии"""
    import shutil
    import os

    backup_path = f'databases/backups/{filename}'
    db_path = 'databases/database_helpdesk.db'

    if os.path.exists(backup_path):
        # Создаем копию текущей БД перед восстановлением
        shutil.copy(db_path, f'databases/database_helpdesk_backup_before_restore.db')
        # Восстанавливаем
        shutil.copy(backup_path, db_path)
        flash(f'✅ База данных восстановлена из {filename}', 'success')
    else:
        flash('❌ Файл резервной копии не найден', 'danger')

    return redirect(url_for('admin_settings'))


@app.route('/admin/backup/delete/<filename>')
@admin_required
def admin_backup_delete(filename):
    """Удаление резервной копии"""
    import os

    backup_path = f'databases/backups/{filename}'
    if os.path.exists(backup_path):
        os.remove(backup_path)
        flash(f'✅ Резервная копия {filename} удалена', 'success')
    else:
        flash('❌ Файл не найден', 'danger')

    return redirect(url_for('admin_settings'))


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



import io
from werkzeug.utils import secure_filename

# Разрешенные расширения файлов
ALLOWED_EXTENSIONS = {'xlsx', 'xls', 'csv'}


def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS


def normalize_phone(phone):
    """Нормализация номера телефона"""
    if not phone or phone == 'None':
        return ''
    # Удаляем все нецифровые символы
    phone = re.sub(r'\D', '', str(phone))
    # Приводим к формату 79xxxxxxxxx
    if phone.startswith('8'):
        phone = '7' + phone[1:]
    if phone.startswith('7') and len(phone) == 11:
        return phone
    if len(phone) == 10:
        return '7' + phone
    return ''


def generate_username(last_name, first_name, middle_name=''):
    """Генерация логина: Фамилия + Инициалы (Имя + Отчество)"""
    if not last_name or not first_name:
        return None

    # Транслитерация
    translit = {
        'а': 'a', 'б': 'b', 'в': 'v', 'г': 'g', 'д': 'd', 'е': 'e', 'ё': 'e',
        'ж': 'zh', 'з': 'z', 'и': 'i', 'й': 'y', 'к': 'k', 'л': 'l', 'м': 'm',
        'н': 'n', 'о': 'o', 'п': 'p', 'р': 'r', 'с': 's', 'т': 't', 'у': 'u',
        'ф': 'f', 'х': 'h', 'ц': 'ts', 'ч': 'ch', 'ш': 'sh', 'щ': 'sch', 'ъ': '',
        'ы': 'y', 'ь': '', 'э': 'e', 'ю': 'yu', 'я': 'ya'
    }

    # Транслитерируем фамилию (с заглавной буквы)
    last_name_translit = ''
    for i, char in enumerate(last_name.lower()):
        trans = translit.get(char, char)
        if i == 0:
            trans = trans.upper() if trans else trans
        last_name_translit += trans

    # Инициал имени (первая буква, заглавная)
    first_initial = ''
    if first_name:
        first_char = first_name[0].lower()
        first_initial = translit.get(first_char, first_char).upper()

    # Инициал отчества (первая буква, заглавная)
    middle_initial = ''
    if middle_name:
        middle_char = middle_name[0].lower()
        middle_initial = translit.get(middle_char, middle_char).upper()

    # Формируем логин: Фамилия + ИнициалИмени + ИнициалОтчества
    username = f"{last_name_translit}{first_initial}{middle_initial}"

    # Убираем недопустимые символы
    username = re.sub(r'[^a-zA-Z0-9]', '', username)

    return username


@app.route('/admin/users/import', methods=['POST'])
@admin_required
def import_users():
    """Импорт пользователей из Excel/CSV"""
    if 'file' not in request.files:
        flash('Файл не выбран', 'danger')
        return redirect(url_for('admin_users'))

    file = request.files['file']
    if file.filename == '':
        flash('Файл не выбран', 'danger')
        return redirect(url_for('admin_users'))

    if not allowed_file(file.filename):
        flash('Неподдерживаемый формат файла. Используйте .xlsx, .xls или .csv', 'danger')
        return redirect(url_for('admin_users'))

    try:
        # Читаем файл
        if file.filename.endswith('.csv'):
            df = pd.read_csv(file, encoding='utf-8')
        else:
            df = pd.read_excel(file)

        conn = get_db_connection()
        success_count = 0
        error_count = 0
        errors = []

        # Нормализуем названия колонок
        df.columns = [str(col).strip() for col in df.columns]

        # Создаем словарь соответствия колонок
        column_mapping = {}
        for col in df.columns:
            col_lower = col.lower()
            if '№' in col or 'номер' in col_lower or 'id' == col_lower:
                column_mapping['number'] = col
            elif 'подраздел' in col_lower or 'отдел' in col_lower or 'department' in col_lower:
                column_mapping['department'] = col
            elif 'сотрудник' in col_lower or 'фио' in col_lower or 'fio' in col_lower or 'full_name' in col_lower:
                column_mapping['fio'] = col
            elif 'должн' in col_lower or 'post' in col_lower or 'position' in col_lower:
                column_mapping['post'] = col
            elif 'телефон' in col_lower or 'phone' in col_lower or 'tel' in col_lower:
                column_mapping['phone'] = col

        # Проверяем обязательные колонки
        if 'fio' not in column_mapping:
            flash('Не найдена колонка с ФИО. Ожидаются: "Сотрудник", "ФИО" или "full_name"', 'danger')
            return redirect(url_for('admin_users'))

        if 'post' not in column_mapping:
            flash('Не найдена колонка с должностью. Ожидаются: "Должность" или "post"', 'danger')
            return redirect(url_for('admin_users'))

        if 'phone' not in column_mapping:
            flash('Не найдена колонка с телефоном. Ожидаются: "Телефон" или "phone"', 'danger')
            return redirect(url_for('admin_users'))

        for index, row in df.iterrows():
            try:
                # Извлекаем данные
                fio = str(row[column_mapping['fio']]).strip()
                post = str(row[column_mapping['post']]).strip()
                phone_raw = str(row[column_mapping['phone']]).strip()
                department = str(row[column_mapping['department']]) if 'department' in column_mapping else ''

                # Очистка
                if department == 'nan':
                    department = ''
                if post == 'nan':
                    post = ''

                # Пропускаем пустые строки
                if not fio or fio == 'nan' or fio == '':
                    continue

                # Пропускаем заголовки
                if fio.startswith('№') or fio == 'Сотрудник':
                    continue

                # Разбираем ФИО
                fio_parts = fio.split()
                if len(fio_parts) >= 2:
                    last_name = fio_parts[0]
                    first_name = fio_parts[1]
                    middle_name = fio_parts[2] if len(fio_parts) >= 3 else ''
                else:
                    last_name = fio
                    first_name = ''
                    middle_name = ''

                # Нормализуем телефон
                phone = normalize_phone(phone_raw)
                if not phone:
                    errors.append(f"Строка {index + 2}: Неверный формат телефона: {phone_raw}")
                    error_count += 1
                    continue

                # ПРОВЕРКА: существует ли пользователь с таким ФИО
                existing_user = conn.execute('''
                    SELECT id FROM users 
                    WHERE last_name = ? AND first_name = ? AND middle_name = ?
                ''', (last_name, first_name, middle_name)).fetchone()

                if existing_user:
                    errors.append(
                        f"Строка {index + 2}: Пользователь {fio} уже существует в системе (ID: {existing_user['id']})")
                    error_count += 1
                    continue

                # Генерируем логин
                username = generate_username(last_name, first_name, middle_name)
                if not username:
                    errors.append(f"Строка {index + 2}: Не удалось сгенерировать логин для {fio}")
                    error_count += 1
                    continue

                # Уникальность логина
                base_username = username
                counter = 1
                while conn.execute('SELECT id FROM users WHERE username = ?', (username,)).fetchone():
                    username = f"{base_username}{counter}"
                    counter += 1

                # Генерируем email
                email = f"{username}@mosreg.ru"

                # Временный пароль
                temp_password = hashlib.sha256('Qwerty123'.encode()).hexdigest()
                created_at = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

                # ПРОВЕРКА: существует ли телефон
                existing_phone = conn.execute('SELECT id FROM users WHERE phone = ?', (phone,)).fetchone()
                if existing_phone:
                    errors.append(f"Строка {index + 2}: Телефон {phone} уже зарегистрирован другим пользователем")
                    error_count += 1
                    continue

                # Создаем пользователя
                conn.execute('''
                    INSERT INTO users (username, email, password, last_name, first_name, middle_name, post, department, phone, created_at)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                ''', (username, email, temp_password, last_name, first_name, middle_name, post, department, phone,
                      created_at))

                success_count += 1

            except Exception as e:
                error_count += 1
                errors.append(f"Строка {index + 2}: {str(e)}")

        conn.commit()
        conn.close()

        flash(f'✅ Импорт завершен. Добавлено: {success_count}, Ошибок: {error_count}', 'success')
        if errors:
            for error in errors[:10]:
                flash(error, 'warning')

    except Exception as e:
        flash(f'Ошибка при чтении файла: {str(e)}', 'danger')

    return redirect(url_for('admin_users'))


@app.route('/admin/user/add', methods=['GET', 'POST'])
@admin_required
def admin_user_add():
    """Ручное добавление пользователя"""
    if request.method == 'POST':
        username = request.form['username'].strip()
        email = request.form['email'].strip()
        password = request.form['password']
        last_name = request.form['last_name'].strip()
        first_name = request.form['first_name'].strip()
        middle_name = request.form.get('middle_name', '').strip()
        post = request.form['post'].strip()
        department = request.form.get('department', '').strip()
        phone = request.form['phone'].strip()

        # Валидация
        errors = []

        if not username:
            errors.append('Логин обязателен')
        if not email:
            errors.append('Email обязателен')
        if len(password) < 6:
            errors.append('Пароль должен быть не менее 6 символов')
        if not last_name:
            errors.append('Фамилия обязательна')
        if not first_name:
            errors.append('Имя обязательно')
        if not phone:
            errors.append('Телефон обязателен')

        # Нормализация телефона
        phone = re.sub(r'\D', '', phone)
        if not re.match(r'^[78]\d{10}$', phone):
            errors.append('Введите корректный номер телефона (10 цифр после 7 или 8)')

        if errors:
            for error in errors:
                flash(error, 'danger')
            return render_template('admins/admin_user_add.html')

        hashed_pwd = hashlib.sha256(password.encode()).hexdigest()
        created_at = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

        conn = get_db_connection()

        # Проверка уникальности логина
        existing_username = conn.execute('SELECT id FROM users WHERE username = ?', (username,)).fetchone()
        if existing_username:
            flash('Пользователь с таким логином уже существует', 'danger')
            conn.close()
            return render_template('admins/admin_user_add.html')

        # Проверка уникальности email
        existing_email = conn.execute('SELECT id FROM users WHERE email = ?', (email,)).fetchone()
        if existing_email:
            flash('Пользователь с таким email уже существует', 'danger')
            conn.close()
            return render_template('admins/admin_user_add.html')

        # Проверка уникальности телефона
        existing_phone = conn.execute('SELECT id FROM users WHERE phone = ?', (phone,)).fetchone()
        if existing_phone:
            flash('Пользователь с таким телефоном уже существует', 'danger')
            conn.close()
            return render_template('admins/admin_user_add.html')

        try:
            conn.execute('''
                INSERT INTO users (username, email, password, last_name, first_name, middle_name, post, department, phone, created_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ''', (username, email, hashed_pwd, last_name, first_name, middle_name, post, department, phone, created_at))
            conn.commit()
            flash(f'✅ Пользователь {username} успешно добавлен!', 'success')
            return redirect(url_for('admin_users'))
        except Exception as e:
            flash(f'Ошибка при добавлении: {str(e)}', 'danger')
        finally:
            conn.close()

    return render_template('admins/admin_user_add.html')

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

# ===================== Добавление ОПЕРАТОРОВ (АДМИН) =====================
@app.route('/admin/operator/add', methods=['GET', 'POST'])
@admin_required
def admin_operator_add():
    """Ручное добавление оператора"""
    if request.method == 'POST':
        username = request.form['username'].strip()
        password = request.form['password']
        last_name = request.form['last_name'].strip()
        first_name = request.form['first_name'].strip()
        middle_name = request.form.get('middle_name', '').strip()
        post = request.form.get('post', '').strip()
        phone = request.form.get('phone', '').strip()

        # Валидация
        errors = []

        if not username:
            errors.append('Логин обязателен')
        if len(password) < 6:
            errors.append('Пароль должен быть не менее 6 символов')
        if not last_name:
            errors.append('Фамилия обязательна')
        if not first_name:
            errors.append('Имя обязательно')

        # Нормализация телефона (если указан)
        if phone:
            phone = re.sub(r'\D', '', phone)
            if not re.match(r'^[78]\d{10}$', phone):
                errors.append('Введите корректный номер телефона (10 цифр после 7 или 8)')
        else:
            phone = ''

        if errors:
            for error in errors:
                flash(error, 'danger')
            return render_template('admins/admin_operator_add.html')

        hashed_pwd = hashlib.sha256(password.encode()).hexdigest()

        conn = get_db_connection()

        # Проверка уникальности логина
        existing_username = conn.execute('SELECT id FROM operators WHERE username = ?', (username,)).fetchone()
        if existing_username:
            flash('Оператор с таким логином уже существует', 'danger')
            conn.close()
            return render_template('admins/admin_operator_add.html')

        # Проверка уникальности телефона (если указан)
        if phone:
            existing_phone = conn.execute('SELECT id FROM operators WHERE phone = ?', (phone,)).fetchone()
            if existing_phone:
                flash('Оператор с таким телефоном уже существует', 'danger')
                conn.close()
                return render_template('admins/admin_operator_add.html')

        try:
            conn.execute('''
                INSERT INTO operators (username, password, last_name, first_name, middle_name, post, phone)
                VALUES (?, ?, ?, ?, ?, ?, ?)
            ''', (username, hashed_pwd, last_name, first_name, middle_name, post, phone))
            conn.commit()
            flash(f'✅ Оператор {username} успешно добавлен!', 'success')
            return redirect(url_for('admin_operators'))
        except Exception as e:
            flash(f'Ошибка при добавлении: {str(e)}', 'danger')
        finally:
            conn.close()

    return render_template('admins/admin_operator_add.html')

# ===================== РЕДАКТИРОВАНИЕ ОПЕРАТОРОВ (АДМИН) =====================

@app.route('/admin/operator/edit/<int:operator_id>', methods=['GET', 'POST'])
@admin_required
def admin_operator_edit(operator_id):
    """Редактирование оператора"""
    conn = get_db_connection()

    if request.method == 'POST':
        last_name = request.form['last_name']
        first_name = request.form['first_name']
        middle_name = request.form.get('middle_name', '')
        post = request.form.get('post', '')
        phone = request.form.get('phone', '')

        # Валидация телефона
        if phone:
            phone = re.sub(r'\D', '', phone)
            if not re.match(r'^[78]\d{10}$', phone):
                flash('Введите корректный номер телефона', 'danger')
                return redirect(url_for('admin_operator_edit', operator_id=operator_id))
        else:
            phone = ''

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


@app.route('/operator/assign/<int:ticket_id>', methods=['POST'])
@operator_required
def assign_operator(ticket_id):
    """Назначение оператора на заявку"""
    assigned_to = request.form.get('assigned_to')
    current_time = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    conn = get_db_connection()

    try:
        # Получаем информацию о заявке
        ticket = conn.execute('SELECT user_id FROM tickets WHERE id = ?', (ticket_id,)).fetchone()

        if assigned_to and assigned_to != '':
            conn.execute('''
                UPDATE tickets 
                SET assigned_to = ?, status = 'in_progress', updated_at = ?
                WHERE id = ?
            ''', (int(assigned_to), current_time, ticket_id))

            # Отправляем уведомления ПОСЛЕ закрытия соединения
            conn.commit()
            conn.close()

            # Уведомление оператору
            send_notification(
                'operator',
                int(assigned_to),
                f'📋 Заявка #{ticket_id} назначена вам',
                f'Вам назначена заявка #{ticket_id}',
                'assignment',
                f'/operator/ticket/{ticket_id}'
            )

            # Уведомление пользователю
            if ticket:
                send_notification(
                    'user',
                    ticket['user_id'],
                    f'👨‍💼 Заявка #{ticket_id} взята в работу',
                    f'IT-специалист назначен на вашу заявку',
                    'status_change',
                    f'/ticket/{ticket_id}'
                )

            flash('IT-специалист назначен на заявку', 'success')
        else:
            conn.execute('UPDATE tickets SET assigned_to = NULL, status = "new", updated_at = NULL WHERE id = ?',
                         (ticket_id,))
            conn.commit()
            conn.close()
            flash('Назначение отменено', 'info')

    except Exception as e:
        conn.close()
        flash(f'Ошибка: {e}', 'danger')

    return redirect(url_for('operator_dashboard'))


# ===================== СБРОС ПАРОЛЯ =====================

@app.route('/admin/user/reset_password/<int:user_id>', methods=['GET', 'POST'])
@admin_required
def admin_user_reset_password(user_id):
    """Сброс пароля пользователя администратором"""
    conn = get_db_connection()
    user = conn.execute('SELECT * FROM users WHERE id = ?', (user_id,)).fetchone()

    if not user:
        flash('Пользователь не найден', 'danger')
        conn.close()
        return redirect(url_for('admin_users'))

    if request.method == 'POST':
        new_password = request.form.get('new_password', '')

        if len(new_password) < 6:
            flash('Пароль должен быть не менее 6 символов', 'danger')
            conn.close()
            return render_template('admins/admin_user_reset_password.html', user=user)

        hashed_pwd = hashlib.sha256(new_password.encode()).hexdigest()
        conn.execute('UPDATE users SET password = ? WHERE id = ?', (hashed_pwd, user_id))
        conn.commit()

        flash(f'✅ Пароль для пользователя {user["username"]} успешно изменен!', 'success')
        conn.close()
        return redirect(url_for('admin_users'))

    conn.close()
    return render_template('admins/admin_user_reset_password.html', user=user)


@app.route('/admin/operator/reset_password/<int:operator_id>', methods=['GET', 'POST'])
@admin_required
def admin_operator_reset_password(operator_id):
    """Сброс пароля оператора администратором"""
    conn = get_db_connection()
    operator = conn.execute('SELECT * FROM operators WHERE id = ?', (operator_id,)).fetchone()

    if not operator:
        flash('Оператор не найден', 'danger')
        conn.close()
        return redirect(url_for('admin_operators'))

    if request.method == 'POST':
        new_password = request.form.get('new_password', '')

        if len(new_password) < 6:
            flash('Пароль должен быть не менее 6 символов', 'danger')
            conn.close()
            return render_template('admins/admin_operator_reset_password.html', operator=operator)

        hashed_pwd = hashlib.sha256(new_password.encode()).hexdigest()
        conn.execute('UPDATE operators SET password = ? WHERE id = ?', (hashed_pwd, operator_id))
        conn.commit()

        flash(f'✅ Пароль для оператора {operator["username"]} успешно изменен!', 'success')
        conn.close()
        return redirect(url_for('admin_operators'))

    conn.close()
    return render_template('admins/admin_operator_reset_password.html', operator=operator)


# ===================== КОММЕНТАРИИ =====================

@app.route('/ticket/<int:ticket_id>/add_comment', methods=['POST'])
@login_required
def add_comment(ticket_id):
    """Добавление комментария пользователем"""
    comment = request.form.get('comment', '').strip()

    if not comment:
        flash('Комментарий не может быть пустым', 'warning')
        return redirect(url_for('ticket_status', ticket_id=ticket_id))

    conn = get_db_connection()

    # Проверяем, что заявка принадлежит пользователю и получаем назначенного оператора
    ticket = conn.execute('SELECT user_id, assigned_to FROM tickets WHERE id = ?', (ticket_id,)).fetchone()
    if not ticket or ticket['user_id'] != session['user_id']:
        flash('Доступ запрещен', 'danger')
        conn.close()
        return redirect(url_for('dashboard'))

    conn.execute('''
        INSERT INTO comments (ticket_id, user_id, comment, created_at)
        VALUES (?, ?, ?, ?)
    ''', (ticket_id, session['user_id'], comment, datetime.now().strftime("%Y-%m-%d %H:%M:%S")))
    conn.commit()

    # ===== УВЕДОМЛЕНИЕ ОПЕРАТОРУ =====
    if ticket['assigned_to']:
        send_notification(
            'operator',
            ticket['assigned_to'],
            f'💬 Новый комментарий в заявке #{ticket_id}',
            f'Пользователь оставил комментарий: {comment[:50]}...',
            'comment',
            f'/operator/ticket/{ticket_id}'
        )
    # ================================

    conn.close()

    flash('Комментарий добавлен', 'success')
    return redirect(url_for('ticket_status', ticket_id=ticket_id))


@app.route('/operator/ticket/<int:ticket_id>/add_comment', methods=['POST'])
@operator_required
def operator_add_comment(ticket_id):
    """Добавление комментария оператором"""
    comment = request.form.get('comment', '').strip()

    if not comment:
        flash('Комментарий не может быть пустым', 'warning')
        return redirect(url_for('operator_ticket', ticket_id=ticket_id))

    conn = get_db_connection()

    # Получаем ID пользователя, которому принадлежит заявка
    ticket = conn.execute('SELECT user_id FROM tickets WHERE id = ?', (ticket_id,)).fetchone()

    conn.execute('''
        INSERT INTO comments (ticket_id, operator_id, comment, created_at)
        VALUES (?, ?, ?, ?)
    ''', (ticket_id, session['operator_id'], comment, datetime.now().strftime("%Y-%m-%d %H:%M:%S")))
    conn.commit()

    # ===== УВЕДОМЛЕНИЕ ПОЛЬЗОВАТЕЛЮ =====
    if ticket:
        send_notification(
            'user',
            ticket['user_id'],
            f'💬 Ответ в заявке #{ticket_id}',
            f'IT-специалист ответил на вашу заявку: {comment[:50]}...',
            'comment',
            f'/ticket/{ticket_id}'
        )
    # ===================================

    conn.close()

    flash('Комментарий добавлен', 'success')
    return redirect(url_for('operator_ticket', ticket_id=ticket_id))


@app.route('/ticket/<int:ticket_id>/comments')
def get_comments(ticket_id):
    """Получение комментариев к заявке (AJAX)"""
    conn = get_db_connection()

    comments = conn.execute('''
        SELECT c.*, 
               u.last_name as user_last_name, u.first_name as user_first_name,
               o.last_name as op_last_name, o.first_name as op_first_name
        FROM comments c
        LEFT JOIN users u ON c.user_id = u.id
        LEFT JOIN operators o ON c.operator_id = o.id
        WHERE c.ticket_id = ?
        ORDER BY c.created_at ASC
    ''', (ticket_id,)).fetchall()

    conn.close()

    return {'comments': [dict(c) for c in comments]}

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

        # Получаем информацию о заявке до обновления
        ticket_info = conn.execute('SELECT user_id, status FROM tickets WHERE id = ?', (ticket_id,)).fetchone()
        old_status = ticket_info['status'] if ticket_info else None

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

        # Уведомление пользователю при смене статуса (если статус изменился)
        if old_status != status:
            status_messages = {
                'new': '🆕 Новая',
                'in_progress': '⚙️ В работе',
                'resolved': '✅ Решена',
                'closed': '📦 Закрыта'
            }
            status_text = status_messages.get(status, status)
            send_notification(
                'user',
                ticket_info['user_id'],
                f'🔄 Статус заявки #{ticket_id} изменен',
                f'Статус вашей заявки изменен на "{status_text}"',
                'status_change',
                f'/ticket/{ticket_id}'
            )

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
        import re

        # Получаем описание
        description = request.form.get('description', '')

        # ===== АГРЕССИВНАЯ ОЧИСТКА ПЕРЕД СОХРАНЕНИЕМ =====
        # Заменяем все виды переносов на \n
        description = description.replace('\r\n', '\n').replace('\r', '\n')

        # Разбиваем на строки и чистим каждую
        lines = description.split('\n')
        cleaned_lines = []
        for line in lines:
            # Убираем пробелы в начале и конце строки
            clean_line = line.strip()
            # Пропускаем пустые строки и строки-маркеры
            if clean_line and not re.match(r'^[-=*_]{3,}$', clean_line):
                cleaned_lines.append(clean_line)

        # Соединяем с одним переносом
        description = '\n'.join(cleaned_lines)

        # Убираем множественные пробелы внутри строки
        description = re.sub(r'[ \t]+', ' ', description)
        description = description.strip()

        if not description:
            description = 'Описание не указано'

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
            conn.commit()
            ticket_id = conn.execute('SELECT last_insert_rowid()').fetchone()[0]

            # ===== УВЕДОМЛЕНИЯ О НОВОЙ ЗАЯВКЕ =====
            # Отправляем уведомление всем операторам
            send_notification_to_all_operators(
                f'🆕 Новая заявка #{ticket_id}',
                f'Пользователь {session["full_name"]} создал новую заявку',
                'new_ticket',
                f'/operator/ticket/{ticket_id}'
            )

            # Отправляем уведомление всем администраторам
            send_notification_to_all_admins(
                f'🆕 Новая заявка #{ticket_id}',
                f'Пользователь {session["full_name"]} создал новую заявку',
                'new_ticket',
                f'/admin/ticket/edit/{ticket_id}'
            )
            # ===================================

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

    # Заменяем все виды переносов на \n
    s = s.replace('\r\n', '\n').replace('\r', '\n')

    # Убираем маркеры
    s = re.sub(r'^[-=*_]{3,}$', '', s, flags=re.MULTILINE)

    # Разбиваем на строки
    lines = s.split('\n')
    cleaned_lines = []

    for line in lines:
        # Убираем пробелы в начале и конце строки
        clean_line = line.strip()
        # Пропускаем пустые строки
        if clean_line:
            cleaned_lines.append(clean_line)

    # Соединяем
    result = '\n'.join(cleaned_lines)

    # Убираем множественные пробелы
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
            tickets = conn.execute('''
                SELECT t.*, u.last_name, u.first_name, u.middle_name, u.post, u.phone, u.username,
                       o.last_name as op_last_name, o.first_name as op_first_name,
                       CAST(ROUND((julianday('now') - julianday(t.created_at)) * 24, 2) AS REAL) as hours_since_created
                FROM tickets t 
                JOIN users u ON t.user_id = u.id 
                LEFT JOIN operators o ON t.assigned_to = o.id
                WHERE t.status NOT IN ('resolved', 'closed')
                ORDER BY 
                    CASE t.priority
                        WHEN 'high' THEN 1
                        WHEN 'medium' THEN 2
                        WHEN 'low' THEN 3
                        ELSE 4
                    END,
                    CASE t.status 
                        WHEN 'new' THEN 1
                        WHEN 'in_progress' THEN 2
                        ELSE 3
                    END, 
                    t.id DESC
            ''').fetchall()
        elif status_filter == 'resolved':
            tickets = conn.execute('''
                SELECT t.*, u.last_name, u.first_name, u.middle_name, u.post, u.phone, u.username,
                       o.last_name as op_last_name, o.first_name as op_first_name,
                       CAST(ROUND((julianday('now') - julianday(t.created_at)) * 24, 2) AS REAL) as hours_since_created
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
                       CAST(ROUND((julianday('now') - julianday(t.created_at)) * 24, 2) AS REAL) as hours_since_created
                FROM tickets t 
                JOIN users u ON t.user_id = u.id 
                LEFT JOIN operators o ON t.assigned_to = o.id
                WHERE t.status = 'new'
                ORDER BY 
                    CASE t.priority
                        WHEN 'high' THEN 1
                        WHEN 'medium' THEN 2
                        WHEN 'low' THEN 3
                        ELSE 4
                    END,
                    t.id DESC
            ''').fetchall()
        elif status_filter == 'in_progress':
            tickets = conn.execute('''
                SELECT t.*, u.last_name, u.first_name, u.middle_name, u.post, u.phone, u.username,
                       o.last_name as op_last_name, o.first_name as op_first_name,
                       CAST(ROUND((julianday('now') - julianday(t.created_at)) * 24, 2) AS REAL) as hours_since_created
                FROM tickets t 
                JOIN users u ON t.user_id = u.id 
                LEFT JOIN operators o ON t.assigned_to = o.id
                WHERE t.status = 'in_progress'
                ORDER BY 
                    CASE t.priority
                        WHEN 'high' THEN 1
                        WHEN 'medium' THEN 2
                        WHEN 'low' THEN 3
                        ELSE 4
                    END,
                    t.id DESC
            ''').fetchall()
        else:
            tickets = conn.execute('''
                SELECT t.*, u.last_name, u.first_name, u.middle_name, u.post, u.phone, u.username,
                       o.last_name as op_last_name, o.first_name as op_first_name,
                       CAST(ROUND((julianday('now') - julianday(t.created_at)) * 24, 2) AS REAL) as hours_since_created
                FROM tickets t 
                JOIN users u ON t.user_id = u.id 
                LEFT JOIN operators o ON t.assigned_to = o.id
                WHERE t.status NOT IN ('resolved', 'closed')
                ORDER BY t.id DESC
            ''').fetchall()
    except sqlite3.OperationalError as e:
        print(f"Ошибка БД: {e}")
        tickets = []

    # ============ СТАТИСТИКА ДЛЯ ОПЕРАТОРА ============
    # Общая статистика
    total_tickets = conn.execute('SELECT COUNT(*) FROM tickets').fetchone()[0]
    new_tickets = conn.execute('SELECT COUNT(*) FROM tickets WHERE status = "new"').fetchone()[0]
    in_progress = conn.execute('SELECT COUNT(*) FROM tickets WHERE status = "in_progress"').fetchone()[0]
    resolved = conn.execute('SELECT COUNT(*) FROM tickets WHERE status IN ("resolved", "closed")').fetchone()[0]

    # Статистика по текущему оператору
    my_tickets = \
    conn.execute('SELECT COUNT(*) FROM tickets WHERE assigned_to = ?', (session['operator_id'],)).fetchone()[0]
    my_in_progress = conn.execute('SELECT COUNT(*) FROM tickets WHERE assigned_to = ? AND status = "in_progress"',
                                  (session['operator_id'],)).fetchone()[0]
    my_resolved = \
    conn.execute('SELECT COUNT(*) FROM tickets WHERE assigned_to = ? AND status IN ("resolved", "closed")',
                 (session['operator_id'],)).fetchone()[0]

    # Заявки за сегодня
    today = datetime.now().strftime("%Y-%m-%d")
    tickets_today = conn.execute('SELECT COUNT(*) FROM tickets WHERE date(created_at) = ?', (today,)).fetchone()[0]

    operators = conn.execute('SELECT id, last_name, first_name FROM operators ORDER BY last_name').fetchall()
    conn.close()

    return render_template('operators/operator_dashboard.html',
                           tickets=tickets,
                           current_filter=status_filter,
                           operators=operators,
                           # Статистика
                           total_tickets=total_tickets,
                           new_tickets=new_tickets,
                           in_progress=in_progress,
                           resolved=resolved,
                           my_tickets=my_tickets,
                           my_in_progress=my_in_progress,
                           my_resolved=my_resolved,
                           tickets_today=tickets_today)

@app.route('/operator/get_templates/<category>')
@operator_required
def get_templates(category):
    """Получение шаблонов ответов по категории"""
    conn = get_db_connection()
    if category == 'all':
        templates = conn.execute('SELECT * FROM answer_templates ORDER BY category, name').fetchall()
    else:
        templates = conn.execute(
            'SELECT * FROM answer_templates WHERE category = ? OR category = "common" ORDER BY name',
            (category,)).fetchall()
    conn.close()

    return {'templates': [dict(t) for t in templates]}


@app.route('/operator/ticket/<int:ticket_id>', methods=['GET', 'POST'])
@operator_required
def operator_ticket(ticket_id):
    conn = get_db_connection()

    if request.method == 'POST':
        status = request.form['status']
        priority = request.form['priority']
        answer = request.form.get('answer', '')
        updated_at = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

        # Получаем информацию о заявке до обновления
        ticket_info = conn.execute('SELECT user_id, assigned_to, status FROM tickets WHERE id = ?',
                                   (ticket_id,)).fetchone()
        old_status = ticket_info['status'] if ticket_info else None

        if status == 'in_progress' and not \
        conn.execute('SELECT assigned_to FROM tickets WHERE id = ?', (ticket_id,)).fetchone()['assigned_to']:
            conn.execute('UPDATE tickets SET assigned_to = ?, updated_at = ? WHERE id = ?',
                         (session['operator_id'], updated_at, ticket_id))

        if status == 'resolved':
            completed_at = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            conn.execute(
                'UPDATE tickets SET status = ?, operator_answer = ?, priority = ?, updated_at = ?, completed_at = ? WHERE id = ?',
                (status, answer, priority, updated_at, completed_at, ticket_id))

            # ===== УВЕДОМЛЕНИЕ О РЕШЕНИИ ЗАЯВКИ =====
            send_notification(
                'user',
                ticket_info['user_id'],
                f'✅ Заявка #{ticket_id} решена',
                f'Ваша заявка # {ticket_id} решена. Ответ: {answer[:50]}...',
                'success',
                f'/ticket/{ticket_id}'
            )
            # ======================================

        elif status == 'closed':
            closed_at = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            conn.execute(
                'UPDATE tickets SET status = ?, operator_answer = ?, priority = ?, updated_at = ?, completed_at = ? WHERE id = ?',
                (status, answer, priority, updated_at, closed_at, ticket_id))

            # ===== УВЕДОМЛЕНИЕ О ЗАКРЫТИИ ЗАЯВКИ =====
            send_notification(
                'user',
                ticket_info['user_id'],
                f'📦 Заявка #{ticket_id} закрыта',
                f'Ваша заявка # {ticket_id} закрыта. Если остались вопросы - создайте новую.',
                'info',
                f'/ticket/{ticket_id}'
            )
            # ======================================

        else:
            conn.execute(
                'UPDATE tickets SET status = ?, operator_answer = ?, priority = ?, updated_at = ? WHERE id = ?',
                (status, answer, priority, updated_at, ticket_id))

            # Уведомление при смене статуса (не resolved и не closed)
            if old_status != status:
                status_messages = {
                    'new': '🆕 Новая',
                    'in_progress': '⚙️ В работе'
                }
                status_text = status_messages.get(status, status)
                send_notification(
                    'user',
                    ticket_info['user_id'],
                    f'🔄 Статус заявки #{ticket_id} изменен',
                    f'Статус вашей заявки изменен на "{status_text}"',
                    'status_change',
                    f'/ticket/{ticket_id}'
                )

        conn.commit()
        flash('Заявка обновлена', 'success')
        conn.close()
        return redirect(url_for('operator_dashboard'))

    ticket = conn.execute('''
        SELECT t.*, u.last_name, u.first_name, u.middle_name, u.post, u.phone, u.username, u.email,
               o.last_name as op_last_name, o.first_name as op_first_name, o.middle_name as op_middle_name, o.post as op_post,
               ROUND(MAX(0, julianday('now') - julianday(t.created_at)), 2) as hours_since_created
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
            # Полное ФИО
            full_name_parts = []
            if user['last_name']:
                full_name_parts.append(user['last_name'])
            if user['first_name']:
                full_name_parts.append(user['first_name'])
            if user['middle_name']:
                full_name_parts.append(user['middle_name'])
            full_name = ' '.join(full_name_parts)

            user_info = {
                'id': user['id'],
                'username': user['username'],
                'email': user['email'],
                'full_name': full_name,
                'first_name': user['first_name'],
                'last_name': user['last_name'],
                'middle_name': user['middle_name'],
                'post': user['post'],
                'department': user['department'],
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


# ===================== УВЕДОМЛЕНИЯ =====================

def send_notification(recipient_type, recipient_id, title, message, notification_type='info', link=None):
    """Отправка уведомления"""
    conn = get_db_connection()

    try:
        if recipient_type == 'user':
            conn.execute('''
                INSERT INTO notifications (user_id, title, message, type, link, created_at)
                VALUES (?, ?, ?, ?, ?, ?)
            ''', (recipient_id, title, message, notification_type, link, datetime.now().strftime("%Y-%m-%d %H:%M:%S")))
        elif recipient_type == 'operator':
            conn.execute('''
                INSERT INTO notifications (operator_id, title, message, type, link, created_at)
                VALUES (?, ?, ?, ?, ?, ?)
            ''', (recipient_id, title, message, notification_type, link, datetime.now().strftime("%Y-%m-%d %H:%M:%S")))
        elif recipient_type == 'admin':
            conn.execute('''
                INSERT INTO notifications (admin_id, title, message, type, link, created_at)
                VALUES (?, ?, ?, ?, ?, ?)
            ''', (recipient_id, title, message, notification_type, link, datetime.now().strftime("%Y-%m-%d %H:%M:%S")))

        conn.commit()
    except Exception as e:
        print(f"Ошибка в send_notification: {e}")
    finally:
        conn.close()


def send_notification_to_all_operators(title, message, notification_type='info', link=None):
    """Отправка уведомления всем операторам"""
    conn = get_db_connection()
    operators = conn.execute('SELECT id FROM operators').fetchall()
    conn.close()  # Важно! Закрываем соединение

    for op in operators:
        send_notification('operator', op['id'], title, message, notification_type, link)


def send_notification_to_all_admins(title, message, notification_type='info', link=None):
    """Отправка уведомления всем администраторам"""
    conn = get_db_connection()
    admins = conn.execute('SELECT id FROM admins').fetchall()
    conn.close()  # Важно! Закрываем соединение

    for admin in admins:
        send_notification('admin', admin['id'], title, message, notification_type, link)


@app.route('/notifications')
@login_required
def get_notifications():
    """Получение уведомлений пользователя (AJAX)"""
    try:
        conn = get_db_connection()

        # Проверяем существование таблицы
        conn.execute('SELECT 1 FROM notifications LIMIT 1')

        # Уведомления для пользователя
        notifications = conn.execute('''
            SELECT * FROM notifications 
            WHERE user_id = ? 
            ORDER BY created_at DESC LIMIT 50
        ''', (session['user_id'],)).fetchall()

        unread_count = conn.execute('''
            SELECT COUNT(*) FROM notifications 
            WHERE user_id = ? AND is_read = 0
        ''', (session['user_id'],)).fetchone()[0]

        conn.close()

        return jsonify({
            'notifications': [dict(n) for n in notifications],
            'unread_count': unread_count
        })
    except Exception as e:
        print(f"Ошибка в get_notifications: {e}")
        return jsonify({
            'notifications': [],
            'unread_count': 0,
            'error': str(e)
        })


@app.route('/operator/notifications')
@operator_required
def operator_get_notifications():
    conn = get_db_connection()
    notifications = conn.execute('''
        SELECT * FROM notifications 
        WHERE operator_id = ? 
        ORDER BY created_at DESC LIMIT 50
    ''', (session['operator_id'],)).fetchall()
    unread_count = conn.execute('''
        SELECT COUNT(*) FROM notifications 
        WHERE operator_id = ? AND is_read = 0
    ''', (session['operator_id'],)).fetchone()[0]
    conn.close()
    return jsonify({
        'notifications': [dict(n) for n in notifications],
        'unread_count': unread_count
    })


@app.route('/debug/create_notification')
def debug_create_notification():
    """Создание тестового уведомления"""
    import sqlite3
    from datetime import datetime

    if not session.get('user_id') and not session.get('operator_logged_in'):
        return 'Не авторизован'

    conn = get_db_connection()

    # Для пользователя
    if session.get('user_id'):
        conn.execute('''
            INSERT INTO notifications (user_id, title, message, type, link, created_at)
            VALUES (?, ?, ?, ?, ?, ?)
        ''', (session['user_id'], '🔔 Тестовое уведомление', 'Это проверка работы уведомлений!', 'info', '/dashboard',
              datetime.now().strftime("%Y-%m-%d %H:%M:%S")))

    # Для оператора
    if session.get('operator_logged_in'):
        conn.execute('''
            INSERT INTO notifications (operator_id, title, message, type, link, created_at)
            VALUES (?, ?, ?, ?, ?, ?)
        ''', (session['operator_id'], '🔔 Тестовое уведомление', 'Это проверка работы уведомлений!', 'info',
              '/operator/dashboard', datetime.now().strftime("%Y-%m-%d %H:%M:%S")))

    conn.commit()
    conn.close()

    return '✅ Тестовое уведомление создано! Обновите страницу и нажмите на 🔔'

@app.route('/admin/notifications')
@admin_required
def admin_get_notifications():
    """Получение уведомлений администратора (AJAX)"""
    conn = get_db_connection()

    notifications = conn.execute('''
        SELECT * FROM notifications 
        WHERE admin_id = ? 
        ORDER BY created_at DESC LIMIT 50
    ''', (session['admin_id'],)).fetchall()

    unread_count = conn.execute('''
        SELECT COUNT(*) FROM notifications 
        WHERE admin_id = ? AND is_read = 0
    ''', (session['admin_id'],)).fetchone()[0]

    conn.close()

    return jsonify({
        'notifications': [dict(n) for n in notifications],
        'unread_count': unread_count
    })


@app.route('/notifications/mark_read/<int:notif_id>', methods=['POST'])
@login_required
def mark_notification_read(notif_id):
    """Отметить уведомление как прочитанное"""
    conn = get_db_connection()
    conn.execute('UPDATE notifications SET is_read = 1 WHERE id = ?', (notif_id,))
    conn.commit()
    conn.close()
    return jsonify({'success': True})


@app.route('/notifications/mark_all_read', methods=['POST'])
@login_required
def mark_all_notifications_read():
    """Отметить все уведомления как прочитанные"""
    conn = get_db_connection()
    conn.execute('UPDATE notifications SET is_read = 1 WHERE user_id = ?', (session['user_id'],))
    conn.commit()
    conn.close()
    return jsonify({'success': True})


if __name__ == '__main__':
    init_db()
    app.run(debug=True)