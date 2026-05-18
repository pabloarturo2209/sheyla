from flask import Flask, render_template, request, redirect, url_for, session
import sqlite3

app = Flask(__name__)
app.secret_key = "clave_secreta"

# ---------------- BASE DE DATOS ----------------

def crear_bd():

    conn = sqlite3.connect("prestamos.db")
    cursor = conn.cursor()

    # TABLA ADMIN
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS admin (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        usuario TEXT,
        contraseña TEXT
    )
    """)

    # TABLA CLIENTES
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS clientes (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        nombre TEXT,
        telefono TEXT
    )
    """)

    # TABLA PRESTAMOS
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS prestamos (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        cliente_id INTEGER,
        monto REAL,
        interes REAL,
        plazo TEXT,
        estado TEXT
    )
    """)

    # TABLA PAGOS
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS pagos (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        prestamo_id INTEGER,
        cantidad REAL
    )
    """)

    # CREAR ADMIN POR DEFECTO
    cursor.execute("SELECT * FROM admin")
    admin = cursor.fetchone()

    if not admin:

        cursor.execute("""
        INSERT INTO admin (usuario, contraseña)
        VALUES (?, ?)
        """, ("admin", "1234"))

    conn.commit()
    conn.close()

crear_bd()

# ---------------- LOGIN ----------------

@app.route("/", methods=["GET", "POST"])
def login():

    if request.method == "POST":

        usuario = request.form["usuario"]
        contraseña = request.form["contraseña"]

        conn = sqlite3.connect("prestamos.db")
        cursor = conn.cursor()

        cursor.execute("""
        SELECT * FROM admin
        WHERE usuario = ? AND contraseña = ?
        """, (usuario, contraseña))

        admin = cursor.fetchone()

        conn.close()

        if admin:

            session["admin"] = usuario

            return redirect(url_for("panel"))

    return render_template("login.html")

# ---------------- PANEL ----------------

@app.route("/panel")
def panel():

    if "admin" not in session:
        return redirect(url_for("login"))

    return render_template("panel.html")

# ---------------- CLIENTES ----------------

@app.route("/clientes", methods=["GET", "POST"])
def clientes():

    if "admin" not in session:
        return redirect(url_for("login"))

    conn = sqlite3.connect("prestamos.db")
    cursor = conn.cursor()

    if request.method == "POST":

        nombre = request.form["nombre"]
        telefono = request.form["telefono"]

        cursor.execute("""
        INSERT INTO clientes (nombre, telefono)
        VALUES (?, ?)
        """, (nombre, telefono))

        conn.commit()

    cursor.execute("SELECT * FROM clientes")
    datos = cursor.fetchall()

    conn.close()

    return render_template("clientes.html", datos=datos)

# ---------------- PRESTAMOS ----------------

@app.route("/prestamos", methods=["GET", "POST"])
def prestamos():

    if "admin" not in session:
        return redirect(url_for("login"))

    conn = sqlite3.connect("prestamos.db")
    cursor = conn.cursor()

    if request.method == "POST":

        cliente_id = request.form["cliente_id"]
        monto = request.form["monto"]
        interes = request.form["interes"]
        plazo = request.form["plazo"]

        cursor.execute("""
        INSERT INTO prestamos
        (cliente_id, monto, interes, plazo, estado)

        VALUES (?, ?, ?, ?, ?)
        """, (
            cliente_id,
            monto,
            interes,
            plazo,
            "Pendiente"
        ))

        conn.commit()

    cursor.execute("""
    SELECT id, nombre, telefono
    FROM clientes
    """)

    clientes = cursor.fetchall()

    cursor.execute("""
    SELECT
        prestamos.id,
        clientes.nombre,
        prestamos.monto,
        prestamos.interes,
        prestamos.plazo,
        prestamos.estado

    FROM prestamos

    INNER JOIN clientes
    ON prestamos.cliente_id = clientes.id
    """)

    datos = cursor.fetchall()

    conn.close()

    return render_template(
        "prestamos.html",
        clientes=clientes,
        datos=datos
    )

# ---------------- HISTORIAL CLIENTE ----------------

@app.route("/historial_cliente/<int:cliente_id>")
def historial_cliente(cliente_id):

    if "admin" not in session:
        return redirect(url_for("login"))

    conn = sqlite3.connect("prestamos.db")
    cursor = conn.cursor()

    cursor.execute("""
    SELECT * FROM clientes
    WHERE id = ?
    """, (cliente_id,))

    cliente = cursor.fetchone()

    cursor.execute("""
    SELECT id, monto, interes, plazo, estado
    FROM prestamos
    WHERE cliente_id = ?
    """, (cliente_id,))

    prestamos_db = cursor.fetchall()

    prestamos = []

    for prestamo in prestamos_db:

        prestamo_id = prestamo[0]
        monto = prestamo[1]
        interes = prestamo[2]
        plazo = prestamo[3]
        estado = prestamo[4]

        cursor.execute("""
        SELECT SUM(cantidad)
        FROM pagos
        WHERE prestamo_id = ?
        """, (prestamo_id,))

        total_abonado = cursor.fetchone()[0]

        if total_abonado is None:
            total_abonado = 0

        saldo = monto - total_abonado

        prestamos.append({
            "id": prestamo_id,
            "monto": monto,
            "interes": interes,
            "plazo": plazo,
            "estado": estado,
            "abonado": total_abonado,
            "saldo": saldo
        })

    conn.close()

    return render_template(
        "historial_cliente.html",
        cliente=cliente,
        prestamos=prestamos
    )

# ---------------- PAGOS ----------------

@app.route("/pagos", methods=["GET", "POST"])
def pagos():

    if "admin" not in session:
        return redirect(url_for("login"))

    conn = sqlite3.connect("prestamos.db")
    cursor = conn.cursor()

    if request.method == "POST":

        prestamo_id = request.form["prestamo_id"]
        cantidad = float(request.form["cantidad"])

        cursor.execute("""
        INSERT INTO pagos (prestamo_id, cantidad)
        VALUES (?, ?)
        """, (prestamo_id, cantidad))

        cursor.execute("""
        SELECT monto FROM prestamos
        WHERE id = ?
        """, (prestamo_id,))

        monto_prestamo = cursor.fetchone()[0]

        cursor.execute("""
        SELECT SUM(cantidad)
        FROM pagos
        WHERE prestamo_id = ?
        """, (prestamo_id,))

        total_abonado = cursor.fetchone()[0]

        if total_abonado >= monto_prestamo:
            cursor.execute("""
            UPDATE prestamos
            SET estado = 'Pagado'
            WHERE id = ?
            """, (prestamo_id,))
        else:
            cursor.execute("""
            UPDATE prestamos
            SET estado = 'Pendiente'
            WHERE id = ?
            """, (prestamo_id,))

        conn.commit()

    cursor.execute("""
    SELECT
        prestamos.id,
        clientes.nombre,
        prestamos.monto,
        prestamos.estado
    FROM prestamos
    INNER JOIN clientes
    ON prestamos.cliente_id = clientes.id
    """)

    prestamos_db = cursor.fetchall()

    prestamos = []

    for prestamo in prestamos_db:

        prestamo_id = prestamo[0]
        monto = prestamo[2]

        cursor.execute("""
        SELECT SUM(cantidad)
        FROM pagos
        WHERE prestamo_id = ?
        """, (prestamo_id,))

        abonado = cursor.fetchone()[0]

        if abonado is None:
            abonado = 0

        saldo = monto - abonado

        prestamos.append({
            "id": prestamo_id,
            "cliente": prestamo[1],
            "monto": monto,
            "estado": prestamo[3],
            "abonado": abonado,
            "saldo": saldo
        })

    conn.close()

    return render_template("pagos.html", prestamos=prestamos)
# ---------------- LOGOUT ----------------

@app.route("/logout")
def logout():

    session.clear()

    return redirect(url_for("login"))

# ---------------- EJECUTAR ----------------

if __name__ == "__main__":
    app.run(debug=True)