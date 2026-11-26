from flask import Flask, request, jsonify
from flask_cors import CORS
import mysql.connector

app = Flask(__name__)
CORS(app)

db_config = {
    "host": "mysql-27028d1c-plantitas.l.aivencloud.com",
    "user": "avnadmin",
    "port": "16236",
    "password": "AVNS_i6obPFXEL9WmI8TpD68",
    "database": "plantas_db"
}

def conectar():
    return mysql.connector.connect(**db_config)

# Leer datos para mostrarlos en el HTML
@app.route('/datos', methods=['GET'])
def obtener_datos():
    try:
        conn = conectar()
        cursor = conn.cursor(dictionary=True)
        cursor.execute("SELECT * FROM registros")  # Cambia por el nombre de tu tabla
        filas = cursor.fetchall()
        cursor.close()
        conn.close()
        return jsonify(filas)
    except Exception as e:
        return jsonify({"error": str(e)}), 500

# Guardar datos que lleguen por POST (desde HTML o desde el Pico WH)
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
        return jsonify({"mensaje": "Guardado correctamente"})
    except Exception as e:
        return jsonify({"error": str(e)}), 500

if __name__ == '__main__':
    # host='0.0.0.0' permite que también se conecte tu Raspberry Pi Pico WH por Wi-Fi
    app.run(host='0.0.0.0', port=5000, debug=True)