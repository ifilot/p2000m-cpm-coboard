// ====================================================================
// 82S123 ROM Reader - Arduino Leonardo
// --------------------------------------------------------------------
// Wiring summary:
//   ROM A0-A4  -> D2, D3, D4, D5, D6
//   ROM /CE    -> D7
//   ROM D0-D3  -> A3-A0 (PF4-PF7)
//   ROM D4-D7  -> D8-D11 (PB4-PB7)
// --------------------------------------------------------------------
// Serial command protocol (115200 baud, 8N1, newline-terminated ASCII
// commands). This firmware is driven by a host application (e.g. the
// companion Qt6 GUI) instead of auto-dumping on boot, so reads always
// happen on request and can be verified by the host.
//
//   PING   -> "PONG 82S123-READER v0.1.0"
//   READ   -> 32 lines "AA:DD" (address:data, hex), then "CHK:xx"
//             (XOR checksum of all 32 data bytes), then "OK"
//   other  -> "ERR UNKNOWN_CMD <cmd>"
// ====================================================================

const int ADDR_PINS[5] = {2, 3, 4, 5, 6};
const int CE_PIN = 7;
const int DATA_LOW_PINS[4] = {A3, A2, A1, A0};  // D0-D3
const int DATA_HIGH_PINS[4] = {8, 9, 10, 11};   // D4-D7

const char *FIRMWARE_ID = "82S123-READER";
const char *FIRMWARE_VERSION = "v0.1.1";

const uint8_t MAX_LINE_LENGTH = 64;
String inputLine;

void print_hex2(uint8_t v) {
  if (v < 16) Serial.print('0');
  Serial.print(v, HEX);
}

uint8_t read_byte(uint8_t addr) {
  // Output address bits
  for (int bit = 0; bit < 5; bit++) {
    digitalWrite(ADDR_PINS[bit], (addr >> bit) & 1);
  }

  // Enable chip
  digitalWrite(CE_PIN, LOW);
  delayMicroseconds(5); // allow ROM outputs to settle

  // Read data bits
  uint8_t value = 0;
  for (int bit = 0; bit < 4; bit++) {
    value |= (digitalRead(DATA_LOW_PINS[bit]) << bit);
    value |= (digitalRead(DATA_HIGH_PINS[bit]) << (bit + 4));
  }

  // Disable chip
  digitalWrite(CE_PIN, HIGH);

  return value;
}

void cmd_ping() {
  Serial.print(F("PONG "));
  Serial.print(FIRMWARE_ID);
  Serial.print(' ');
  Serial.println(FIRMWARE_VERSION);
}

void cmd_read() {
  uint8_t checksum = 0;

  for (uint16_t addr = 0; addr < 32; addr++) {
    uint8_t value = read_byte((uint8_t)addr);
    checksum ^= value;

    print_hex2((uint8_t)addr);
    Serial.print(':');
    print_hex2(value);
    Serial.print('\n');
  }

  Serial.print(F("CHK:"));
  print_hex2(checksum);
  Serial.print('\n');
  Serial.println(F("OK"));
}

void handle_command(String cmd) {
  cmd.trim();
  cmd.toUpperCase();
  if (cmd.length() == 0) return;

  if (cmd == "PING") {
    cmd_ping();
  } else if (cmd == "READ") {
    cmd_read();
  } else {
    Serial.print(F("ERR UNKNOWN_CMD "));
    Serial.println(cmd);
  }
}

void setup() {
  Serial.begin(115200);
  // Deliberately not "while (!Serial);" here: that gate waits for the host
  // to assert DTR, which the Arduino Serial Monitor and avrdude do
  // automatically but generic serial libraries (e.g. Qt's QSerialPort, as
  // used by the companion GUI) do not do by default. Native-USB boards like
  // the Leonardo can transmit/receive over CDC as soon as they're
  // enumerated regardless of that flag, so skipping the wait keeps the
  // board responsive to any host without relying on DTR behavior.

  // A0-A3 double as the ATmega32U4's on-chip JTAG interface (TDI/TDO/TMS/TCK
  // on PF7-PF4). If the JTAGEN fuse is left programmed, JTAG claims those
  // four pins at every reset until software disables it, which can prevent
  // ordinary GPIO functions -- including pinMode(..., INPUT_PULLUP) below --
  // from reaching the physical pin (A0/TDI is affected; TCK/TMS/TDO get an
  // automatic JTAG-internal pull-up so they read fine regardless). This
  // project never uses JTAG, so disable it unconditionally; per the
  // datasheet, disabling requires writing JTD twice within four cycles.
  noInterrupts();
  MCUCR |= (1 << JTD);
  MCUCR |= (1 << JTD);
  interrupts();

  // Address + CE as outputs
  for (int i = 0; i < 5; i++) {
    pinMode(ADDR_PINS[i], OUTPUT);
    digitalWrite(ADDR_PINS[i], LOW);
  }
  pinMode(CE_PIN, OUTPUT);
  digitalWrite(CE_PIN, HIGH); // /CE inactive

  // Data as inputs
  for (int i = 0; i < 4; i++) {
    pinMode(DATA_LOW_PINS[i], INPUT_PULLUP);
    pinMode(DATA_HIGH_PINS[i], INPUT_PULLUP);
  }

  inputLine.reserve(MAX_LINE_LENGTH);
}

void loop() {
  while (Serial.available() > 0) {
    char c = (char)Serial.read();

    if (c == '\n' || c == '\r') {
      if (inputLine.length() > 0) {
        handle_command(inputLine);
        inputLine = "";
      }
    } else {
      inputLine += c;
      // Guard against a runaway/garbled line filling up memory.
      if (inputLine.length() >= MAX_LINE_LENGTH) {
        inputLine = "";
      }
    }
  }
}
