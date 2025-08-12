using UnityEngine;
using System;
using System.Collections.Concurrent;
using System.Text;
using System.Threading;
using System.Threading.Tasks;
using MQTTnet;
using MQTTnet.Client;
using MQTTnet.Client.Options;

[Serializable]
public struct SensorPayload
{
    public string type;
    public string ts;
    public float value;   // use float; se for int, mude
}

[Serializable]
public struct CommandPayload
{
    public object value;
    public string type;
    public string source;
}

public class MqttUnityClient : MonoBehaviour
{
    [Header("Broker")]
    [SerializeField] private string host = "127.0.0.1";
    [SerializeField] private int port = 1883;
    [SerializeField] private bool useWebSocket = false;

    [Header("Topics")]
    [SerializeField] private string sensorsBase = "planta/sensores/#";
    [SerializeField] private string commandsBase = "planta/comandos/";

    [Header("Debug")]
    [SerializeField] private bool logIncoming = true;
    [SerializeField] private bool logOutgoing = true;

    private readonly ConcurrentQueue<(string topic, string payload)> incomingQueue = new();
    private IMqttClient client;
    private CancellationTokenSource cts;

    public event Action<string, SensorPayload> OnTagValue; // topicTag, payload

    async void Start()
    {
        await ConnectAndSubscribe();
    }

    private async Task ConnectAndSubscribe()
    {
        cts = new CancellationTokenSource();

        var factory = new MqttFactory();
        client = factory.CreateMqttClient();

        client.UseApplicationMessageReceivedHandler(e =>
        {
            var topic = e.ApplicationMessage.Topic;
            var payload = e.ApplicationMessage.Payload == null ? "" : Encoding.UTF8.GetString(e.ApplicationMessage.Payload);
            incomingQueue.Enqueue((topic, payload));
        });

        client.UseDisconnectedHandler(async e =>
        {
            Debug.LogWarning($"MQTT desconectado: {e.Reason}");
            await Task.Delay(TimeSpan.FromSeconds(2), cts.Token);
            try { await client.ReconnectAsync(); } catch { }
        });

        var builder = new MqttClientOptionsBuilder()
            .WithClientId("UnityClient_" + Guid.NewGuid().ToString("N"))
            .WithCleanSession();

        if (useWebSocket)
            builder = builder.WithWebSocketServer($"{host}:{port}/mqtt");
        else
            builder = builder.WithTcpServer(host, port);

        var options = builder.Build();

        await client.ConnectAsync(options, cts.Token);
        Debug.Log("MQTT conectado.");

        await client.SubscribeAsync(sensorsBase);
        Debug.Log($"Subscribed: {sensorsBase}");
    }

    void Update()
    {
        while (incomingQueue.TryDequeue(out var msg))
        {
            if (logIncoming) Debug.Log($"[MQTT IN] {msg.topic} -> {msg.payload}");

            // "planta/sensores/<tagTopic>"
            var parts = msg.topic.Split('/', 3);
            if (parts.Length < 3) continue;
            string tagTopic = parts[2];

            SensorPayload pl;
            try
            {
                pl = JsonUtility.FromJson<SensorPayload>(msg.payload);
            }
            catch (Exception ex)
            {
                Debug.LogError($"JSON parse error [{msg.topic}]: {ex}");
                continue;
            }

            OnTagValue?.Invoke(tagTopic, pl);
        }
    }

    public async Task PublishCommandAsync(string tagTopic, object value, string type = "Int32", string source = "unity")
    {
        var cmd = new CommandPayload { value = value, type = type, source = source };
        string payload = JsonUtility.ToJson(cmd);

        var msg = new MqttApplicationMessageBuilder()
            .WithTopic(commandsBase + tagTopic) // planta/comandos/PLCData/MyTag
            .WithPayload(payload)
            .WithAtMostOnceQoS()
            .WithRetainFlag(false)
            .Build();

        if (logOutgoing) Debug.Log($"[MQTT OUT] {msg.Topic} -> {payload}");
        await client.PublishAsync(msg, cts.Token);
    }

    private async void OnApplicationQuit()
    {
        if (client != null && client.IsConnected)
        {
            try { await client.DisconnectAsync(); } catch { }
        }
        cts?.Cancel();
        cts?.Dispose();
    }
}