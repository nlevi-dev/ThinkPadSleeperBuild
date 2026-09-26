#include <Wire.h>

#define POWER_PIN 12
#define PAGE_SIZE 16

#define DEV_ADDR 0x57

void setup() {
    Serial.begin(9600);
    while (!Serial);
    pinMode(POWER_PIN, OUTPUT);
    digitalWrite(POWER_PIN, LOW);
    Wire.begin();
    Serial.println("ready");
}

void loop() {
    if (!Serial.available()) return;
    String line = Serial.readStringUntil('\n');
    line.trim();

    if (line == "POWER_ON") {
        digitalWrite(POWER_PIN, HIGH);
        Serial.println("ok");
    } else if (line == "POWER_OFF") {
        digitalWrite(POWER_PIN, LOW);
        Serial.println("ok");
    } else if (line.startsWith("FLASH ")) {
        int pos = 6;
        // parse address
        int spaceIdx = line.indexOf(' ', pos);
        if (spaceIdx == -1) { Serial.println("error: missing address"); return; }
        String addrStr = line.substring(pos, spaceIdx);
        int romAddr = (int)strtol(addrStr.c_str(), nullptr, 16);
        pos = spaceIdx + 1;

        // parse bytes
        byte buf[PAGE_SIZE];
        int n = 0;
        while (pos + 1 < (int)line.length() && n < PAGE_SIZE) {
            while (pos < (int)line.length() && line[pos] == ' ') pos++;
            if (pos + 2 > (int)line.length()) break;
            char hex[3] = { line[pos], line[pos+1], 0 };
            buf[n++] = (byte)strtol(hex, nullptr, 16);
            pos += 2;
        }
        if (n == 0) { Serial.println("error: no bytes"); return; }

        Wire.beginTransmission(DEV_ADDR);
        Wire.write(romAddr >> 8);
        Wire.write(romAddr & 0xFF);
        for (int i = 0; i < n; i++) Wire.write(buf[i]);
        Wire.endTransmission();
        delay(10);

        Serial.print("ok wrote "); Serial.print(n); Serial.print(" @ 0x"); Serial.println(romAddr, HEX);
    } else if (line.startsWith("DUMP ")) {
        int totalPages = (int)strtol(line.c_str() + 5, nullptr, 10);
        for (int page = 0; page < totalPages; page++) {
            int romAddr = page * PAGE_SIZE;
            Wire.beginTransmission(DEV_ADDR);
            Wire.write(romAddr >> 8);
            Wire.write(romAddr & 0xFF);
            Wire.endTransmission(false);
            Wire.requestFrom(DEV_ADDR, PAGE_SIZE);
            String out = "";
            for (int i = 0; i < PAGE_SIZE && Wire.available(); i++) {
                char hex[4]; sprintf(hex, i ? " %02X" : "%02X", Wire.read());
                out += hex;
            }
            Serial.println(out);
        }
        Serial.println("ok");
    } else {
        Serial.println("error: unknown command");
    }
}
