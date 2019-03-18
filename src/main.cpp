#include <Arduino.h>
#include <LoRa.h>
#include <WiFi.h>
#include <WiFiClient.h>
#include <ArduinoOTA.h>
#include "private.h"

// config:
const char* ssid = P_SSID;
const char* password = P_PASSWORD;
const char* consoleHost = P_CONSOLEIP;
const int csPin = 18;          // LoRa radio chip select
const int resetPin = 14;       // LoRa radio reset
const int irqPin = 26;         // interrupt pin

// globals
WiFiClient http;
WiFiServer wifiServer(80);
int startFrequency = 868000000;
int endFrequency = 869000000;
int stepSize = 1000000;
int powerLevel = 17;
const String initRequest = String("GET /getInit HTTP/1.1\r\nHost: ") + consoleHost + "\r\n\r\n";
const String endRequest  = String("GET /end HTTP/1.1\r\nHost: ") + consoleHost + "\r\n\r\n";
bool masterMode = false;
String lastLoRaMessage("");
int lastRssi = 0;
bool unhandledLoRaMessage = false;
int unhandeldConsoleCommand = 0;
int sweepFrequency = 868000000;
int timeOutTime = 3000;
int nrOfRetries = 3;
int retryCount = 0;
bool waitingForReply = false;
int lastPacketSentTime = 0;
int lastPacketSentFrequency = 0;

void setupOTA() {
  ArduinoOTA.onStart([]() {
    String type;
    if (ArduinoOTA.getCommand() == U_FLASH) {
      type = "sketch";
    } else {
      type = "filesystem";
    }
  });
  ArduinoOTA.begin();
 }

// isr for LoRa receive
void onReceive(int packetSize) {
  if (!unhandledLoRaMessage) {
    lastLoRaMessage = "";
    for (int i = 0; i < packetSize; i++) {
      lastLoRaMessage = lastLoRaMessage + String((char)LoRa.read());
    }
    lastRssi = LoRa.packetRssi();
    unhandledLoRaMessage = true;
    waitingForReply = false;
    retryCount = 0;
  }
}

// report error
void handleError(String e) {
  const String errorRequest = String("GET /error?e=") + e + " HTTP/1.1\r\nHost: " +\
                              consoleHost + "\r\n\r\n";
  http.print(errorRequest);
  Serial.println(e);
}

// init
bool getInit() {
  bool retval = true;
  http.print(initRequest);
  if (http.find("init=[")) {
    startFrequency = (http.readStringUntil(',')).toInt();
    sweepFrequency = startFrequency;
    endFrequency = (http.readStringUntil(',')).toInt();
    stepSize = (http.readStringUntil(',')).toInt();
    powerLevel = (http.readStringUntil(',')).toInt();
    String master = (http.readStringUntil(','));
    String slave = (http.readStringUntil(']'));
    if (startFrequency && endFrequency && stepSize) {
      LoRa.setPins(csPin, resetPin, irqPin);
      if (!LoRa.begin(startFrequency)) {
        handleError("Starting LoRa failed");
        retval = false;
      } else {
        LoRa.setTxPower(powerLevel);
        Serial.println("LoRa active");
        Serial.println("startFrequency (init): " + String(startFrequency));
        Serial.println("sweepFrequency (init): " + String(sweepFrequency));
        Serial.println("endFrequency (init): " + String(endFrequency));
        Serial.println("stepSize (init): " + String(stepSize));
        if (WiFi.localIP().toString() == master) {
          masterMode = true;
          Serial.println("Master mode");
        } else {
          Serial.println("Slave mode");
        }
        LoRa.onReceive(onReceive);
        LoRa.receive();
      }
    } else {
      handleError("Init returned invalid parameters");
      retval = false;
    }
  } else {
    handleError("Init was refused");
    retval = false;
  }
  return retval;
}

// add reading
void addReading() {
  const String addReadingRequest = String("GET /addReading?f=") + sweepFrequency + "&rssi=" + lastRssi + " HTTP/1.1\r\nHost: " +\
                              consoleHost + "\r\n\r\n";
  http.print(addReadingRequest);
  http.find("added");
  http.connect(consoleHost, 5000);
}

void sendSweepPacket(bool hopForWait, bool repeatLast) {
  if (repeatLast) {
    LoRa.setFrequency(lastPacketSentFrequency);
  } else {
    LoRa.setFrequency(sweepFrequency);
  }
  int retryBeginPacket = 0;
  while (!LoRa.beginPacket()) {
    Serial.print(".");
    delay(100);
    retryBeginPacket += 1;
    if (retryBeginPacket > (timeOutTime/100)) {
      handleError("time-out waiting for end of previous transmission");
      return;
    }
  }
  LoRa.print((masterMode ? "mas" : "sla") + String(sweepFrequency));
  LoRa.endPacket();
  Serial.println("sendSweepPacket 3");
  lastPacketSentTime = millis();
  lastPacketSentFrequency = sweepFrequency;
  waitingForReply = true;
  if (repeatLast) {
    Serial.println((masterMode ? " repeat mas" : "repeat sla") + String(lastPacketSentFrequency) + " at " + String(lastPacketSentTime));
  } else {
    Serial.println((masterMode ? " sent mas" : "sent sla") + String(sweepFrequency) + " at " + String(lastPacketSentTime));
  }
  if (hopForWait) {
    sweepFrequency += stepSize;
  }
  LoRa.setFrequency(sweepFrequency);
  LoRa.receive();
}

void setup() {
  pinMode(LED_BUILTIN, OUTPUT);
  Serial.begin(115200);
  delay(10);
  WiFi.begin(ssid, password);
  while (WiFi.status() != WL_CONNECTED) {
    delay(1000);
    Serial.println("Connecting to WiFi..");
  }
  Serial.println("Connected to the WiFi network");
  Serial.print(WiFi.getHostname());
  Serial.print(" with ip address: ");
  Serial.println(WiFi.localIP().toString());
  http.connect(consoleHost, 5000);
  wifiServer.begin();
  unhandeldConsoleCommand = 1;
  setupOTA();
}

void loop() {
  ArduinoOTA.handle();
  if (http.connected()) {
    WiFiClient console = wifiServer.available();
    if (console && console.connected() && console.available() > 0) {
      unhandeldConsoleCommand = console.read();
      Serial.println("received: " + String(unhandeldConsoleCommand));
      console.stop();
    }
    if (unhandeldConsoleCommand == 1) {
      Serial.println("getInit command");
      if (getInit()) {
        digitalWrite(LED_BUILTIN, HIGH);
        unhandeldConsoleCommand = 0;
      }
    }
    if (unhandeldConsoleCommand == 2) {
      Serial.println("sweep command");
      unhandeldConsoleCommand = 0;
      sweepFrequency = startFrequency;
      if (masterMode) {
        Serial.println("start sweep with frequency " + String(sweepFrequency));
        sendSweepPacket(false, false);
      }
    }
    if (unhandledLoRaMessage) {
      Serial.println("received: " + lastLoRaMessage);
      addReading();
      if (masterMode) {
        if (lastLoRaMessage == "sla" + String(sweepFrequency)) {
          sweepFrequency += stepSize;
          if (sweepFrequency < endFrequency) {
            Serial.println("round trip completed, next sweep step with " + String(sweepFrequency));
            sendSweepPacket(false, false);
          } else {
            Serial.println("master done, sending end request");
            http.print(endRequest);
          }
        }
      } else {
        if (lastLoRaMessage == "mas" + String(sweepFrequency)) {
          sendSweepPacket(true, false);
        }
      }
      unhandledLoRaMessage = false;
    }
    if (waitingForReply && (sweepFrequency < endFrequency) && ((millis() - lastPacketSentTime) > timeOutTime) && (retryCount < nrOfRetries)) {
      sendSweepPacket(false, true);
      retryCount += 1;
      if ((retryCount >= nrOfRetries) && !unhandledLoRaMessage) {
        if (masterMode) {
          lastLoRaMessage = "sla" + String(sweepFrequency);
        } else {
          lastLoRaMessage = "mas" + String(sweepFrequency);
        }
        lastRssi = 0;
        unhandledLoRaMessage = true;
        waitingForReply = false;
        retryCount = 0;
      }
    }
  } else {
    delay(500);
    http.connect(consoleHost, 5000);
  }
}
