using UnityEngine;

public class SendCommand : MonoBehaviour
{
    [SerializeField] private MqttUnityClient mqtt;
    [SerializeField] private string tagTopic = "PLCData/MyTag";  // mesmo do tags.yaml

    // Chamado por UI (botão) ou por outro script
    public void SendInt(int value)
    {
        _ = mqtt.PublishCommandAsync(tagTopic, value, "Int32", "unity");
    }

    // Overloads, se precisar
    public void SendFloat(float value) => _ = mqtt.PublishCommandAsync(tagTopic, value, "Float", "unity");
    public void SendBool(bool value) => _ = mqtt.PublishCommandAsync(tagTopic, value, "Boolean", "unity");
    public void SendString(string txt) => _ = mqtt.PublishCommandAsync(tagTopic, txt, "String", "unity");
}
