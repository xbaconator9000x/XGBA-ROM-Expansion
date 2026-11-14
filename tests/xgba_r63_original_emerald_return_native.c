/* R63 native source0 return contract in genuine GBA map namespace.
 * Synthetic object data only. Native Emerald ARM build itself is covered
 * by the existing source-gated mGBA CI, not by this host contract test. */
#include "../integration/common/xgba_r63_native_return_path.h"
#include <assert.h>
#include <stdio.h>
int main(void)
{
    assert(XgbaR63IsExpectedNativeReturn(0,0,9));
    assert(!XgbaR63IsExpectedNativeReturn(1,0,9));
    assert(!XgbaR63IsExpectedNativeReturn(2,0,4));
    assert(!XgbaR63IsExpectedNativeReturn(0,9,9));
    assert(XgbaR63VerifyNativeReturnHeader(
          0,0,9,20,20,8,12,14));
    assert(!XgbaR63VerifyNativeReturnHeader(
          0,0,9,20,20,0,12,14));
    assert(!XgbaR63VerifyNativeReturnHeader(
          0,0,9,24,25,8,12,14));
    assert(!XgbaR63VerifyNativeReturnHeader(
          0,0,9,20,20,8,13,14));
    assert(!XgbaR63VerifyNativeReturnHeader(
          1,0,9,20,20,8,12,14));
    assert(!XgbaR63VerifyNativeReturnHeader(
          0,0,10,20,20,8,12,14));
    puts("PASS_R63_RETURN_NATIVE_EMERALD_NO_SOURCE0_SIDECAR_REQUIRED");
    return 0;
}
