XGBA R11: actual pinned FireRed Pallet Town and real patched mGBA-native execution, same ROM and sidecar in all six trials.
The native emulator samples CLOCK_MONOTONIC around each mCore.runFrame call, including Select live swap input. 120 warmup, 360 steady, 3 select, 360 steady frames/run; no image writing or GIF encoding during timing.
The computed FPS is **UNCAPPED EMULATION PROCESSING** THROUGHPUT, NOT displayed FPS or emulator vsync. CI runner CPU scheduling and caching can affect measurements. Hardware/GUI/Android performance remains unverified.
Source ROM hash, upstream pins, and raw six machine-produced JSON traces recorded in r11-summary.json.
