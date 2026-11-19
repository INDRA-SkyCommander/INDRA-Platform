import pygame
import time

DEADZONE = 0.12

pygame.init()
pygame.joystick.init()

if pygame.joystick.get_count() == 0:
    raise SystemExit("No controller detected. Check USB passthrough and /dev/input permissions.")

js = pygame.joystick.Joystick(0)
js.init()

print(f"Controller: {js.get_name()}")
print(f"Axes: {js.get_numaxes()} | Buttons: {js.get_numbuttons()} | Hats: {js.get_numhats()}")
print("Move one stick / press one button at a time. Ctrl+C to quit.\n")

last_axes = [None] * js.get_numaxes()
last_buttons = [None] * js.get_numbuttons()
last_hats = [None] * js.get_numhats()

try:
    while True:
        pygame.event.pump()

        for i in range(js.get_numaxes()):
            value = js.get_axis(i)
            previous = last_axes[i]
            if abs(value) < DEADZONE:
                value = 0.0
            if previous is None or abs(value - previous) >= 0.08:
                print(f"AXIS   {i}: {value:+.3f}")
                last_axes[i] = value

        for i in range(js.get_numbuttons()):
            value = js.get_button(i)
            if last_buttons[i] is None or value != last_buttons[i]:
                if value:
                    print(f"BUTTON {i}: PRESSED")
                elif last_buttons[i] == 1:
                    print(f"BUTTON {i}: released")
                last_buttons[i] = value

        for i in range(js.get_numhats()):
            value = js.get_hat(i)
            if last_hats[i] is None or value != last_hats[i]:
                print(f"HAT    {i}: {value}")
                last_hats[i] = value

        time.sleep(0.02)
except KeyboardInterrupt:
    print("\nController test stopped.")
finally:
    pygame.quit()
