from opcua import Server, ua
import time
from pathlib import Path
import signal
import sys
import socket

# ==== Configurações ====
ENDPOINT  = "opc.tcp://localhost:1217"
URI       = "http://ifsc.org/ua"
UPDATE_S  = 1.0  # segundos

# ==== Instancia servidor ====
server = Server()
server.set_endpoint(ENDPOINT)

# ApplicationURI recomendado pelo perfil OPC UA
server.set_application_uri(f"urn:{socket.gethostname()}:opcua-server")

# Determina o diretório base (tcc/opcua-server/)
BASE_DIR = Path(__file__).resolve().parent.parent

# Caminho para os certs
CERT_DIR  = BASE_DIR / "certs"
SERVER_CRT = CERT_DIR / "server_cert.pem"
SERVER_KEY = CERT_DIR / "server_key.pem"

# === Segurança OPC UA ===
server.load_certificate(str(SERVER_CRT))
server.load_private_key(str(SERVER_KEY))
server.set_security_policy([ua.SecurityPolicyType.Basic256Sha256_SignAndEncrypt])

# Namespace e variável
idx      = server.register_namespace(URI)
objects  = server.get_objects_node()
plc_obj  = objects.add_object(idx, "PLCData")
my_var   = plc_obj.add_variable(idx, "MyTag", 0)
my_var.set_writable(True)

def graceful_exit(*_):
    print("\nEncerrando servidor...")
    try:
        server.stop()
    finally:
        sys.exit(0)

signal.signal(signal.SIGINT, graceful_exit)
signal.signal(signal.SIGTERM, graceful_exit)

# Inicia
server.start()
print(f"Servidor OPC UA seguro rodando em {ENDPOINT}")
print(f"ApplicationURI: {server._application_uri}")
print(f"NodeId da variável MyTag: {my_var.nodeid.to_string()}")

try:
    while True:
        valor = int(time.time() % 100)
        my_var.set_value(ua.Variant(valor, ua.VariantType.Int32))
        time.sleep(UPDATE_S)
except KeyboardInterrupt:
    graceful_exit()
finally:
    server.stop()