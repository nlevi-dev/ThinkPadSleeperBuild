#include <Wire.h>

#define PAGE_SIZE 16

static byte page[PAGE_SIZE];
static int  pagePos = 0;
static int  romAddr = 0;

void writePage(int devAddr) {
    Wire.beginTransmission(devAddr);
    Wire.write(romAddr >> 8);
    Wire.write(romAddr & 0xFF);
    for (int i = 0; i < pagePos; i++) Wire.write(page[i]);
    Wire.endTransmission();
    delay(10);
    if (romAddr % 256 == 0) Serial.print(".");
    romAddr += pagePos;
    pagePos = 0;
}

void setup() {
    Serial.begin(9600);
    while (!Serial);
    Wire.begin();

    int found = -1, count = 0;
    for (byte addr = 1; addr < 127; addr++) {
        Wire.beginTransmission(addr);
        if (Wire.endTransmission() == 0) { found = addr; count++; }
    }
    if (count == 0) { Serial.println("error: no I2C devices found"); return; }
    if (count > 1) {
        Serial.print("multiple devices, enter address: ");
        while (!Serial.available());
        String s = Serial.readStringUntil('\n'); s.trim();
        found = (int)strtol(s.c_str(), nullptr, 16);
    }
    Serial.print("device: 0x"); Serial.println(found, HEX);
    Serial.println("send txt (empty line to finish):");

    while (true) {
        while (!Serial.available());
        String line = Serial.readStringUntil('\n');
        line.trim();
        if (line.length() == 0) break;

        int pos = 0;
        while (pos < (int)line.length()) {
            while (pos < (int)line.length() && line[pos] == ' ') pos++;
            if (pos + 2 > (int)line.length()) break;
            char buf[3] = { line[pos], line[pos+1], 0 };
            page[pagePos++] = (byte)strtol(buf, nullptr, 16);
            pos += 2;
            if (pagePos == PAGE_SIZE) writePage(found);
        }
    }

    if (pagePos > 0) writePage(found);

    Serial.println();
    Serial.print("done, wrote "); Serial.print(romAddr); Serial.println(" bytes");
}

void loop() {}
