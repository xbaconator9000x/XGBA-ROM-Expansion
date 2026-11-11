XGBA R10: ACTUAL FIRE RED PALLET TOWN OVERWORLD
All source game graphics, native map engine, player and NPC objects from the actual pinned FireRed engine.
The new 64x64 overlay object uses FireRed CreateSprite and LoadSpriteSheet. Crystal and Magma bytes are ONLY in a post-32MiB sidecar.
SELECT sends a real mGBA GBA controller input; the running game issues another XGBA MMIO request and replaces the existing sprite VRAM tiles WITHOUT RESETTING THE ROM.
PNG frames are direct native mGBA software LCD renderer output. The animated GIF is assembled only from those frames. No mock screen or AI-generated pixel data.
LIMITATION: source-instrumented real FireRed with custom overlay; not yet a normal ROM-hacking editor resource API.
