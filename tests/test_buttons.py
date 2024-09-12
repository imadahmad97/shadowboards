import RPi.GPIO as GPIO
import time

# Set up GPIO mode
GPIO.setmode(GPIO.BCM)

# Define the GPIO pin numbers where the buttons are connected
red_button_pin = 17
blue_button_pin = 27
green_button_pin = 22

# Set up the button pins as inputs with pull-up resistors
GPIO.setup(red_button_pin, GPIO.IN, pull_up_down=GPIO.PUD_UP)
GPIO.setup(blue_button_pin, GPIO.IN, pull_up_down=GPIO.PUD_UP)
GPIO.setup(green_button_pin, GPIO.IN, pull_up_down=GPIO.PUD_UP)

try:
    while True:
        # Check if the red button is pressed (LOW state)
        if GPIO.input(red_button_pin) == GPIO.LOW:
            print("red button pressed")
            time.sleep(0.2)  # Debounce delay
            
        # Check if the blue button is pressed (LOW state)
        if GPIO.input(blue_button_pin) == GPIO.LOW:
            print("blue button pressed")
            time.sleep(0.2)  # Debounce delay
            
        # Check if the green button is pressed (LOW state)
        if GPIO.input(green_button_pin) == GPIO.LOW:
            print("green button pressed")
            time.sleep(0.2)  # Debounce delay

except KeyboardInterrupt:
    # Clean up GPIO settings when the script is interrupted
    GPIO.cleanup()
