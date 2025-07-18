  #include <Arduino.h>

  // Quantas conversões fazemos por pino a cada ciclo (sempre 1)
  #define CONVERSIONS_PER_PIN 1

  // Pinos ADC disponíveis
  uint8_t adc_pins[] = {5, 6, 7};
  const uint8_t maxPins = sizeof(adc_pins) / sizeof(adc_pins[0]);

  // Vetor de pinos efetivamente usados e número de canais ativos
  uint8_t selectedPins[maxPins];
  uint8_t channelsToSend = maxPins;  // inicia com todos

  // Flag disparada pela ISR quando uma nova amostra está pronta
  volatile bool adc_conversion_done = false;
  adc_continuous_data_t * result = nullptr;

  // ISR chamada pelo driver ADC
  void IRAM_ATTR adcComplete() {
    adc_conversion_done = true;
  }

  // (Re)configura o ADC para usar apenas os primeiros N canais
  void updateConversion() {
    analogContinuousStop();
    for (uint8_t i = 0; i < channelsToSend; i++) {
      selectedPins[i] = adc_pins[i];
    }
    analogContinuous(
      selectedPins,
      channelsToSend,
      CONVERSIONS_PER_PIN,
      40000,           // sample rate interno (40 kHz / canal)
      &adcComplete
    );
    analogContinuousStart();
  }

  // Lê da Serial se o usuário digitou '1', '2' ou '3'
  void processSerialInput() {
    while (Serial.available()) {  
      char c = Serial.read();
      if (c >= '1' && c <= '0' + maxPins) {
        uint8_t n = c - '0';
        if (n != channelsToSend) {
          channelsToSend = n;
          updateConversion();
        }
      }
    }
  }

  void setup() {
    Serial.begin(115200);
    // Configura ADC de 12 bits e atenuação máxima (0–3.6 V)
    analogContinuousSetWidth(12);
    analogContinuousSetAtten(ADC_11db);

    // Inicializa com todos os canais e já começa a amostrar
    updateConversion();
  }

  void loop() {
    processSerialInput();

    if (adc_conversion_done) {
      adc_conversion_done = false;

      // Lê o bloco de resultados (aqui só há 1 conversão por pino)
      if (analogContinuousRead(&result, 0)) {
        // Imprime imediatamente uma linha com N valores
        for (uint8_t i = 0; i < channelsToSend; i++) {
          Serial.print(result[i].avg_read_raw);
          if (i < channelsToSend - 1) Serial.print('\t');
        }
        Serial.println();
      }
    }
  }