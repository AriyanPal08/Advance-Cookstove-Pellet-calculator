🔌 Hardware Setup Guide: ESP32 Cookstove Dashboard

This document outlines the physical hardware assembly, wiring, and deployment instructions for the Biomass Cookstove Simulator Dashboard built on the ESP32 microcontroller.

1. Bill of Materials (BOM)

To build the physical dashboard, you need the following components:

ESP32 Development Board: The main "brain" running the MicroPython physics engine.

16x2 Character LCD: The display screen for the UI.

I2C LCD Backpack (PCF8574): Usually soldered to the back of the LCD to reduce the number of wires needed from 16 to just 4.

KY-040 Rotary Encoder: The twisting knob used to navigate menus (must include the built-in push-button switch).

Breadboard & Jumper Wires: For prototyping connections.

Micro-USB or USB-C Cable: For power and flashing code via laptop.

2. Wiring Diagram & Pinouts

We are using specific GPIO pins on the ESP32 to utilize hardware interrupts (for instant knob responses) and hardware I2C (for the screen). Follow this exact wiring table.

A. I2C LCD Screen

LCD (I2C Backpack) Pin

ESP32 Pin

Note

GND

GND

Ground

VCC

VIN / 5V

Powers the LCD backlight (3.3V may be too dim)

SDA (Data)

GPIO 21

Standard ESP32 I2C Data line

SCL (Clock)

GPIO 22

Standard ESP32 I2C Clock line

B. KY-040 Rotary Encoder

Encoder Pin

ESP32 Pin

Note

GND

GND

Ground

+ / VCC

3V3

3.3V Logic Power

CLK (Clock)

GPIO 32

Triggers interrupt on twist

DT (Data)

GPIO 33

Determines Left/Right direction

SW (Switch)

GPIO 25

The push-button click

(Note: The ESP32 code uses internal Pin.PULL_UP resistors for the encoder pins, so no external resistors are required).

3. Software Flashing & Deployment

Once the hardware is wired up, you need to load the software.

Install Thonny IDE: Download and install Thonny on your computer.

Flash MicroPython: * Plug in the ESP32.

In Thonny, go to Run -> Configure interpreter.

Select MicroPython (ESP32) and click Install or update MicroPython to flash the base firmware.

Upload the Software Payload:
Use Thonny's file explorer to upload the following 7 files to the root directory of the ESP32 (/):

lcd_api.py

esp8266_i2c_lcd.py

food_db.py

pellet_db.py

utensil_db.py

main_logic.py

main.py (The merged file combining the UI and Physics engine)

⚠️ CRITICAL: The file running the UI loop must be named main.py. The ESP32 is hardcoded to automatically run this specific filename the moment it receives power.

4. Hardware Operation (User Guide)

When you plug the ESP32 into a power bank, it will boot up automatically without a computer.

Twisting the Knob: Scrolls through the menu options (e.g., selecting dishes, increasing pot mass, changing the wind factor).

Clicking the Knob: Pushing down on the dial acts as the "Enter" or "Confirm" button to move to the next screen.

The Physics Run: When you click confirm on the "Est Time" screen, the ESP32 will briefly display "Simulating...". During this time, the microchip is running the 1Hz Discrete Transient Thermodynamics loop.

Restarting: After the final pellet weight is shown, clicking the knob one more time will reset the system back to the beginning.

5. Troubleshooting Common Hardware Issues

Issue: The LCD screen lights up, but there is no text (or only solid white blocks).

Fix: Look at the back of the I2C backpack on the LCD. There is a tiny blue box with a screw (a potentiometer). Use a small screwdriver to twist it left or right to adjust the screen contrast until the text appears.

Issue: The knob is skipping numbers or going backwards.

Fix: The KY-040 encoder pins (CLK and DT) might be swapped. Swap the wires going to GPIO 32 and GPIO 33.

Issue: The screen stays completely blank.

Fix: Double-check that your I2C address is 0x27. Some newer LCD backpacks use 0x3F. (You can scan for I2C devices using Thonny if needed). Ensure VCC is plugged into a 5V source, not 3.3V.