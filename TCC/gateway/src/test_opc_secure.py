import sys
import asyncio
from asyncua import Client

# No Windows, usar SelectorEventLoopPolicy para suportar add_reader
if sys.platform.startswith("win"):
    asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())

async def test_opc_secure():
    endpoint = "opc.tcp://localhost:1217"
    print(f"Tentando conectar ao OPC UA seguro em {endpoint}")

    # monta o client com endpoint seguro
    client = Client(endpoint)

    # configuração de segurança: policy, mode, cert e chave do cliente
    # certs/gw_cert.pem e certs/gw_key.pem devem estar relativos a este script
    sec_string = "Basic256Sha256,SignAndEncrypt,../certs/gw_cert.pem,../certs/gw_key.pem"
    await client.set_security_string(sec_string)

    try:
        await client.connect()
        print("✅ Conectou ao OPC UA com segurança!")
        await client.disconnect()
    except Exception as e:
        print(f"❌ Falha ao conectar ao OPC UA seguro: {e}")

if __name__ == "__main__":
    asyncio.run(test_opc_secure())
