// Connector pins (Hirose DF12NB 20-pin):
// pin 7  = VCC5B (5V)
// pin 11 = PAD_RESET (active low)
// pin 13 = PADCLK
// pin 15 = PADDATA
// pin 17 = GND

const uint8_t PAD_DATA  = 3;
const uint8_t PAD_CLK   = 2;
const uint8_t PAD_RESET = 52;

volatile uint16_t bitBuffer = 0;
volatile int bitCount = 0;
volatile unsigned long lastBitTime = 0;

volatile uint8_t ps2Packet[3];
volatile int packetIndex = 0;
volatile bool packetReady = false;

uint8_t safePacket[3];

void writePS2Byte(uint8_t value) {
    pinMode(PAD_CLK, OUTPUT);
    digitalWrite(PAD_CLK, LOW);
    delayMicroseconds(200);

    pinMode(PAD_DATA, OUTPUT);
    digitalWrite(PAD_DATA, LOW); // start bit

    pinMode(PAD_CLK, INPUT_PULLUP);

    uint8_t parity = 1;
    for (int i = 0; i < 8; i++) {
        while (digitalRead(PAD_CLK) == HIGH);
        uint8_t bit = (value >> i) & 0x01;
        if (bit == 0) { pinMode(PAD_DATA, OUTPUT); digitalWrite(PAD_DATA, LOW); }
        else          { pinMode(PAD_DATA, INPUT_PULLUP); }
        parity ^= bit;
        while (digitalRead(PAD_CLK) == LOW);
    }

    // parity
    while (digitalRead(PAD_CLK) == HIGH);
    if (parity == 0) { pinMode(PAD_DATA, OUTPUT); digitalWrite(PAD_DATA, LOW); }
    else             { pinMode(PAD_DATA, INPUT_PULLUP); }
    while (digitalRead(PAD_CLK) == LOW);

    // stop
    while (digitalRead(PAD_CLK) == HIGH);
    pinMode(PAD_DATA, INPUT_PULLUP);
    while (digitalRead(PAD_CLK) == LOW);

    // ACK
    unsigned long t = millis();
    while (digitalRead(PAD_DATA) == HIGH  && millis() - t < 250);
    while (digitalRead(PAD_CLK) == HIGH   && millis() - t < 250);
    while ((digitalRead(PAD_DATA) == LOW || digitalRead(PAD_CLK) == LOW) && millis() - t < 250);
}

void clkISR() {
    unsigned long now = micros();
    if (now - lastBitTime > 3000) { bitCount = 0; bitBuffer = 0; }
    lastBitTime = now;

    bitBuffer |= (digitalRead(PAD_DATA) << bitCount);
    bitCount++;

    if (bitCount >= 11) {
        uint8_t b = (bitBuffer >> 1) & 0xFF;
        bitCount = 0;
        bitBuffer = 0;

        if (packetIndex == 0 && (b & 0x08) == 0) return;
        ps2Packet[packetIndex++] = b;
        if (packetIndex >= 3) { packetReady = true; packetIndex = 0; }
    }
}

void setup() {
    Serial.begin(9600);

    pinMode(PAD_RESET, OUTPUT);
    digitalWrite(PAD_RESET, HIGH);
    pinMode(PAD_CLK,  INPUT_PULLUP);
    pinMode(PAD_DATA, INPUT_PULLUP);

    delay(1000);
    Serial.println("startup");

    digitalWrite(PAD_RESET, LOW);
    delay(10);
    digitalWrite(PAD_RESET, HIGH);
    delay(500);

    attachInterrupt(digitalPinToInterrupt(PAD_CLK), clkISR, FALLING);
    writePS2Byte(0xFF); // reset
    delay(1000);
    writePS2Byte(0xF4); // enable stream
    delay(200);

    noInterrupts(); packetIndex = 0; packetReady = false; interrupts();
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

    if (s & 0x10) x |= 0xFF00;
    if (s & 0x20) y |= 0xFF00;
    y = -y;

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
}
