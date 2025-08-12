import asyncio
import sys
from loguru import logger
from asyncio_mqtt import Client, MqttError

if sys.platform.startswith("win"):
    asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())

async def test():
    # Envia logs direto pra stdout
    logger.remove()
    logger.add(lambda m: print(m, end=""), level="DEBUG")
    
    try:
        logger.info("Tentando conectar no MQTT em localhost:1883")
        async with Client("localhost", 1883) as client:
            logger.success("✅ Conectou no MQTT!")
    except MqttError as e:
        logger.error(f"❌ Erro MQTT: {e}")

if __name__ == "__main__":
    asyncio.run(test())