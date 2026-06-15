# app.py - Backend TechStore S.A.C.
from flask import Flask, request, jsonify, render_template, redirect, session, url_for
from flask_cors import CORS
import sqlite3
import os

app = Flask(__name__)
app.secret_key = 'techstore_secret_2026'
CORS(app)  # Habilitar CORS para permitir peticiones desde Flutter

DB_PATH = os.path.join(os.path.dirname(__file__), 'database.db')

def get_db():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn

def init_db():
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS usuario (
            id       INTEGER PRIMARY KEY AUTOINCREMENT,
            username TEXT    NOT NULL UNIQUE,
            password TEXT    NOT NULL,
            nombre   TEXT,
            activo   INTEGER DEFAULT 1
        )
    ''')
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS producto (
            id          INTEGER PRIMARY KEY AUTOINCREMENT,
            codigo      TEXT    NOT NULL UNIQUE,
            nombre      TEXT    NOT NULL,
            categoria   TEXT    NOT NULL,
            precio      REAL    NOT NULL,
            stock       INTEGER DEFAULT 0,
            descripcion TEXT
        )
    ''')

    # Insertar datos de prueba si las tablas están vacías
    cursor.execute('SELECT COUNT(*) FROM usuario')
    if cursor.fetchone()[0] == 0:
        cursor.execute(
            'INSERT INTO usuario (username, password, nombre) VALUES (?,?,?)',
            ('admin', 'admin123', 'Administrador TechStore')
        )
        cursor.execute(
            'INSERT INTO usuario (username, password, nombre) VALUES (?,?,?)',
            ('vendedor1', 'pass123', 'Juan Pérez')
        )

    cursor.execute('SELECT COUNT(*) FROM producto')
    if cursor.fetchone()[0] == 0:
        productos = [
            ('PROD-001', 'Laptop HP 15', 'Laptops', 2599.90, 10, 'Laptop HP 15.6 pulgadas, Intel Core i5, 8GB RAM, 512GB SSD'),
            ('PROD-002', 'Laptop Dell Inspiron', 'Laptops', 2899.90, 8, 'Dell Inspiron 15, Intel Core i7, 16GB RAM, 512GB SSD'),
            ('PROD-003', 'Smartphone Samsung Galaxy A54', 'Smartphones', 1299.90, 25, 'Samsung Galaxy A54, 128GB, 6GB RAM, cámara 50MP'),
            ('PROD-004', 'Tablet iPad Air', 'Tablets', 3499.90, 5, 'Apple iPad Air 10.9, chip M1, 64GB, WiFi'),
            ('PROD-005', 'Mouse Logitech MX Master 3', 'Periféricos', 399.90, 30, 'Mouse inalámbrico ergonómico de alta precisión'),
            ('PROD-006', 'Teclado Mecánico Redragon', 'Periféricos', 299.90, 20, 'Teclado mecánico RGB, switches azules, anti-ghosting'),
            ('PROD-007', 'Monitor LG 24 pulgadas', 'Monitores', 799.90, 12, 'Monitor Full HD IPS, 75Hz, HDMI, DisplayPort'),
            ('PROD-008', 'SSD Kingston 1TB', 'Almacenamiento', 299.90, 40, 'SSD NVMe M.2 PCIe 4.0, lectura 3500MB/s'),
        ]
        cursor.executemany(
            'INSERT INTO producto (codigo, nombre, categoria, precio, stock, descripcion) VALUES (?,?,?,?,?,?)',
            productos
        )

    conn.commit()
    conn.close()
    print('[DB] Base de datos inicializada correctamente.')

# Inicializar la base de datos al importar el módulo (necesario para Gunicorn en Render)
init_db()

# ─────────────────────────────────────────
# Endpoints REST (API para Flutter)
# ─────────────────────────────────────────

# POST /api/login
@app.route('/api/login', methods=['POST'])
def api_login():
    datos = request.get_json()
    if not datos or 'username' not in datos or 'password' not in datos:
        return jsonify({'ok': False, 'mensaje': 'Datos incompletos'}), 400

    conn = get_db()
    cursor = conn.cursor()
    cursor.execute(
        'SELECT id, username, nombre FROM usuario WHERE username=? AND password=? AND activo=1',
        (datos['username'].strip(), datos['password'])
    )
    usuario = cursor.fetchone()
    conn.close()

    if usuario:
        return jsonify({'ok': True, 'mensaje': 'Acceso exitoso',
            'usuario': {'id': usuario['id'], 'username': usuario['username'],
                        'nombre': usuario['nombre']}}), 200
    else:
        return jsonify({'ok': False, 'mensaje': 'Credenciales incorrectas'}), 401

# GET /api/productos
@app.route('/api/productos', methods=['GET'])
def listar_productos():
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute('SELECT * FROM producto ORDER BY nombre')
    rows = cursor.fetchall()
    conn.close()
    return jsonify([dict(row) for row in rows]), 200

# GET /api/productos/buscar?q=<termino>
@app.route('/api/productos/buscar', methods=['GET'])
def buscar_productos():
    q = request.args.get('q', '').strip()
    if not q:
        return jsonify([]), 200

    conn = get_db()
    cursor = conn.cursor()
    termino = f'%{q}%'
    cursor.execute(
        'SELECT * FROM producto WHERE codigo LIKE ? OR nombre LIKE ? OR categoria LIKE ? ORDER BY nombre',
        (termino, termino, termino))
    rows = cursor.fetchall()
    conn.close()
    return jsonify([dict(row) for row in rows]), 200

# POST /api/productos
@app.route('/api/productos', methods=['POST'])
def registrar_producto():
    datos = request.get_json()
    try:
        conn = get_db()
        cursor = conn.cursor()
        cursor.execute(
            'INSERT INTO producto (codigo, nombre, categoria, precio, stock, descripcion) VALUES (?,?,?,?,?,?)',
            (datos['codigo'], datos['nombre'], datos['categoria'],
             datos['precio'], datos.get('stock', 0), datos.get('descripcion', '')))
        conn.commit()
        new_id = cursor.lastrowid
        conn.close()
        return jsonify({'ok': True, 'mensaje': 'Producto registrado', 'id': new_id}), 201
    except sqlite3.IntegrityError:
        return jsonify({'ok': False, 'mensaje': 'El código ya existe'}), 409

# PUT /api/productos/<id>
@app.route('/api/productos/<int:prod_id>', methods=['PUT'])
def actualizar_producto(prod_id):
    datos = request.get_json()
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute(
        'UPDATE producto SET nombre=?, categoria=?, precio=?, stock=?, descripcion=? WHERE id=?',
        (datos.get('nombre'), datos.get('categoria'), datos.get('precio'),
         datos.get('stock', 0), datos.get('descripcion', ''), prod_id))
    conn.commit()
    conn.close()
    return jsonify({'ok': True, 'mensaje': 'Producto actualizado'}), 200

# DELETE /api/productos/<id>
@app.route('/api/productos/<int:prod_id>', methods=['DELETE'])
def eliminar_producto(prod_id):
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute('DELETE FROM producto WHERE id=?', (prod_id,))
    conn.commit()
    conn.close()
    return jsonify({'ok': True, 'mensaje': 'Producto eliminado'}), 200

# ─────────────────────────────────────────
# Rutas web de administración
# ─────────────────────────────────────────

@app.route('/', methods=['GET', 'POST'])
def web_login():
    error = None
    if request.method == 'POST':
        username = request.form.get('username', '').strip()
        password = request.form.get('password', '')
        conn = get_db()
        cursor = conn.cursor()
        cursor.execute(
            'SELECT id, username, nombre FROM usuario WHERE username=? AND password=? AND activo=1',
            (username, password)
        )
        usuario = cursor.fetchone()
        conn.close()
        if usuario:
            session['usuario'] = {'id': usuario['id'], 'username': usuario['username'], 'nombre': usuario['nombre']}
            return redirect(url_for('web_principal'))
        else:
            error = 'Credenciales incorrectas.'
    return render_template('login.html', error=error)

@app.route('/principal')
def web_principal():
    if 'usuario' not in session:
        return redirect(url_for('web_login'))
    return render_template('principal.html', usuario=session['usuario'])

@app.route('/productos-web', methods=['GET', 'POST'])
def web_productos():
    if 'usuario' not in session:
        return redirect(url_for('web_login'))

    mensaje = None
    if request.method == 'POST':
        codigo = request.form.get('codigo', '').strip()
        nombre = request.form.get('nombre', '').strip()
        categoria = request.form.get('categoria', '').strip()
        precio = request.form.get('precio', 0)
        stock = request.form.get('stock', 0)
        descripcion = request.form.get('descripcion', '').strip()
        try:
            conn = get_db()
            cursor = conn.cursor()
            cursor.execute(
                'INSERT INTO producto (codigo, nombre, categoria, precio, stock, descripcion) VALUES (?,?,?,?,?,?)',
                (codigo, nombre, categoria, float(precio), int(stock), descripcion)
            )
            conn.commit()
            conn.close()
            mensaje = 'Producto registrado correctamente.'
        except sqlite3.IntegrityError:
            mensaje = 'Error: El código ya existe.'

    conn = get_db()
    cursor = conn.cursor()
    cursor.execute('SELECT * FROM producto ORDER BY nombre')
    productos = [dict(row) for row in cursor.fetchall()]
    conn.close()
    return render_template('productos.html', productos=productos, mensaje=mensaje, usuario=session['usuario'])

@app.route('/eliminar-producto/<int:prod_id>', methods=['POST'])
def web_eliminar_producto(prod_id):
    if 'usuario' not in session:
        return redirect(url_for('web_login'))
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute('DELETE FROM producto WHERE id=?', (prod_id,))
    conn.commit()
    conn.close()
    return redirect(url_for('web_productos'))

@app.route('/salir')
def web_salir():
    session.clear()
    return redirect(url_for('web_login'))

# ─────────────────────────────────────────
# Punto de arranque
# ─────────────────────────────────────────
if __name__ == '__main__':
    init_db()
    app.run(debug=True, host='0.0.0.0', port=5000)
