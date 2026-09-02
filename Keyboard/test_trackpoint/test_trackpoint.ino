const uint8_t TP_DATA  = 2;
const uint8_t TP_CLK   = 3;
const uint8_t TP_RESET = 48;

const uint8_t TP_SENSITIVITY = 0xFF; // default 0x80
const uint8_t TP_SPEED       = 0xFF; // default 0x61

volatile uint16_t bitBuffer = 0;
volatile int bitCount = 0;
volatile bool packetReady = false;
volatile unsigned long lastBitTime = 0;

volatile uint8_t ps2Packet[3];
volatile int packetIndex = 0;

uint8_t safePacket[3]; // copy consumed by loop

void writePS2Byte(uint8_t value) {
    pinMode(TP_CLK, OUTPUT);
    digitalWrite(TP_CLK, LOW);
    delayMicroseconds(200);

    pinMode(TP_DATA, OUTPUT);
    digitalWrite(TP_DATA, LOW); // start bit

    pinMode(TP_CLK, INPUT_PULLUP);

    uint8_t parity = 1;
    for (int i = 0; i < 8; i++) {
        while (digitalRead(TP_CLK) == HIGH);
        uint8_t bit = (value >> i) & 0x01;
        if (bit == 0) { pinMode(TP_DATA, OUTPUT); digitalWrite(TP_DATA, LOW); }
        else          { pinMode(TP_DATA, INPUT_PULLUP); }
        parity ^= bit;
        while (digitalRead(TP_CLK) == LOW);
    }

    // parity
    while (digitalRead(TP_CLK) == HIGH);
    if (parity == 0) { pinMode(TP_DATA, OUTPUT); digitalWrite(TP_DATA, LOW); }
    else             { pinMode(TP_DATA, INPUT_PULLUP); }
    while (digitalRead(TP_CLK) == LOW);

    // stop
    while (digitalRead(TP_CLK) == HIGH);
    pinMode(TP_DATA, INPUT_PULLUP);
    while (digitalRead(TP_CLK) == LOW);

    // ACK handshake with timeout
    unsigned long t = millis();
    while (digitalRead(TP_DATA) == HIGH  && millis() - t < 250);
    while (digitalRead(TP_CLK) == HIGH   && millis() - t < 250);
    while ((digitalRead(TP_DATA) == LOW || digitalRead(TP_CLK) == LOW) && millis() - t < 250);
}

void clkISR() {
    unsigned long now = micros();
    if (now - lastBitTime > 3000) { bitCount = 0; bitBuffer = 0; packetIndex = 0; }
    lastBitTime = now;

    bitBuffer |= (digitalRead(TP_DATA) << bitCount);
    bitCount++;

    if (bitCount >= 11) {
        ps2Packet[packetIndex++] = (bitBuffer >> 1) & 0xFF;
        if (packetIndex >= 3) { packetReady = true; packetIndex = 0; }
        bitCount = 0;
        bitBuffer = 0;
    }
}

void setup() {
    Serial.begin(9600);

    pinMode(TP_RESET, OUTPUT);
    digitalWrite(TP_RESET, LOW);
    pinMode(TP_CLK,  INPUT_PULLUP);
    pinMode(TP_DATA, INPUT_PULLUP);

    delay(1000);
    Serial.println("startup");

    digitalWrite(TP_RESET, HIGH);
    delay(1);
    digitalWrite(TP_RESET, LOW);

    unsigned long start = millis();
    while (millis() - start < 2000) {
        if (digitalRead(TP_CLK) == LOW) { Serial.println("CLK went LOW - TP alive"); break; }
    }
    if (millis() - start >= 2000) { Serial.println("CLK never went LOW - TP not responding"); return; }

    delay(600);
    writePS2Byte(0xFF); // reset
    delay(600);
    writePS2Byte(0xE2); delay(20); // write to RAM
    writePS2Byte(0x81); delay(20);
    writePS2Byte(0x4A); delay(20); // sensitivity
    writePS2Byte(TP_SENSITIVITY); delay(20);
    writePS2Byte(0xE2); delay(20); // write to RAM
    writePS2Byte(0x81); delay(20);
    writePS2Byte(0x60); delay(20); // speed
    writePS2Byte(TP_SPEED); delay(20);
    writePS2Byte(0xF4); // enable stream
    delay(200);

    attachInterrupt(digitalPinToInterrupt(TP_CLK), clkISR, FALLING);
    Serial.println("ready");
}

void loop() {
    if (!packetReady) return;

    noInterrupts();
    safePacket[0] = ps2Packet[0];
    safePacket[1] = ps2Packet[1];
    safePacket[2] = ps2Packet[2];
    packetReady = false;
    interrupts();

    uint8_t s  = safePacket[0];
    int16_t x  = safePacket[1];
    int16_t y  = safePacket[2];

    if ((s & 0x08) == 0 || (s & 0xC0)) return;

    if (s & 0x10) x |= 0xFF00;
    if (s & 0x20) y |= 0xFF00;

    x = constrain(x, -127, 127);
    y = constrain(y, -127, 127);

    bool left   = s & 0x01;
    bool right  = s & 0x02;
    bool middle = s & 0x04;

    if (x || y) {
        Serial.print("x="); Serial.print(x);
        Serial.print(" y="); Serial.println(y);
    }
    if (left)   Serial.println("LEFT");
    if (right)  Serial.println("RIGHT");
    if (middle) Serial.println("MIDDLE");

    noInterrupts(); packetReady = false; interrupts();
}
