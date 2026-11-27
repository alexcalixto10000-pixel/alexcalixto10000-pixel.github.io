import os
from flask import Flask, request, jsonify
from flask_cors import CORS
import mysql.connector

app = Flask(__name__)
CORS(app)

def conectar():
    return mysql.connector.connect(
        host=os.environ.get("DB_HOST"),
        port=int(os.environ.get("DB_PORT", 3306)),
        user=os.environ.get("DB_USER"),
        password=os.environ.get("DB_PASSWORD"),
        database=os.environ.get("DB_NAME", "defaultdb"),
        ssl_disabled=False
    )

@app.route('/', methods=['GET'])
def inicio():
    return jsonify({"estado": "API AquaSmart TESOEM 5S2 conectada a Aiven"})

# 1. Leer historial de riego y humedad
@app.route('/datos', methods=['GET'])
def obtener_datos():
    try:
        conn = conectar()
        cursor = conn.cursor(dictionary=True)
        cursor.execute("SELECT * FROM registros ORDER BY id DESC LIMIT 50")
        filas = cursor.fetchall()
        cursor.close()
        conn.close()
        return jsonify(filas)
    except Exception as e:
        return jsonify({"error": str(e)}), 500

# 2. Guardar registro manual en tabla de riego
@app.route('/guardar', methods=['POST'])
def guardar_dato():
    try:
        datos = request.json
        nombre = datos.get('nombre', 'Planta')
        valor = datos.get('valor', '')
        conn = conectar()
        cursor = conn.cursor()
        cursor.execute("INSERT INTO registros (nombre, valor) VALUES (%s, %s)", (nombre, valor))
        conn.commit()
        cursor.close()
        conn.close()
        return jsonify({"mensaje": "Guardado en registros"})
    except Exception as e:
        return jsonify({"error": str(e)}), 500

# 3. Leer historial de la nueva tabla del foco de calor
@app.route('/foco', methods=['GET'])
def obtener_foco():
    try:
        conn = conectar()
        cursor = conn.cursor(dictionary=True)
        cursor.execute("SELECT * FROM registros_foco ORDER BY id DESC LIMIT 50")
        filas = cursor.fetchall()
        cursor.close()
        conn.close()
        return jsonify(filas)
    except Exception as e:
        return jsonify({"error": str(e)}), 500

# 4. Consultar estado de botones y sensores en tiempo real
@app.route('/estado', methods=['GET'])
def obtener_estado():
    try:
        conn = conectar()
        cursor = conn.cursor(dictionary=True)
        cursor.execute("SELECT * FROM control_remoto WHERE id = 1")
        estado = cursor.fetchone()
        cursor.close()
        conn.close()
        return jsonify(estado)
    except Exception as e:
        return jsonify({"error": str(e)}), 500

# 5. Recibir órdenes desde los botones de la página web
@app.route('/control', methods=['POST'])
def actualizar_control():
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

        # Registrar acción manual en su tabla correspondiente
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
        conn.close()
        return jsonify(nuevo_estado)
    except Exception as e:
        return jsonify({"error": str(e)}), 500

# 6. Endpoint único para la Raspberry Pi Pico WH (envía lecturas/eventos y recibe órdenes)
@app.route('/telemetria', methods=['POST'])
def telemetria_pico():
    try:
        datos = request.json
        hum1 = float(datos.get('hum1', 0))
        hum2 = float(datos.get('hum2', 0))
        hum_prom = round((hum1 + hum2) / 2.0, 1)
        bomba_real = 1 if datos.get('bomba') else 0
        foco_real = 1 if datos.get('foco') else 0
        evento_bomba = datos.get('evento_bomba')  # Ej: "Riego iniciado" o "Riego completado"
        evento_foco = datos.get('evento_foco')    # Ej: "Foco encendido" o "Foco apagado"
        modo_txt = datos.get('modo', 'Automático')

        conn = conectar()
        cursor = conn.cursor(dictionary=True)

        # Actualizar lecturas vivas de la Pico WH
        cursor.execute(
            "UPDATE control_remoto SET hum1=%s, hum2=%s, bomba_real=%s, foco_real=%s WHERE id=1",
            (hum1, hum2, bomba_real, foco_real)
        )

        # Si la Pico terminó el ciclo manual al llegar al 60%, apagar la orden remota
        if datos.get('fin_riego_manual'):
            cursor.execute("UPDATE control_remoto SET orden_bomba = 0 WHERE id = 1")

        # Si hubo cambio de estado en la bomba, guardar registro en tabla 'registros'
        if evento_bomba:
            detalle = f"{evento_bomba} · Humedad {hum_prom}% (S1:{int(hum1)}% S2:{int(hum2)}%)"
            cursor.execute("INSERT INTO registros (nombre, valor) VALUES (%s, %s)", ("Pico WH", detalle))

        # Si hubo cambio de estado en el foco, guardar registro en tabla 'registros_foco'
        if evento_foco:
            cursor.execute(
                "INSERT INTO registros_foco (evento, humedad, modo) VALUES (%s, %s, %s)",
                (evento_foco, f"{hum_prom}% (S1:{int(hum1)}% S2:{int(hum2)}%)", modo_txt)
            )

        conn.commit()
        cursor.execute("SELECT modo_auto, orden_bomba, orden_foco, umbral_min, umbral_max FROM control_remoto WHERE id = 1")
        ordenes = cursor.fetchone()
        cursor.close()
        conn.close()
        return jsonify(ordenes)
    except Exception as e:
        return jsonify({"error": str(e)}), 500

if __name__ == '__main__':
    port = int(os.environ.get("PORT", 5000))
    app.run(host='0.0.0.0', port=port)
