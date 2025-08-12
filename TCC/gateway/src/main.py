import asyncio
import json
import time
import sys
from pathlib import Path
import socket

if sys.platform.startswith("win"):
    asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())

import yaml
from loguru import logger
from tenacity import retry, wait_fixed, stop_after_attempt
from asyncua import Client, ua
from asyncio_mqtt import Client as MqttClient, MqttError

def _resolve_sec_string(raw: str | None) -> str | None:
    if not raw or raw == "None":
        return None
    parts = [p.strip() for p in raw.split(",")]
    if len(parts) < 4:
        raise ValueError(f"SEC inválido: {raw}")
    policy, mode, cert, key = parts[:4]
    cert_p = Path(cert)
    key_p  = Path(key)
    if not cert_p.is_absolute():
        cert_p = (BASE_DIR / cert).resolve()
    if not key_p.is_absolute():
        key_p  = (BASE_DIR / key).resolve()
    if not cert_p.exists():
        logger.error(f"Certificado do cliente não encontrado: {cert_p}")
        raise FileNotFoundError(cert_p)
    if not key_p.exists():
        logger.error(f"Chave do cliente não encontrada: {key_p}")
        raise FileNotFoundError(key_p)
    # mantém qualquer parâmetro extra após os 4 primeiros
    tail = parts[4:]
    return ",".join([policy, mode, str(cert_p), str(key_p), *tail])

# ----------------- Util -----------------
UA_TYPES = {
    "Int32": ua.VariantType.Int32,
    "Float": ua.VariantType.Float,
    "Boolean": ua.VariantType.Boolean,
    "String": ua.VariantType.String,
}
def to_variant(value, vtype_str):
    return ua.Variant(value, UA_TYPES.get(vtype_str, ua.VariantType.String))

def utc_iso():
    return time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())

# ----------------- Config -----------------
BASE_DIR = Path(__file__).resolve().parent
cfg = yaml.safe_load((BASE_DIR / "config.yaml").read_text(encoding="utf-8"))
tags_cfg = yaml.safe_load((BASE_DIR / cfg["tags_map"]).read_text(encoding="utf-8"))

OPC_EP   = cfg["opcua"]["endpoint"]
SEC      = cfg["opcua"]["security"]
USER     = cfg["opcua"]["username"]
PASS     = cfg["opcua"]["password"]
KEEPALIVE= cfg["opcua"]["keepalive_ms"]/1000

MQTT_HOST= cfg["mqtt"]["host"]
MQTT_PORT= cfg["mqtt"]["port"]
MQTT_QOS = cfg["mqtt"]["qos"]
MQTT_RET = cfg["mqtt"]["retain"]
TOP_SENS = cfg["mqtt"]["base_topics"]["sensors"]
TOP_CMD  = cfg["mqtt"]["base_topics"]["commands"]

PUB_MODE = cfg["publish_mode"]
PUB_INT  = cfg["publish_interval_ms"]/1000

# ----------------- Gateway -----------------
class OpcUaMqttGateway:
    def __init__(self):
        self.opc_client: Client | None = None
        self.mqtt: MqttClient | None = None
        self.nodes: dict[str, Node] = {}
        self.sub: Subscription | None = None
        self.running = True

    # ----- MQTT -----
    @retry(wait=wait_fixed(5), stop=stop_after_attempt(100))
    async def connect_mqtt(self):
        logger.debug("-> connect_mqtt() chamado")
        self.mqtt = MqttClient(MQTT_HOST, MQTT_PORT)
        await self.mqtt.connect()
        logger.success("MQTT conectado.")
        await self.mqtt.subscribe(f"{TOP_CMD}/#", qos=MQTT_QOS)

        # subscribe commands
        topic = f"{TOP_CMD}/#"
        await self.mqtt.subscribe((topic, MQTT_QOS))
        logger.info(f"Subscrito em {topic}")

    async def publish_value(self, tag_name: str, value, vtype: str):
        topic = f"{TOP_SENS}/{tags_cfg[tag_name]['topic']}"
        payload = {
            "value": value,
            "type": vtype,
            "ts": utc_iso()
        }
        await self.mqtt.publish(topic, json.dumps(payload), qos=MQTT_QOS, retain=MQTT_RET)

    async def mqtt_listener(self):
        assert self.mqtt is not None
        async with self.mqtt.unfiltered_messages() as messages:
            await self.mqtt.subscribe(f"{TOP_CMD}/#", qos=MQTT_QOS)
            async for msg in messages:
                try:
                    payload = json.loads(msg.payload.decode("utf-8"))
                except Exception as e:
                    logger.error(f"JSON inválido em {msg.topic}: {e}")
                    continue

                # topic = planta/comandos/<topicTag>
                parts = msg.topic.split("/")
                tag_topic = "/".join(parts[2:])
                for tag_name, info in tags_cfg.items():
                    if info["topic"] == tag_topic:
                        try:
                            node = self.nodes[tag_name]
                            await node.write_value(to_variant(payload["value"], info["type"]))
                            logger.info(f"WRITE {tag_name}={payload['value']}")
                        except Exception as ex:
                            logger.exception(f"Erro write {tag_name}: {ex}")
                        break

    # ----- OPC UA -----
    @retry(wait=wait_fixed(5), stop=stop_after_attempt(100))
    async def connect_opc(self):
        logger.debug("-> connect_opc() chamado")
        logger.info(f"OPC UA conectando em {OPC_EP}")
        self.opc_client = Client(OPC_EP)
        self.opc_client.application_uri = f"urn:{socket.gethostname()}:gateway-client"
        try:
            sec = _resolve_sec_string(SEC)
            if sec:
                logger.debug(f"Aplicando security: {sec}")
                await self.opc_client.set_security_string(sec)

            if USER and PASS:
                self.opc_client.set_user(USER)
                self.opc_client.set_password(PASS)

            await self.opc_client.connect()
            logger.success("OPC UA conectado.")
        except Exception as e:
            logger.exception(f"Falha ao conectar OPC UA: {e}")
            raise

    # ----- Loop principal -----
    async def run(self):
        logger.debug("Entrou em run(), iniciando loop principal")
        while self.running:
            try:
                # 1) MQTT primeiro
                await self.connect_mqtt()

                # 2) OPC UA em seguida
                await self.connect_opc()

                # 3) Subscription on_change
                handler = DataChangeHandler(self)
                self.sub = await self.opc_client.create_subscription(100, handler)
                await self.sub.subscribe_data_change(list(self.nodes.values()))
                logger.info("Subscription criada (on_change).")

                # 4) Fica escutando mensagens MQTT (o subscription chama publish_value internamente)
                await self.mqtt_listener()

            except Exception as e:
                logger.error(f"Gateway caiu: {e}")
                # desmonta tudo e tenta de novo
                if self.mqtt:
                    await self.mqtt.disconnect()
                await self.disconnect_opc()
                await asyncio.sleep(5)


    async def cyclic_publisher(self):
        while True:
            for tag_name, info in tags_cfg.items():
                try:
                    val = await self.nodes[tag_name].read_value()
                    await self.publish_value(tag_name, val, info["type"])
                except Exception as e:
                    logger.exception(f"Leitura falhou ({tag_name}): {e}")
                    raise  # força reconectar
            await asyncio.sleep(PUB_INT)

class DataChangeHandler:
    def __init__(self, gw):
        self.gw = gw

    async def datachange_notification(self, node, val, data):
        for tag_name, n in self.gw.nodes.items():
            if n == node:
                await self.gw.publish_value(tag_name, val, tags_cfg[tag_name]["type"])
                break

    async def event_notification(self, event):
        pass

if __name__ == "__main__":
    # 1) Redireciona logs para console também
    logger.remove()  # limpa handlers padrões
    logger.add(sys.stdout, format="{time:HH:mm:ss} | {level} | {message}", level="DEBUG")
    logger.add("gateway.log", rotation="1 MB", retention="7 days", level="DEBUG")

    logger.debug("=== INICIANDO GATEWAY OPC UA ⇆ MQTT ===")
    gw = OpcUaMqttGateway()
    try:
        asyncio.run(gw.run())
    except KeyboardInterrupt:
        logger.info("Encerrando (Ctrl+C)")
    except Exception as e:
        logger.exception(f"Erro fatal no gateway: {e}")