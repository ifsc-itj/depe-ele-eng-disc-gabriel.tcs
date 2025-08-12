import sys
import asyncio
from asyncua import Client

# No Windows, usamos o SelectorEventLoopPolicy
if sys.platform.startswith("win"):
    asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())

async def test_opc():
    endpoint = "opc.tcp://localhost:1217"  # ajuste se precisar
    print(f"Tentando conectar ao OPC UA em {endpoint}")
    client = Client(endpoint)
    try:
        await client.connect()
        print("✅ Conectou ao OPC UA!")
        await client.disconnect()
    except Exception as e:
        print(f"❌ Falha ao conectar ao OPC UA: {e}")

if __name__ == "__main__":
    asyncio.run(test_opc())