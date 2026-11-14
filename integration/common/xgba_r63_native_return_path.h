/* R63: return to original native Emerald without treating Emerald's
 * already-linked game ROM as a foreign sidecar graphics resource.
 *
 * R54 may use the ordinary native source0 map warp after releasing the
 * previous foreign-world heap objects. R58 may offer this specific target
 * only after checking the ORIGINAL native game MapHeader and events.
 * Does not claim the actual Fly was executed or that guest state is saved.
 */
#ifndef XGBA_R63_NATIVE_RETURN_PATH_H
#define XGBA_R63_NATIVE_RETURN_PATH_H
#include <stdint.h>
#define XGBA_R63_NATIVE_WORLD 0u
#define XGBA_R63_NATIVE_GROUP 0u
#define XGBA_R63_NATIVE_MAP 9u
#define XGBA_R63_NATIVE_WIDTH 20u
#define XGBA_R63_NATIVE_HEIGHT 20u
#define XGBA_R63_NATIVE_LANDING_X 12
#define XGBA_R63_NATIVE_LANDING_Y 14

/* No extra target is implicitly promoted to safe native status. */
static inline int XgbaR63IsExpectedNativeReturn(
    unsigned world,unsigned group,unsigned map)
{
    return world==XGBA_R63_NATIVE_WORLD &&
           group==XGBA_R63_NATIVE_GROUP &&
           map==XGBA_R63_NATIVE_MAP;
}
static inline int XgbaR63VerifyNativeReturnHeader(
    unsigned world,unsigned group,unsigned map,
    unsigned width,unsigned height,unsigned object_count,
    int landing_x,int landing_y)
{
    return XgbaR63IsExpectedNativeReturn(world,group,map) &&
           width==XGBA_R63_NATIVE_WIDTH &&
           height==XGBA_R63_NATIVE_HEIGHT &&
           object_count!=0u &&
           landing_x==XGBA_R63_NATIVE_LANDING_X &&
           landing_y==XGBA_R63_NATIVE_LANDING_Y;
}
#endif
