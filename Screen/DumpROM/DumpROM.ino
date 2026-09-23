#include <Wire.h>

#define EEPROM_SIZE 8192

void setup() {
    Serial.begin(9600);
    while (!Serial);
    Wire.begin();
    Serial.println("ready");

    // Scan
    int found = -1;
    int count = 0;
    for (byte addr = 1; addr < 127; addr++) {
        Wire.beginTransmission(addr);
        if (Wire.endTransmission() == 0) {
            found = addr;
            count++;
        }
    }

    if (count == 0) {
        Serial.println("error: no I2C devices found");
        return;
    }
    if (count > 1) {
        Serial.print("multiple I2C devices found: ");
        for (byte addr = 1; addr < 127; addr++) {
            Wire.beginTransmission(addr);
            if (Wire.endTransmission() == 0) {
                Serial.print("0x"); Serial.print(addr, HEX); Serial.print(" ");
            }
        }
        Serial.println();
        Serial.println("enter address (e.g. 0x50):");
        while (!Serial.available());
        String input = Serial.readStringUntil('\n');
        input.trim();
        found = (int)strtol(input.c_str(), nullptr, 16);
        Serial.print("using 0x"); Serial.println(found, HEX);
    }

    // Dump
    for (int addr = 0; addr < EEPROM_SIZE; addr++) {
        Wire.beginTransmission(found);
        Wire.write(addr >> 8);
        Wire.write(addr & 0xFF);
        Wire.endTransmission();
        Wire.requestFrom(found, 1);

        byte b = Wire.read();
        if (b < 0x10) Serial.print("0");
        Serial.print(b, HEX);
        Serial.print((addr + 1) % 16 == 0 ? "\n" : " ");
    }
}

void loop() {}
