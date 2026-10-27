# Analyst whole-file candidate 0073 — Weather setter declaration

**ANALYST-PREPARED ONLY; independent verdict pending.** Source: [`pret/pokefirered@ce6406d8c2eaf46d543c8a2606de0c3cb1951982/include/field_weather_util.h`](https://github.com/pret/pokefirered/blob/ce6406d8c2eaf46d543c8a2606de0c3cb1951982/include/field_weather_util.h); exact pinned Git blob SHA-1 `da49d3869a5dda525f8504e8eb8a5d214a874b20`. Inspected the **entire 6-line header**; all nonblank, non-comment source lines are enumerated below, including guards, types, enumerators, globals and prototypes. This is not a source-implementation review or approval.

## Whole-file semantic disposition (source-level)

The header contains only SetWeather(u8 weather) behind an include guard, and does not include global.h; u8 must be available from the including context.

## Exhaustive non-comment source-line inventory

- L1: `#ifndef GUARD_FIELD_WEATHER_UTIL_H`
- L2: `#define GUARD_FIELD_WEATHER_UTIL_H`
- L4: `void SetWeather(u8 weather);`
- L6: `#endif //GUARD_FIELD_WEATHER_UTIL_H`

## Dependencies, expansion relevance and independent review

Trace weather-ID validation, persistence and cross-map transitions, as well as include-order requirements and eventual visual effect dispatch. This declaration-only file does not itself prove caller preconditions, linker/compiled behavior, save persistence, emulator execution or editor round-trip. Validate exact symbol definitions, conditional compilation and consumers against the pinned upstream revision. No independent reviewer has attested this file.

**Disposition: prepared for independent whole-file review; approved 0; authoritative Phase 1 gate FAIL_INCOMPLETE.**
