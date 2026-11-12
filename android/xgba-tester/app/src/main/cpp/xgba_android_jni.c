/*
 * R43 JNI frontend: Android rendering and physical XGBA host-provider handshake
 * for the EXACT mGBA core used in native CI (pinned fd9dc5c).
 *
 * ROMs and original game assets are NEVER bundled into the APK. A Java-side
 * signed-identity manifest and each resource SHA are validated before launch;
 * the native provider independently repeats SHA-256 verification per request.
 *
 * No network, native frame injection or GBA RAM mirroring beyond original
 * 256KiB. Files live in the app's sandbox only.
 */
#define _FILE_OFFSET_BITS 64
#define _POSIX_C_SOURCE 200809L
#include <jni.h>
#include <pthread.h>
#include <mgba/core/core.h>
#include <mgba/gba/core.h>
#include <mgba/internal/gba/gba.h>
#include <mgba-util/image.h>
#include <mgba-util/vfs.h>
#include "xgba_mgba_device.h"

#include <limits.h>
#include <stdint.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>

#define R43_MAX_RESOURCES 64u
#define R43_MAX_GAME_BYTES (32u * 1024u * 1024u)
#define R43_FRAME_PIXELS (240u*160u)
#define R43_MAX_RESOURCE_BYTES 16384u
struct R43Resource {
    char id[129];
    uint64_t offset;
    uint32_t length;
    uint8_t digest[32];
};
struct R43Pack {
    FILE *file;
    uint64_t file_size;
    unsigned count;
    struct R43Resource resources[R43_MAX_RESOURCES];
};

static pthread_mutex_t g_mutex=PTHREAD_MUTEX_INITIALIZER;
static struct R43Pack g_pack;
static struct XgbaGbaDevice g_device;
static struct mCore *g_core=NULL;
static uint8_t *g_rom=NULL;
static mColor *g_video=NULL;
static uint32_t g_input=0;
static int g_has_frame=0;
static uint32_t g_frames=0;

static int r43_parse_sha(const char *s,uint8_t result[32])
{
    if(!s || strlen(s)!=64)return 0;
    for(unsigned i=0;i<32;i++){
        unsigned hi,lo;
        char a=s[2*i],b=s[2*i+1];
        hi=a>='0'&&a<='9'?a-'0':a>='a'&&a<='f'?a-'a'+10u:256u;
        lo=b>='0'&&b<='9'?b-'0':b>='a'&&b<='f'?b-'a'+10u:256u;
        if(hi>15u||lo>15u)return 0;
        result[i]=(uint8_t)((hi<<4)|lo);
    }
    return 1;
}

static const struct R43Resource *r43_find(const struct R43Pack *pack,const char *id)
{
    if(!id)return NULL;
    for(unsigned i=0;i<pack->count;i++)
        if(strcmp(pack->resources[i].id,id)==0)
            return &pack->resources[i];
    return NULL;
}
static int r43_lookup(void *ctx,const char *id,uint64_t *length,uint8_t digest[32])
{
    struct R43Pack *pack=(struct R43Pack *)ctx;
    const struct R43Resource *r=r43_find(pack,id);
    if(!r)return 1;
    *length=r->length;
    memcpy(digest,r->digest,32);
    return 0;
}
static int r43_read(void *ctx,const char *id,uint8_t *dst,size_t cap,size_t *actual)
{
    struct R43Pack *pack=(struct R43Pack *)ctx;
    const struct R43Resource *r=r43_find(pack,id);
    if(!r||!pack->file||!actual||r->length>cap||
       r->offset>pack->file_size||r->length>pack->file_size-r->offset||
       r->offset>(uint64_t)INT64_MAX)
        return 1;
    if(fseeko(pack->file,(off_t)r->offset,SEEK_SET)!=0)return 1;
    size_t n=fread(dst,1,r->length,pack->file);
    if(n!=r->length)return 1;
    *actual=n; /* the mGBA R5 provider independently checks SHA-256 */
    return 0;
}
static void r43_cleanup_locked(void)
{
    if(g_core){
        if(g_core->board)
            ((struct GBA *)g_core->board)->xgbaDevice=NULL;
        mCoreConfigDeinit(&g_core->config);
        g_core->deinit(g_core);
        g_core=NULL;
    }
    free(g_video);g_video=NULL;
    free(g_rom);g_rom=NULL;
    if(g_pack.file)fclose(g_pack.file);
    memset(&g_pack,0,sizeof(g_pack));
    memset(&g_device,0,sizeof(g_device));
    g_input=0;g_frames=0;g_has_frame=0;
}
static jstring r43_error(JNIEnv *env,const char *value)
{
    return (*env)->NewStringUTF(env,value);
}

JNIEXPORT jstring JNICALL Java_org_xgba_tester_MainActivity_nativeOpen(
    JNIEnv *env,jclass cls,jstring gameFile,jstring dataFile,jstring saveFile,
    jstring sourceName,jstring sourceDigest,
    jobjectArray names,jlongArray offsets,jintArray lengths,jobjectArray shaList)
{
    (void)cls;
    char error[256]="";
    const char *rompath=NULL,*datapath=NULL,*savepath=NULL,*src=NULL,*digeststr=NULL;
    uint8_t expected_digest[32];
    uint8_t actual_digest[32];
    uint8_t *rom=NULL;
    FILE *romfile=NULL;
    struct R43Pack pack={0};
    jlong *positions=NULL;
    jint *sizes=NULL;
    const jsize count=(*env)->GetArrayLength(env,names);
    if(count<1||count>(jsize)R43_MAX_RESOURCES||
       count!=(*env)->GetArrayLength(env,offsets)||
       count!=(*env)->GetArrayLength(env,lengths)||
       count!=(*env)->GetArrayLength(env,shaList))
        return r43_error(env,"Invalid XGBA resource-table length");
    rompath=(*env)->GetStringUTFChars(env,gameFile,NULL);
    datapath=(*env)->GetStringUTFChars(env,dataFile,NULL);
    savepath=(*env)->GetStringUTFChars(env,saveFile,NULL);
    src=(*env)->GetStringUTFChars(env,sourceName,NULL);
    digeststr=(*env)->GetStringUTFChars(env,sourceDigest,NULL);
    if(!rompath||!datapath||!savepath||!src||!digeststr){
        snprintf(error,sizeof(error),"Cannot decode selected file paths");
        goto done;
    }
    if(strlen(src)>128u||strlen(src)<1u||!r43_parse_sha(digeststr,expected_digest)){
        snprintf(error,sizeof(error),"Invalid source identity or SHA-256");
        goto done;
    }
    positions=(*env)->GetLongArrayElements(env,offsets,NULL);
    sizes=(*env)->GetIntArrayElements(env,lengths,NULL);
    if(!positions||!sizes){
        snprintf(error,sizeof(error),"Cannot read resource metadata");
        goto done;
    }
    pack.file=fopen(datapath,"rb");
    if(!pack.file||fseeko(pack.file,0,SEEK_END)!=0){
        snprintf(error,sizeof(error),"Cannot open external XGBA sidecar");
        goto done;
    }
    off_t end=ftello(pack.file);
    if(end<=0){snprintf(error,sizeof(error),"Empty sidecar");goto done;}
    pack.file_size=(uint64_t)end;
    pack.count=(unsigned)count;
    for(jsize i=0;i<count;i++){
        jstring n=(jstring)(*env)->GetObjectArrayElement(env,names,i);
        jstring h=(jstring)(*env)->GetObjectArrayElement(env,shaList,i);
        if(!n||!h){snprintf(error,sizeof(error),"Missing resource ID/hash");goto done;}
        const char *id=(*env)->GetStringUTFChars(env,n,NULL);
        const char *hash=(*env)->GetStringUTFChars(env,h,NULL);
        if(!id||!hash){
            snprintf(error,sizeof(error),"Unreadable resource metadata");
        }else if(strlen(id)<1||strlen(id)>128u||sizes[i]<=0||
           sizes[i]>(jint)R43_MAX_RESOURCE_BYTES||positions[i]<0||
           (uint64_t)positions[i]>pack.file_size||
           (uint64_t)sizes[i]>pack.file_size-(uint64_t)positions[i]||
           !r43_parse_sha(hash,pack.resources[i].digest)){
            snprintf(error,sizeof(error),"Invalid external resource bounds/SHA");
        }else{
            for(unsigned c=0;c<strlen(id);c++){
                char x=id[c];
                if(!((x>='a'&&x<='z')||(x>='A'&&x<='Z')||
                     (x>='0'&&x<='9')||(c&&(x=='.'||x=='_'||x=='-')))){
                    snprintf(error,sizeof(error),"Resource ID contains prohibited characters");
                    break;
                }
            }
            if(!error[0]){
                strncpy(pack.resources[i].id,id,sizeof(pack.resources[i].id)-1);
                pack.resources[i].offset=(uint64_t)positions[i];
                pack.resources[i].length=(uint32_t)sizes[i];
                if(r43_find(&pack,id)!=&pack.resources[i]){
                    /* Check only already-set slots, not zero-valued future entries. */
                    snprintf(error,sizeof(error),"Duplicate resource ID");
                }
            }
        }
        if(id)(*env)->ReleaseStringUTFChars(env,n,id);
        if(hash)(*env)->ReleaseStringUTFChars(env,h,hash);
        (*env)->DeleteLocalRef(env,n);
        (*env)->DeleteLocalRef(env,h);
        if(error[0])goto done;
    }
    romfile=fopen(rompath,"rb");
    if(!romfile||fseeko(romfile,0,SEEK_END)!=0){
        snprintf(error,sizeof(error),"Cannot open selected GBA ROM");
        goto done;
    }
    off_t size=ftello(romfile);
    if(size<0xC0||size>(off_t)R43_MAX_GAME_BYTES){
        snprintf(error,sizeof(error),"ROM exceeds standard 32 MiB mapped game limit");
        goto done;
    }
    rom=malloc((size_t)size);
    if(!rom||fseeko(romfile,0,SEEK_SET)!=0||
       fread(rom,1,(size_t)size,romfile)!=(size_t)size){
        snprintf(error,sizeof(error),"Cannot load selected GBA ROM");
        goto done;
    }
    extern void XgbaProviderSha256(const uint8_t*,size_t,uint8_t[32]);
    XgbaProviderSha256(rom,(size_t)size,actual_digest);
    if(memcmp(actual_digest,expected_digest,32)!=0){
        snprintf(error,sizeof(error),"ROM does not match external pack source identity");
        goto done;
    }
    pthread_mutex_lock(&g_mutex);
    r43_cleanup_locked();
    g_rom=rom;rom=NULL;
    g_pack=pack;memset(&pack,0,sizeof(pack));
    struct XgbaMgbaProviderV1 host={
        .abi_version=1u,.struct_size=sizeof(host),
        .context=&g_pack,.lookup=r43_lookup,.read=r43_read
    };
    strcpy(host.source_id,src);
    memcpy(host.source_sha256,expected_digest,32);
    if(XgbaDeviceInit(&g_device,&host,1,src,expected_digest)!=0){
        snprintf(error,sizeof(error),"Native XGBA provider rejected source identity");
        goto bad_native;
    }
    g_core=GBACoreCreate();
    if(!g_core||!g_core->init(g_core)){
        snprintf(error,sizeof(error),"Patched native mGBA initialization failed");
        goto bad_native;
    }
    g_video=calloc(R43_FRAME_PIXELS,sizeof(mColor));
    if(!g_video){
        snprintf(error,sizeof(error),"Cannot allocate native LCD framebuffer");
        goto bad_native;
    }
    g_core->setVideoBuffer(g_core,g_video,240u);
    mCoreInitConfig(g_core,NULL);
    struct VFile *vf=VFileFromConstMemory(g_rom,(size_t)size);
    if(!vf||!g_core->loadROM(g_core,vf)){
        snprintf(error,sizeof(error),"Native mGBA refused supplied GBA executable");
        if(vf)vf->close(vf);
        goto bad_native;
    }
    if(!mCoreLoadSaveFile(g_core,savepath,false)){
        snprintf(error,sizeof(error),"Cannot attach private persistent GBA Flash save");
        goto bad_native;
    }
    g_core->reset(g_core);
    if(!g_core->board){
        snprintf(error,sizeof(error),"Native GBA board unavailable");
        goto bad_native;
    }
    ((struct GBA *)g_core->board)->xgbaDevice=&g_device;
    pthread_mutex_unlock(&g_mutex);
    goto done;
bad_native:
    r43_cleanup_locked();
    pthread_mutex_unlock(&g_mutex);
done:
    if(positions)(*env)->ReleaseLongArrayElements(env,offsets,positions,JNI_ABORT);
    if(sizes)(*env)->ReleaseIntArrayElements(env,lengths,sizes,JNI_ABORT);
    if(romfile)fclose(romfile);
    if(pack.file)fclose(pack.file);
    free(rom);
    if(rompath)(*env)->ReleaseStringUTFChars(env,gameFile,rompath);
    if(datapath)(*env)->ReleaseStringUTFChars(env,dataFile,datapath);
    if(savepath)(*env)->ReleaseStringUTFChars(env,saveFile,savepath);
    if(src)(*env)->ReleaseStringUTFChars(env,sourceName,src);
    if(digeststr)(*env)->ReleaseStringUTFChars(env,sourceDigest,digeststr);
    return r43_error(env,error[0]?error:"OK");
}

JNIEXPORT void JNICALL Java_org_xgba_tester_MainActivity_nativeFrame(
    JNIEnv *env,jclass cls,jint keys)
{
    (void)env;(void)cls;
    pthread_mutex_lock(&g_mutex);
    if(g_core){
        g_core->setKeys(g_core,(uint32_t)keys & 0x3FFu);
        g_core->runFrame(g_core);
        g_has_frame=1;
        ++g_frames;
    }
    pthread_mutex_unlock(&g_mutex);
}

JNIEXPORT jintArray JNICALL Java_org_xgba_tester_MainActivity_nativePixels(
    JNIEnv *env,jclass cls)
{
    (void)cls;
    jintArray output=(*env)->NewIntArray(env,R43_FRAME_PIXELS);
    if(!output)return NULL;
    pthread_mutex_lock(&g_mutex);
    if(g_video && g_has_frame){
        jint pixels[R43_FRAME_PIXELS];
        for(size_t i=0;i<R43_FRAME_PIXELS;i++){
            uint32_t c=g_video[i];
#ifdef COLOR_16_BIT
            uint32_t r=((c&0x1Fu)*255u+15u)/31u;
            uint32_t g=(((c>>5u)&0x1Fu)*255u+15u)/31u;
            uint32_t b=(((c>>10u)&0x1Fu)*255u+15u)/31u;
#else
            uint32_t r=c&0xFFu;
            uint32_t g=(c>>8u)&0xFFu;
            uint32_t b=(c>>16u)&0xFFu;
#endif
            pixels[i]=(jint)(0xFF000000u|(r<<16u)|(g<<8u)|b);
        }
        (*env)->SetIntArrayRegion(env,output,0,R43_FRAME_PIXELS,pixels);
    }
    pthread_mutex_unlock(&g_mutex);
    return output;
}
JNIEXPORT jlongArray JNICALL Java_org_xgba_tester_MainActivity_nativeStats(
    JNIEnv *env,jclass cls)
{
    (void)cls;
    jlongArray a=(*env)->NewLongArray(env,4);
    if(!a)return NULL;
    pthread_mutex_lock(&g_mutex);
    jlong stats[4]={(jlong)g_frames,(jlong)g_device.successful_reads,
                   (jlong)g_device.failed_reads,(jlong)g_device.provider_bad_sha256};
    pthread_mutex_unlock(&g_mutex);
    (*env)->SetLongArrayRegion(env,a,0,4,stats);
    return a;
}
JNIEXPORT void JNICALL Java_org_xgba_tester_MainActivity_nativeClose(
    JNIEnv *env,jclass cls)
{
    (void)env;(void)cls;
    pthread_mutex_lock(&g_mutex);
    r43_cleanup_locked();
    pthread_mutex_unlock(&g_mutex);
}
