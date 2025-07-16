#define CONVERSIONS_PER_PIN 1
#define BUFFER_SIZE 500

uint8_t adc_pins[] = {5, 6, 7};
uint8_t adc_pins_count = sizeof(adc_pins) / sizeof(uint8_t);

volatile bool adc_coversion_done = false;
adc_continuous_data_t * result = NULL;

uint16_t raw_buffer[3][BUFFER_SIZE];
uint16_t buffer_index = 0;

void ARDUINO_ISR_ATTR adcComplete() {
  adc_coversion_done = true;
}

void setup() {
    Serial.begin(115200);
    analogContinuousSetWidth(12);
    analogContinuousSetAtten(ADC_11db);
    analogContinuous(adc_pins, adc_pins_count, CONVERSIONS_PER_PIN, 40000, &adcComplete);
    analogContinuousStart();
}

void loop() {
    if (adc_coversion_done == true) {
        adc_coversion_done = false;

        if (analogContinuousRead(&result, 0)) {
            for (int i = 0; i < adc_pins_count; i++) {
                raw_buffer[i][buffer_index] = result[i].avg_read_raw;
            }
            buffer_index++;

            if (buffer_index >= BUFFER_SIZE) {
                // Opcional: parar aquisição enquanto envia/mostra dados
                analogContinuousStop();

                
                for (int i = 0; i < adc_pins_count; i++) {
                    Serial.printf("%d", adc_pins[i]);
                    for (int j = 0; j < BUFFER_SIZE; j++) {
                        Serial.printf("%d", raw_buffer[i][j]);
                        if (j < BUFFER_SIZE - 1)
                            Serial.print("\t");
                    }
Serial.println("---"); // separador de blocos de dados
Serial.println();
                }
                
                buffer_index = 0; // Zera buffer

                delay(500); // Só para facilitar visualização

                // Reinicia aquisição contínua
                analogContinuousStart();
            }
        } else {
            Serial.println("Erro na leitura do ADC.");
        }
    }
}