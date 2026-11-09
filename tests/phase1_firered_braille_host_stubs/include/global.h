#ifndef PHASE1_BRAILLE_HOST_GLOBAL_H
#define PHASE1_BRAILLE_HOST_GLOBAL_H

#include <stdint.h>

typedef uint8_t u8;
typedef uint16_t u16;
typedef uint32_t u32;
typedef int32_t s32;
typedef int bool8;
typedef int bool32;

#define TRUE 1
#define FALSE 0
#define INCBIN_U16(path) {0}

#define OPTIONS_TEXT_SPEED_SLOW 0
#define OPTIONS_TEXT_SPEED_MID 1
#define OPTIONS_TEXT_SPEED_FAST 2

#define EOS 0xFF
#define CHAR_NEWLINE 0xFE
#define PLACEHOLDER_BEGIN 0xFD
#define EXT_CTRL_CODE_BEGIN 0xFC
#define CHAR_PROMPT_CLEAR 0xFB
#define CHAR_PROMPT_SCROLL 0xFA
#define CHAR_EXTRA_SYMBOL 0xF9
#define CHAR_KEYPAD_ICON 0xF8

#define EXT_CTRL_CODE_COLOR 1
#define EXT_CTRL_CODE_HIGHLIGHT 2
#define EXT_CTRL_CODE_SHADOW 3
#define EXT_CTRL_CODE_COLOR_HIGHLIGHT_SHADOW 4
#define EXT_CTRL_CODE_PALETTE 5
#define EXT_CTRL_CODE_FONT 6
#define EXT_CTRL_CODE_RESET_FONT 7
#define EXT_CTRL_CODE_PAUSE 8
#define EXT_CTRL_CODE_PAUSE_UNTIL_PRESS 9
#define EXT_CTRL_CODE_WAIT_SE 10
#define EXT_CTRL_CODE_PLAY_BGM 11
#define EXT_CTRL_CODE_PLAY_SE 12
#define EXT_CTRL_CODE_ESCAPE 13
#define EXT_CTRL_CODE_SHIFT_RIGHT 14
#define EXT_CTRL_CODE_SHIFT_DOWN 15
#define EXT_CTRL_CODE_FILL_WINDOW 16

#define RENDER_STATE_HANDLE_CHAR 0
#define RENDER_STATE_WAIT 1
#define RENDER_STATE_CLEAR 2
#define RENDER_STATE_SCROLL_START 3
#define RENDER_STATE_SCROLL 4
#define RENDER_STATE_WAIT_SE 5
#define RENDER_STATE_PAUSE 6

#define RENDER_FINISH 10
#define RENDER_UPDATE 11
#define RENDER_REPEAT 12
#define RENDER_PRINT 13

#define A_BUTTON 1
#define B_BUTTON 2
#define JOY_HELD(buttons) 0
#define JOY_NEW(buttons) 0
#define PIXEL_FILL(color) (color)
#define COPYWIN_GFX 1

struct TextPrinterSubStruct
{
    bool32 hasPrintBeenSpedUp;
    u16 glyphId;
    u16 autoScrollDelay;
};

struct TextPrinterTemplate
{
    const u8 *currentChar;
    s32 currentX;
    s32 currentY;
    s32 x;
    s32 y;
    s32 lineSpacing;
    u8 fontId;
    u8 fgColor;
    u8 bgColor;
    u8 shadowColor;
    u8 windowId;
    s32 letterSpacing;
};

struct TextPrinter
{
    u8 state;
    u8 delayCounter;
    u8 textSpeed;
    union
    {
        struct TextPrinterSubStruct sub;
    } subUnion;
    struct TextPrinterTemplate printerTemplate;
    u16 scrollDistance;
};

struct FontInfo
{
    u8 maxLetterHeight;
};

struct TextFlags
{
    bool32 canABSpeedUpPrint;
    bool32 autoScroll;
};

struct SaveBlock2
{
    u16 optionsTextSpeed : 3;
};

struct GlyphInfo
{
    u8 pixels[128];
    u16 width;
    u16 height;
};

extern struct FontInfo gFonts[8];
extern struct TextFlags gTextFlags;
extern struct SaveBlock2 *gSaveBlock2Ptr;
extern struct GlyphInfo gGlyphInfo;

void GenerateFontHalfRowLookupTable(u8 fg, u8 bg, u8 shadow);
void FillWindowPixelBuffer(u8 windowId, u8 fillValue);
void TextPrinterInitDownArrowCounters(struct TextPrinter *textPrinter);
bool8 TextPrinterWait(struct TextPrinter *textPrinter);
bool8 TextPrinterWaitWithDownArrow(struct TextPrinter *textPrinter);
void TextPrinterClearDownArrow(struct TextPrinter *textPrinter);
void ScrollWindow(u8 windowId, u8 direction, u8 distance, u8 fillValue);
void CopyWindowToVram(u8 windowId, u8 mode);
bool8 IsSEPlaying(void);
void DecompressGlyphTile(const u16 *src, u16 *dst);
void CopyGlyphToWindow(struct TextPrinter *textPrinter);

#endif
