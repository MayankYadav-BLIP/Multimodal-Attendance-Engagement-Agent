import time
from modules.audio import AudioMonitor

mon = AudioMonitor()
mon.start()

print("Stay QUIET for the first 2 seconds (calibrating background noise)...")
start = time.time()

while time.time() - start < 20:
    time.sleep(0.5)
    t = time.time() - start
    if not mon.calibrated:
        print(f"{t:4.1f}s  calibrating...")
        continue
    bar = "#" * int(mon.level * 400)
    state = "SPEAKING" if mon.is_speaking else "quiet"
    print(f"{t:4.1f}s  level {mon.level:.4f}  {state:8}  {bar}")

mon.stop()
print(f"\nBackground noise floor: {mon.noise_floor:.4f}")