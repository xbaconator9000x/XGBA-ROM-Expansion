#include <assert.h>
#include <stdio.h>
#include <string.h>

#include "global.h"

#ifndef BRAILLE_SOURCE_PATH
#error BRAILLE_SOURCE_PATH must name the pinned production source
#endif

#include BRAILLE_SOURCE_PATH

struct FontInfo gFonts[8];
struct TextFlags gTextFlags;
static struct SaveBlock2 sSaveBlock2;
struct SaveBlock2 *gSaveBlock2Ptr = &sSaveBlock2;
struct GlyphInfo gGlyphInfo;
static u8 sLastScrollDistance;
static u32 sScrollCalls;

void GenerateFontHalfRowLookupTable(u8 fg, u8 bg, u8 shadow)
{
    (void)fg;
    (void)bg;
    (void)shadow;
}

void FillWindowPixelBuffer(u8 windowId, u8 fillValue)
{
    (void)windowId;
    (void)fillValue;
}

void TextPrinterInitDownArrowCounters(struct TextPrinter *textPrinter)
{
    (void)textPrinter;
}

bool8 TextPrinterWait(struct TextPrinter *textPrinter)
{
    (void)textPrinter;
    return FALSE;
}

bool8 TextPrinterWaitWithDownArrow(struct TextPrinter *textPrinter)
{
    (void)textPrinter;
    return FALSE;
}

void TextPrinterClearDownArrow(struct TextPrinter *textPrinter)
{
    (void)textPrinter;
}

void ScrollWindow(u8 windowId, u8 direction, u8 distance, u8 fillValue)
{
    (void)windowId;
    (void)direction;
    (void)fillValue;
    sLastScrollDistance = distance;
    sScrollCalls++;
}

void CopyWindowToVram(u8 windowId, u8 mode)
{
    (void)windowId;
    (void)mode;
}

bool8 IsSEPlaying(void)
{
    return FALSE;
}

void DecompressGlyphTile(const u16 *src, u16 *dst)
{
    (void)src;
    (void)dst;
}

void CopyGlyphToWindow(struct TextPrinter *textPrinter)
{
    (void)textPrinter;
}

static void InitScrollPrinter(struct TextPrinter *textPrinter, u16 distance)
{
    memset(textPrinter, 0, sizeof(*textPrinter));
    textPrinter->state = RENDER_STATE_SCROLL;
    textPrinter->scrollDistance = distance;
    sScrollCalls = 0;
}

int main(int argc, char **argv)
{
    static const u8 expectedDistances[] = {1, 2, 4};
    struct TextPrinter textPrinter;
    u8 speed;

    if (argc != 2)
        return 2;

    if (strcmp(argv[1], "valid") == 0)
    {
        for (speed = OPTIONS_TEXT_SPEED_SLOW; speed <= OPTIONS_TEXT_SPEED_FAST; speed++)
        {
            InitScrollPrinter(&textPrinter, 10);
            gSaveBlock2Ptr->optionsTextSpeed = speed;
            FontFunc_Braille(&textPrinter);
            assert(sScrollCalls == 1);
            assert(sLastScrollDistance == expectedDistances[speed]);
            assert(textPrinter.scrollDistance == 10 - expectedDistances[speed]);
        }

        InitScrollPrinter(&textPrinter, 1);
        gSaveBlock2Ptr->optionsTextSpeed = OPTIONS_TEXT_SPEED_FAST;
        FontFunc_Braille(&textPrinter);
        assert(sLastScrollDistance == 1);
        assert(textPrinter.scrollDistance == 0);
        puts("PASS valid speed scroll controls");
        return 0;
    }

    if (strcmp(argv[1], "speed-three") == 0)
    {
        InitScrollPrinter(&textPrinter, 10);
        gSaveBlock2Ptr->optionsTextSpeed = 3;
        puts("RUN injected invalid-speed control");
        fflush(stdout);
        FontFunc_Braille(&textPrinter);
        assert(sScrollCalls == 1);
        assert(sLastScrollDistance == 2);
        assert(textPrinter.scrollDistance == 8);
        puts("PASS fixed-index mutation control");
        return 0;
    }

    return 2;
}
