from flask import Flask, render_template, request, jsonify
from datetime import datetime
import sqlite3, platform
from pathlib import Path

DB_FILE = Path(__file__).with_suffix(".db")
app = Flask(__name__)

def get_db():
    con = sqlite3.connect(DB_FILE, check_same_thread=False)
    con.execute("CREATE TABLE IF NOT EXISTS conteo (sku TEXT PRIMARY KEY, cantidad INTEGER DEFAULT 0)")
    con.execute("CREATE TABLE IF NOT EXISTS ticket (id INTEGER PRIMARY KEY AUTOINCREMENT, numero INTEGER NOT NULL)")
    if con.execute("SELECT COUNT(*) FROM ticket").fetchone()[0] == 0:
        con.execute("INSERT INTO ticket (numero) VALUES (1)")
    con.commit()
    return con

# Productos para el evento ANTARES
PRODUCTOS = [
    {"sku": "antares-burger", "nombre": "HAMBURGUESA ANTARES ESPECIAL", "precio": 30.00, "color": "#FF7B25"},
    {"sku": "antares-hotdog", "nombre": "HOT DOG ANTARES CON PAPAS", "precio": 18.00, "color": "#FFB627"},
    {"sku": "antares-combo", "nombre": "COMBO FAMILIAR ANTARES", "precio": 85.00, "color": "#FF4E00"},
    {"sku": "antares-bebida", "nombre": "BEBIDA ANTARES 500ML", "precio": 8.00, "color": "#D32F2F"},
    {"sku": "antares-postre", "nombre": "POSTRE ANTARES ESPECIAL", "precio": 12.00, "color": "#7B1FA2"},
]

# ---------- RUTAS FLASK ----------
@app.route("/")
def index():
    db = get_db()
    items = []
    for p in PRODUCTOS:
        cant = (db.execute("SELECT cantidad FROM conteo WHERE sku=?", (p["sku"],)).fetchone() or (0,))[0]
        items.append({**p, "cant": cant})
    total = sum(p["cant"] * p["precio"] for p in items)
    return render_template("index.html", items=items, total=total)

@app.route("/add", methods=["POST"])
def add():
    sku = request.json["sku"]
    db = get_db()
    nueva = (db.execute("SELECT cantidad FROM conteo WHERE sku=?", (sku,)).fetchone() or (0,))[0] + 1
    db.execute("INSERT OR REPLACE INTO conteo(sku, cantidad) VALUES(?,?)", (sku, nueva))
    db.commit()
    if platform.system() == "Windows":
        imprimir_ticket([(next(p for p in PRODUCTOS if p["sku"] == sku), 1)], copias=2)
    return jsonify({"cant": nueva})

@app.route("/imprimir", methods=["POST"])
def imprimir():
    db = get_db()
    items = [(p, (db.execute("SELECT cantidad FROM conteo WHERE sku=?", (p["sku"],)).fetchone() or (0,))[0])
             for p in PRODUCTOS if (db.execute("SELECT cantidad FROM conteo WHERE sku=?", (p["sku"],)).fetchone() or (0,))[0] > 0]
    if items:
        imprimir_ticket(items, copias=2)
    return jsonify({"ok": True})

@app.route("/reset", methods=["POST"])
def reset():
    db = get_db()
    for p in PRODUCTOS:
        db.execute("UPDATE conteo SET cantidad=0 WHERE sku=?", (p["sku"],))
    db.commit()
    return jsonify({"ok": True})

# ---------- IMPRESIÓN MEJORADA ----------
def imprimir_ticket(items, copias=1):
    try:
        import win32print, pywintypes
    except ImportError:
        return

    db = get_db()
    n = (db.execute("SELECT numero FROM ticket ORDER BY id DESC LIMIT 1").fetchone() or (1,))[0]
    db.execute("UPDATE ticket SET numero=numero+1")
    db.commit()
    f = datetime.now().strftime("%d/%m/%Y %H:%M")

    for copia in range(1, copias + 1):
        # ---- CABECERA ----
        lineas = []
        lineas.append("        EVENTO ANTARES FESTIVAL 2024")
        lineas.append("     CENTRO DE CONVENCIONES ANTARES")
        lineas.append("=" * 48)
        lineas.append(f"Ticket: {n:04d}    Fecha: {f}")
        if copias > 1:
            lineas.append(f"          COPIA {copia} de {copias}")
        lineas.append("=" * 48)
        lineas.append("PRODUCTO                 CANT  P.U.   TOTAL")
        lineas.append("-" * 48)

        # ---- PRODUCTOS ----
        total = 0.0
        for info, cant in items:
            sub = cant * info["precio"]
            total += sub
            nombre = info['nombre'][:32]
            lineas.append(f"{nombre:<32} {cant:>4}  {info['precio']:>5.2f}  {sub:>6.2f}")

        # ---- PIE ----
        lineas.append("-" * 50)
        lineas.append(f"TOTAL:{' ' * 30} S/{total:>7.2f}")
        lineas.append("=" * 50)
        lineas.append("     🙏 Gracias por tu visita a ANTARES 🙏")
        lineas.append("")
        lineas.append("")

        txt = "\n".join(lineas)
        raw = txt.encode('cp437', errors='ignore') + b'\x1B\x64\x02\x1D\x56\x00'

        try:
            h = win32print.OpenPrinter("BASIC230")
            win32print.StartDocPrinter(h, 1, ("ticket", None, "RAW"))
            win32print.StartPagePrinter(h)
            win32print.WritePrinter(h, raw)
            win32print.EndPagePrinter(h)
            win32print.EndDocPrinter(h)
            win32print.ClosePrinter(h)
        except:
            pass

if __name__ == "__main__":
    app.run(debug=False, port=5000)
