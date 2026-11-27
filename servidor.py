import os
from flask import Flask, request, jsonify
from flask_cors import CORS
import mysql.connector

app = Flask(__name__)
CORS(app)  # Permite conexiones desde GitHub Pages y otros dispositivos

def conectar():
    return mysql.connector.connect(
        host="mysql-27028d1c-plantitas.l.aivencloud.com",  # <-- 1. Pega aquí el Host de Aiven
        port=16236,                                    # <-- 2. Pon aquí el Port de Aiven (sin comillas)
        user="avnadmin",                               # <-- 3. El User de Aiven
        password="AVNS_i6obPFXEL9WmI8TpD68",             # <-- 4. Pega aquí el Password de Aiven
        database="plantas_db",                          # <-- 5. El Database name de Aiven
        ssl_disabled=False                             # <-- Déjalo en False (Aiven exige SSL)
    )

# Ruta principal para comprobar que el servidor está vivo
@app.route('/', methods=['GET'])
def inicio():
    return jsonify({"estado": "Servidor puente conectado a Aiven funcionando"})

# RUTA 1: Leer registros de Aiven y mandarlos al HTML
@app.route('/datos', methods=['GET'])
def obtener_datos():
    try:
        conn = conectar()
        cursor = conn.cursor(dictionary=True)
        cursor.execute("SELECT * FROM registros")
        filas = cursor.fetchall()
        cursor.close()
        conn.close()
        return jsonify(filas)
    except Exception as e:
        return jsonify({"error": str(e)}), 500

# RUTA 2: Guardar nuevos registros desde el HTML (o desde tu Pico WH)
@app.route('/guardar', methods=['POST'])
def guardar_dato():
    try:
        datos = request.json
        nombre = datos.get('nombre')
        valor = datos.get('valor')

        conn = conectar()
        cursor = conn.cursor()
        sql = "INSERT INTO registros (nombre, valor) VALUES (%s, %s)"
        cursor.execute(sql, (nombre, valor))
        conn.commit()
        cursor.close()
        conn.close()
        return jsonify({"mensaje": "Guardado correctamente en Aiven"})
    except Exception as e:
        return jsonify({"error": str(e)}), 500

if __name__ == '__main__':
    # Usa el puerto dinámico que asigna Render automáticamente
    port = int(os.environ.get("PORT", 5000))
    app.run(host='0.0.0.0', port=port)
