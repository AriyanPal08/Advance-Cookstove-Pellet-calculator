from machine import I2C, Pin, PWM
from time import sleep_ms

# ============================================================================
# HARDWARE
# ============================================================================
i2c = I2C(0, scl=Pin(22), sda=Pin(21), freq=400000)

encoder_clk = Pin(32, Pin.IN, Pin.PULL_UP)
encoder_dt  = Pin(33, Pin.IN, Pin.PULL_UP)
encoder_sw  = Pin(25, Pin.IN, Pin.PULL_UP)

led = Pin(26, Pin.OUT)
buzzer = PWM(Pin(27), freq=1000, duty=0)

# ============================================================================
# IMPROVED & RELIABLE LCD1602 DRIVER
# ============================================================================
class LCD1602:
    def __init__(self, i2c, addr=0x27):
        self.i2c = i2c
        self.addr = addr
        self.backlight = 0x08
        self._init_display()

    def _write(self, data, rs=0):
        """Send command or data to LCD"""
        try:
            high = (data & 0xF0) | rs | self.backlight
            low  = ((data << 4) & 0xF0) | rs | self.backlight

            # High nibble
            self.i2c.writeto(self.addr, bytes([high | 0x04]))
            sleep_ms(1)
            self.i2c.writeto(self.addr, bytes([high]))
            sleep_ms(1)

            # Low nibble
            self.i2c.writeto(self.addr, bytes([low | 0x04]))
            sleep_ms(1)
            self.i2c.writeto(self.addr, bytes([low]))
            sleep_ms(1)
        except Exception as e:
            print("LCD Error:", e)

    def _init_display(self):
        try:
            # Standard 4-bit initialization
            sleep_ms(50)
            self._write(0x30)
            sleep_ms(5)
            self._write(0x30)
            sleep_ms(5)
            self._write(0x30)
            sleep_ms(5)
            self._write(0x20)   # Set to 4-bit mode
            sleep_ms(5)

            self._write(0x28)   # 2 lines, 5x8 font
            self._write(0x0C)   # Display ON, Cursor OFF
            self._write(0x06)   # Increment cursor
            self._write(0x01)   # Clear display
            sleep_ms(5)
            print(f"LCD initialized successfully at {hex(self.addr)}")
        except Exception as e:
            print("LCD Init Failed:", e)

    def clear(self):
        self._write(0x01)
        sleep_ms(2)

    def write(self, text, row=0):
        addr = 0x80 if row == 0 else 0xC0
        self._write(addr)
        for char in str(text)[:16]:
            self._write(ord(char), rs=1)   # rs=1 for data

    def display(self, line1, line2=""):
        self.clear()
        self.write(line1[:16], 0)
        if line2:
            self.write(line2[:16], 1)

# Try both common I2C addresses
lcd = None
for addr in [0x27, 0x3F]:
    try:
        lcd = LCD1602(i2c, addr=addr)
        if lcd:
            break
    except:
        continue

if lcd is None:
    print("LCD not detected! Check wiring.")

# ============================================================================
# ROTARY ENCODER (Same improved version)
# ============================================================================
class RotaryEncoder:
    def __init__(self, clk, dt, sw):
        self.clk = clk
        self.dt = dt
        self.sw = sw
        self.counter = 0
        self.last_clk = clk.value()
        self.button_pressed = False

    def update(self):
        clk = self.clk.value()
        if clk != self.last_clk:
            if self.dt.value() != clk:
                self.counter += 1
            else:
                self.counter -= 1
            self.last_clk = clk

        if self.sw.value() == 0:
            if not self.button_pressed:
                self.button_pressed = True
                return "PRESS"
        else:
            self.button_pressed = False
        return None

    def get_count(self):
        return self.counter % 100

    def reset(self):
        self.counter = 0

encoder = RotaryEncoder(encoder_clk, encoder_dt, encoder_sw)

# ============================================================================
# DATABASES & FUNCTIONS
# ============================================================================
FOOD_DB = {
    "Rice": {"mass": 0.12, "water": 0.30},
    "Dal": {"mass": 0.08, "water": 0.24},
    "Vegetables": {"mass": 0.20, "water": 0.35},
}

PELLET_DB = ["Softwood", "Hardwood", "Rice Husk", "Bagasse"]
UTENSIL_DB = ["Al Pot 5L", "Kadhai", "Pressure Cooker"]

def calculate(dish_name, pellet_name, utensil_name, lid_on=True):
    food = FOOD_DB.get(dish_name, FOOD_DB["Rice"])
    m_water = food["water"]
    time_min = 12 + (m_water * 12)
    pellets_g = 75 + (m_water * 45)
    return time_min, pellets_g, "OK"

def menu_select(title, options):
    encoder.reset()
    selected = 0
    while True:
        if lcd:
            lcd.display(title, options[selected])
        action = encoder.update()
        selected = encoder.get_count() % len(options)
        if action == "PRESS":
            return selected
        sleep_ms(60)

def main_app():
    while True:
        dish_idx = menu_select("SELECT DISH", list(FOOD_DB.keys()))
        dish_name = list(FOOD_DB.keys())[dish_idx]

        pellet_idx = menu_select("SELECT PELLET", PELLET_DB)
        pellet_name = PELLET_DB[pellet_idx]

        utensil_idx = menu_select("SELECT POT", UTENSIL_DB)
        utensil_name = UTENSIL_DB[utensil_idx]

        lid_idx = menu_select("LID STATE", ["Lid ON", "Lid OFF"])
        lid_on = (lid_idx == 0)

        if lcd:
            lcd.display("Calculating...", "")
        sleep_ms(400)

        time_min, pellets_g, status = calculate(dish_name, pellet_name, utensil_name, lid_on)

        if lcd:
            lcd.display(f"T:{time_min:.0f}m P:{pellets_g:.0f}g", status)
        else:
            print(f"Time: {time_min} min | Pellets: {pellets_g} g")

        while True:
            if encoder.update() == "PRESS":
                break
            sleep_ms(80)

# ============================================================================
# STARTUP
# ============================================================================
if __name__ == "__main__":
    print("Pellet Calculator Started")
    
    if lcd:
        lcd.display("PELLET CALC", "Press to Start")
    else:
        print("LCD not working. Check address/wiring.")

    while True:
        if encoder.update() == "PRESS":
            break
        sleep_ms(50)

    main_app()