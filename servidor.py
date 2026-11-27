import os
from flask import Flask, request, jsonify
from flask_cors import CORS
import mysql.connector

app = Flask(__name__)
CORS(app)

def conectar():
    return mysql.connector.connect(
        host=os.environ.get("DB_HOST","mysql-27028d1c-plantitas.l.aivencloud.com"),
        port=int(os.environ.get("DB_PORT", 3306)),
        user=os.environ.get("DB_USER","avnadmin"),
        password=os.environ.get("DB_PASSWORD","AVNS_i6obPFXEL9WmI8TpD68"),
        database=os.environ.get("DB_NAME", "plantas_db"),
        ssl_disabled=False,
        connection_timeout=10  # Evita que Gunicorn se congele si Aiven tarda
    )

@app.route('/', methods=['GET'])
def inicio():
    return jsonify({"estado": "API AquaSmart TESOEM 5S2 conectada a Aiven"})

# RUTA OPTIMIZADA: Trae riego, foco y estado en 1 sola conexión a Aiven
@app.route('/todo', methods=['GET'])
def obtener_todo():
    conn = None
    try:
        conn = conectar()
        cursor = conn.cursor(dictionary=True)

        cursor.execute("SELECT * FROM registros ORDER BY id DESC LIMIT 40")
        datos = cursor.fetchall()

        cursor.execute("SELECT * FROM registros_foco ORDER BY id DESC LIMIT 40")
        foco = cursor.fetchall()

        cursor.execute("SELECT * FROM control_remoto WHERE id = 1")
        estado = cursor.fetchone()

        cursor.close()
        return jsonify({"datos": datos, "foco": foco, "estado": estado})
    except Exception as e:
        return jsonify({"error": str(e)}), 500
    finally:
        if conn and conn.is_connected():
            conn.close()

@app.route('/datos', methods=['GET'])
def obtener_datos():
    conn = None
    try:
        conn = conectar()
        cursor = conn.cursor(dictionary=True)
        cursor.execute("SELECT * FROM registros ORDER BY id DESC LIMIT 50")
        filas = cursor.fetchall()
        cursor.close()
        return jsonify(filas)
    except Exception as e:
        return jsonify({"error": str(e)}), 500
    finally:
        if conn and conn.is_connected():
            conn.close()

@app.route('/guardar', methods=['POST'])
def guardar_dato():
    conn = None
    try:
        datos = request.json
        nombre = datos.get('nombre', 'Planta')
        valor = datos.get('valor', '')
        conn = conectar()
        cursor = conn.cursor()
        cursor.execute("INSERT INTO registros (nombre, valor) VALUES (%s, %s)", (nombre, valor))
        conn.commit()
        cursor.close()
        return jsonify({"mensaje": "Guardado en registros"})
    except Exception as e:
        return jsonify({"error": str(e)}), 500
    finally:
        if conn and conn.is_connected():
            conn.close()

@app.route('/foco', methods=['GET'])
def obtener_foco():
    conn = None
    try:
        conn = conectar()
        cursor = conn.cursor(dictionary=True)
        cursor.execute("SELECT * FROM registros_foco ORDER BY id DESC LIMIT 50")
        filas = cursor.fetchall()
        cursor.close()
        return jsonify(filas)
    except Exception as e:
        return jsonify({"error": str(e)}), 500
    finally:
        if conn and conn.is_connected():
            conn.close()

@app.route('/estado', methods=['GET'])
def obtener_estado():
    conn = None
    try:
        conn = conectar()
        cursor = conn.cursor(dictionary=True)
        cursor.execute("SELECT * FROM control_remoto WHERE id = 1")
        estado = cursor.fetchone()
        cursor.close()
        return jsonify(estado)
    except Exception as e:
        return jsonify({"error": str(e)}), 500
    finally:
        if conn and conn.is_connected():
            conn.close()

@app.route('/control', methods=['POST'])
def actualizar_control():
    conn = None
    try:
        datos = request.json
        conn = conectar()
        cursor = conn.cursor(dictionary=True)

        campos = []
        valores = []
        for clave in ['modo_auto', 'orden_bomba', 'orden_foco', 'umbral_min', 'umbral_max']:
            if clave in datos:
                campos.append(f"{clave} = %s")
                valores.append(int(datos[clave]))

        if campos:
            sql = f"UPDATE control_remoto SET {', '.join(campos)} WHERE id = 1"
            cursor.execute(sql, tuple(valores))

        if 'orden_bomba' in datos:
            txt_bomba = "Riego manual ACTIVADO desde Web" if int(datos['orden_bomba']) == 1 else "Riego manual DETENIDO desde Web"
            cursor.execute("INSERT INTO registros (nombre, valor) VALUES (%s, %s)", ("Sistema Web", txt_bomba))

        if 'orden_foco' in datos:
            txt_foco = "Foco calor ENCENDIDO" if int(datos['orden_foco']) == 1 else "Foco calor APAGADO"
            cursor.execute("SELECT hum1, hum2 FROM control_remoto WHERE id = 1")
            lec = cursor.fetchone()
            prom = round((lec['hum1'] + lec['hum2']) / 2, 1) if lec else 0
            cursor.execute(
                "INSERT INTO registros_foco (evento, humedad, modo) VALUES (%s, %s, %s)",
                (txt_foco, f"{prom}%", "Manual Web")
            )

        conn.commit()
        cursor.execute("SELECT * FROM control_remoto WHERE id = 1")
        nuevo_estado = cursor.fetchone()
        cursor.close()
        return jsonify(nuevo_estado)
    except Exception as e:
        return jsonify({"error": str(e)}), 500
    finally:
        if conn and conn.is_connected():
            conn.close()

@app.route('/telemetria', methods=['POST'])
def telemetria_pico():
    conn = None
    try:
        datos = request.json
        hum1 = float(datos.get('hum1', 0))
        hum2 = float(datos.get('hum2', 0))
        hum_prom = round((hum1 + hum2) / 2.0, 1)
        bomba_real = 1 if datos.get('bomba') else 0
        foco_real = 1 if datos.get('foco') else 0
        evento_bomba = datos.get('evento_bomba')
        evento_foco = datos.get('evento_foco')
        modo_txt = datos.get('modo', 'Automático')

        conn = conectar()
        cursor = conn.cursor(dictionary=True)

        cursor.execute(
            "UPDATE control_remoto SET hum1=%s, hum2=%s, bomba_real=%s, foco_real=%s WHERE id=1",
            (hum1, hum2, bomba_real, foco_real)
        )

        if datos.get('fin_riego_manual'):
            cursor.execute("UPDATE control_remoto SET orden_bomba = 0 WHERE id = 1")

        if evento_bomba:
            detalle = f"{evento_bomba} · Humedad {hum_prom}% (S1:{int(hum1)}% S2:{int(hum2)}%)"
            cursor.execute("INSERT INTO registros (nombre, valor) VALUES (%s, %s)", ("Pico WH", detalle))

        if evento_foco:
            cursor.execute(
                "INSERT INTO registros_foco (evento, humedad, modo) VALUES (%s, %s, %s)",
                (evento_foco, f"{hum_prom}% (S1:{int(hum1)}% S2:{int(hum2)}%)", modo_txt)
            )

        conn.commit()
        cursor.execute("SELECT modo_auto, orden_bomba, orden_foco, umbral_min, umbral_max FROM control_remoto WHERE id = 1")
        ordenes = cursor.fetchone()
        cursor.close()
        return jsonify(ordenes)
    except Exception as e:
        return jsonify({"error": str(e)}), 500
    finally:
        if conn and conn.is_connected():
            conn.close()

if __name__ == '__main__':
    port = int(os.environ.get("PORT", 5000))
    app.run(host='0.0.0.0', port=port)
