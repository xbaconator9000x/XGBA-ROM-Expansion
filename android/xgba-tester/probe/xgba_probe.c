/* R43: ALL-ORIGINAL homebrew guest cartridge for hands-on XGBA MMIO.
 * No Nintendo ROM, graphics, script, copy of a commercial save, or BIOS.
 * Runs on native ARM7TDMI GBA CPU; drawn pixels reflect actual sidecar reads.
 * In particular a *stock* emulator displays "NEED XGBA", and MUST NOT fake
 * successful external resources.
 */
#include <stdint.h>

#define MMIO ((volatile uint32_t *)0x04FF8000u)
#define VRAM ((volatile uint16_t *)0x06000000u)
#define REG_DISPCNT (*(volatile uint16_t *)0x04000000u)
#define REG_VCOUNT (*(volatile uint16_t *)0x04000006u)
#define REG_KEYINPUT (*(volatile uint16_t *)0x04000130u)
#define COLOR(r,g,b) ((uint16_t)(((r)&31u)|(((g)&31u)<<5)|(((b)&31u)<<10)))
#define WIDTH 240u
#define HEIGHT 160u
#define ID_AREA ((volatile uint8_t *)0x0203F800u)
#define DATA_AREA ((volatile uint8_t *)0x0203F000u)
#define DATA_BYTES 64u
#define PROBE ((volatile uint32_t *)0x0203F900u)

static const uint8_t glyphs[40][5]={
/* A-Z 5x7 column bitmaps */
{0x7E,0x11,0x11,0x11,0x7E},{0x7F,0x49,0x49,0x49,0x36},
{0x3E,0x41,0x41,0x41,0x22},{0x7F,0x41,0x41,0x22,0x1C},
{0x7F,0x49,0x49,0x49,0x41},{0x7F,0x09,0x09,0x09,0x01},
{0x3E,0x41,0x49,0x49,0x7A},{0x7F,0x08,0x08,0x08,0x7F},
{0x41,0x41,0x7F,0x41,0x41},{0x20,0x40,0x41,0x3F,0x01},
{0x7F,0x08,0x14,0x22,0x41},{0x7F,0x40,0x40,0x40,0x40},
{0x7F,0x02,0x0C,0x02,0x7F},{0x7F,0x04,0x08,0x10,0x7F},
{0x3E,0x41,0x41,0x41,0x3E},{0x7F,0x09,0x09,0x09,0x06},
{0x3E,0x41,0x51,0x21,0x5E},{0x7F,0x09,0x19,0x29,0x46},
{0x46,0x49,0x49,0x49,0x31},{0x01,0x01,0x7F,0x01,0x01},
{0x3F,0x40,0x40,0x40,0x3F},{0x1F,0x20,0x40,0x20,0x1F},
{0x3F,0x40,0x38,0x40,0x3F},{0x63,0x14,0x08,0x14,0x63},
{0x03,0x04,0x78,0x04,0x03},{0x61,0x51,0x49,0x45,0x43},
/* 0-9 */
{0x3E,0x45,0x49,0x51,0x3E},{0x00,0x21,0x7F,0x01,0x00},
{0x23,0x45,0x49,0x51,0x21},{0x42,0x41,0x51,0x69,0x46},
{0x0C,0x14,0x24,0x7F,0x04},{0x72,0x51,0x51,0x51,0x4E},
{0x1E,0x29,0x49,0x49,0x06},{0x40,0x47,0x48,0x50,0x60},
{0x36,0x49,0x49,0x49,0x36},{0x30,0x49,0x49,0x4A,0x3C},
/* punctuation: space, colon, dash, exclamation */
{0,0,0,0,0},{0,0x36,0x36,0,0},
{0x08,0x08,0x08,0x08,0x08},{0,0,0x5F,0,0}
};

static unsigned glyph_idx(char c){
    if(c>='A'&&c<='Z')return (unsigned)(c-'A');
    if(c>='0'&&c<='9')return 26u+(unsigned)(c-'0');
    if(c==':')return 37u;
    if(c=='-')return 38u;
    if(c=='!')return 39u;
    return 36u;
}
static void box(int x,int y,int w,int h,uint16_t color){
    for(int yy=y;yy<y+h;yy++)
        for(int xx=x;xx<x+w;xx++)
            if((unsigned)xx<WIDTH&&(unsigned)yy<HEIGHT)
                VRAM[(unsigned)yy*WIDTH+(unsigned)xx]=color;
}
static void label(int x,int y,const char *s,uint16_t color){
    for(int i=0;s[i]&&i<37;i++){
        unsigned gi=glyph_idx(s[i]);
        for(int col=0;col<5;col++)
            for(int row=0;row<7;row++)
                if(glyphs[gi][col]&(1u<<row))
                    box(x+i*6+col,y+row,1,1,color);
    }
}
static void number(int x,int y,unsigned n,uint16_t color){
    char digits[12];
    int i=0;
    do{digits[i++]=(char)('0'+n%10u);n/=10u;}while(n&&i<11);
    for(int j=0;j<i;j++){
        char temp[2]={digits[i-1-j],0};
        label(x+j*7,y,temp,color);
    }
}
static void strcopy(volatile uint8_t *dest,const char *s){
    unsigned i=0;
    while(s[i]&&i<127u){dest[i]=(uint8_t)s[i];i++;}
    dest[i]=0;
}
static int external_fetch(const char *id,volatile uint8_t *dest){
    strcopy(ID_AREA,id);
    if(MMIO[0]!=0x58474241u || MMIO[1]!=1u)return 0;
    MMIO[2]=(uint32_t)ID_AREA;MMIO[3]=(uint32_t)dest;
    MMIO[4]=DATA_BYTES;MMIO[5]=1u;
    return MMIO[6]==1u && MMIO[7]==DATA_BYTES;
}
static void render(int world,int available,unsigned fetches,unsigned events){
    const uint16_t back=COLOR(2,4,10);
    const uint16_t foreground=COLOR(30,30,30);
    box(0,0,240,160,back);
    box(4,4,232,30,COLOR(3,8,16));
    label(17,12,"XGBA REAL STORAGE",COLOR(28,30,10));
    box(7,38,226,64,world==0?COLOR(3,12,7):
                           world==1?COLOR(12,4,7):COLOR(5,8,17));
    label(16,45,world==0?"EMERALD SOURCE":
                 world==1?"ROCKET SOURCE":"JOHTO SOURCE",foreground);
    if(available) {
        label(16,62,"EXPANDED DATA OK!",COLOR(17,31,17));
        label(16,78,(const char *)(DATA_AREA+world*128u),foreground);
    }else{
        label(16,62,"NEED PATCHED XGBA",COLOR(31,12,12));
        label(16,78,"STOCK EMULATOR FAILS",foreground);
    }
    label(12,111,"L R: SWITCH SOURCE",COLOR(20,25,30));
    label(12,124,"A: INTERACT",COLOR(20,25,30));
    label(12,138,"FETCH:",COLOR(29,22,8));
    number(59,138,fetches,foreground);
    label(120,138,"EVENTS:",COLOR(29,22,8));
    number(181,138,events,foreground);
}
void _start(void) __attribute__((naked,section(".text.start")));
void _start(void){
    __asm__ volatile("ldr sp, =0x03007F00\n bl xgba_main\n 1: b 1b\n");
}
void xgba_main(void){
    REG_DISPCNT=0x0403u; /* GBA mode 3 / BG2 */
    PROBE[0]=0x58474241u;
    unsigned fetches=0u,events=0u;
    int world=0;
    int available=external_fetch("emerald.world",DATA_AREA);
    if(available)++fetches;
    PROBE[1]=(unsigned)available;
    render(world,available,fetches,events);
    uint16_t previous=0x03FFu;
    for(;;){
        while(REG_VCOUNT<160u){}
        while(REG_VCOUNT>=160u){}
        uint16_t buttons=REG_KEYINPUT;
        uint16_t hit=(uint16_t)(previous & (uint16_t)~buttons);
        previous=buttons;
        if(hit & 0x0200u)world=(world+2)%3;
        else if(hit & 0x0100u)world=(world+1)%3;
        else if(hit & 0x0001u)++events;
        else continue;
        const char *names[3]={"emerald.world","rocket.world","heart_soul.world"};
        volatile uint8_t *dest=DATA_AREA+(unsigned)world*128u;
        available=external_fetch(names[world],dest);
        if(available)++fetches;
        PROBE[1]=(unsigned)available;
        PROBE[2]=fetches;
        PROBE[3]=events;
        PROBE[4]=(unsigned)world;
        render(world,available,fetches,events);
    }
}
