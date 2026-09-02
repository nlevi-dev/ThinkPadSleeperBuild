const uint8_t DRIVE_PINS[] = {42,39,35,31,23,25,29,33,27,41,37,43,45,40,44,46};
const uint8_t SENSE_PINS[] = {26,34,30,28,32,24,36,38};

const uint8_t HOTKEY_PIN     = 22;
const uint8_t HOTKEY_RTN_PIN = 47;

const char* MATRIX[16][8] = {
    {"Back-Tick","1","Q","Tab","A","Esc","Z",nullptr},
    {"F1","2","W","Caps-Lock","S","ISO-102","X",nullptr},
    {"F2","3","E","F3","D","F4","C",nullptr},
    {"5","4","R","T","F","G","V","B"},
    {"6","7","U","Y","J","H","M","N"},
    {"Equal","8","I","Right-Brace","K","F6","Comma",nullptr},
    {"F8","9","O","F7","L",nullptr,"Period",nullptr},
    {"Minus","0","P","Left-Brace","Semi-colon","Quote","ISO-103","Forward-Slash"},
    {"F9","F10",nullptr,"Back-Space","Back-Slash","F5","Enter","Space"},
    {"Insert","F12",nullptr,nullptr,nullptr,nullptr,nullptr,"Arrow-Right"},
    {"Delete","F11","Volume-Up","Volume-Down","Mute","Think-Vantage",nullptr,"Arrow-Down"},
    {"Page-Up","Page-Down","GUI",nullptr,"Menu",nullptr,"Page-Left","Page-Right"},
    {"Home","End",nullptr,nullptr,nullptr,"Arrow-Up","Pause","Arrow-Left"},
    {nullptr,"Print-Screen","Scroll-Lock",nullptr,nullptr,"Alt-L",nullptr,"Alt-R"},
    {nullptr,nullptr,nullptr,"Shift-L",nullptr,nullptr,"Shift-R",nullptr},
    {"Ctrl-L",nullptr,nullptr,nullptr,nullptr,nullptr,"Ctrl-R",nullptr},
};

void setup() {
    Serial.begin(9600);

    for (uint8_t d = 0; d < 16; d++) {
        pinMode(DRIVE_PINS[d], OUTPUT);
        digitalWrite(DRIVE_PINS[d], HIGH);
    }
    for (uint8_t s = 0; s < 8; s++) {
        pinMode(SENSE_PINS[s], INPUT_PULLUP);
    }
    pinMode(HOTKEY_PIN,     INPUT_PULLUP);
    pinMode(HOTKEY_RTN_PIN, OUTPUT);
    digitalWrite(HOTKEY_RTN_PIN, LOW);

    Serial.println("startup");
}

void loop() {
    for (uint8_t d = 0; d < 16; d++) {
        digitalWrite(DRIVE_PINS[d], LOW);
        delayMicroseconds(10);
        for (uint8_t s = 0; s < 8; s++) {
            if (digitalRead(SENSE_PINS[s]) == LOW) {
                if (MATRIX[d][s]) Serial.print(MATRIX[d][s]); else Serial.print("UNKNOWN");
                Serial.print(" D"); Serial.print(d); Serial.print(" S"); Serial.println(s);
                delay(200);
            }
        }
        digitalWrite(DRIVE_PINS[d], HIGH);
    }

    if (digitalRead(HOTKEY_PIN) == LOW) {
        Serial.println("HotKey");
        delay(200);
    }
}
