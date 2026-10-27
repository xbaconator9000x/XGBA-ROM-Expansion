# Analyst whole-file candidate 0072 — Weather effect lifecycle callback families

**ANALYST-PREPARED ONLY; independent verdict pending.** Source: [`pret/pokefirered@ce6406d8c2eaf46d543c8a2606de0c3cb1951982/include/field_weather_effects.h`](https://github.com/pret/pokefirered/blob/ce6406d8c2eaf46d543c8a2606de0c3cb1951982/include/field_weather_effects.h); exact pinned Git blob SHA-1 `8ff3bae9ce2e67dd21f3ac58e64fd9f1f39db0d2`. Inspected the **entire 55-line header**; all nonblank, non-comment source lines are enumerated below, including guards, types, enumerators, globals and prototypes. This is not a source-implementation review or approval.

## Whole-file semantic disposition (source-level)

The header declares init-all, init-vars, main and finish entrypoints across ash, bubbles, clouds, fog horizontal/diagonal, rain, thunderstorm, sandstorm, snow, sunny, drought, shade and downpour; families do not all expose identical stages. Unlike most field headers it does not include global.h despite bool8 return types.

## Exhaustive non-comment source-line inventory

- L1: `#ifndef GUARD_FIELD_WEATHER_EFFECTS_H`
- L2: `#define GUARD_FIELD_WEATHER_EFFECTS_H`
- L4: `bool8 Ash_Finish(void);`
- L5: `bool8 Bubbles_Finish(void);`
- L6: `bool8 Clouds_Finish(void);`
- L7: `bool8 FogHorizontal_Finish(void);`
- L8: `bool8 FogDiagonal_Finish(void);`
- L9: `bool8 Rain_Finish(void);`
- L10: `bool8 Thunderstorm_Finish(void);`
- L11: `bool8 Sandstorm_Finish(void);`
- L12: `bool8 Snow_Finish(void);`
- L13: `bool8 Sunny_Finish(void);`
- L14: `bool8 Drought_Finish(void);`
- L15: `bool8 Shade_Finish(void);`
- L16: `void Ash_InitAll(void);`
- L17: `void Ash_InitVars(void);`
- L18: `void Ash_Main(void);`
- L19: `void Bubbles_InitAll(void);`
- L20: `void Bubbles_InitVars(void);`
- L21: `void Bubbles_Main(void);`
- L22: `void Clouds_InitAll(void);`
- L23: `void Clouds_InitVars(void);`
- L24: `void Clouds_Main(void);`
- L25: `void Drought_InitAll(void);`
- L26: `void Drought_InitVars(void);`
- L27: `void Drought_Main(void);`
- L28: `void FogHorizontal_InitAll(void);`
- L29: `void FogHorizontal_InitVars(void);`
- L30: `void FogHorizontal_Main(void);`
- L31: `void FogDiagonal_InitAll(void);`
- L32: `void FogDiagonal_InitVars(void);`
- L33: `void FogDiagonal_Main(void);`
- L34: `void Rain_InitAll(void);`
- L35: `void Rain_InitVars(void);`
- L36: `void Rain_Main(void);`
- L37: `void Thunderstorm_Main(void);`
- L38: `void Sandstorm_InitAll(void);`
- L39: `void Sandstorm_InitVars(void);`
- L40: `void Sandstorm_Main(void);`
- L41: `void Snow_InitAll(void);`
- L42: `void Snow_InitVars(void);`
- L43: `void Shade_InitAll(void);`
- L44: `void Shade_InitVars(void);`
- L45: `void Sunny_InitAll(void);`
- L46: `void Sunny_InitVars(void);`
- L47: `void Sunny_Main(void);`
- L48: `void Shade_Main(void);`
- L49: `void Snow_Main(void);`
- L50: `void Thunderstorm_InitVars(void);`
- L51: `void Thunderstorm_InitAll(void);`
- L52: `void Downpour_InitVars(void);`
- L53: `void Downpour_InitAll(void);`
- L55: `#endif //GUARD_FIELD_WEATHER_EFFECTS_H`

## Dependencies, expansion relevance and independent review

Check translation-unit include order, dispatcher coverage, finish semantics, weather sprite/palette resource lifetime and stage asymmetry; no uniform lifecycle or validated enum range is established here. This declaration-only file does not itself prove caller preconditions, linker/compiled behavior, save persistence, emulator execution or editor round-trip. Validate exact symbol definitions, conditional compilation and consumers against the pinned upstream revision. No independent reviewer has attested this file.

**Disposition: prepared for independent whole-file review; approved 0; authoritative Phase 1 gate FAIL_INCOMPLETE.**
