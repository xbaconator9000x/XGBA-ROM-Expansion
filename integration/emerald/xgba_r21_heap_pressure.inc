/* R21 test-only instrumentation is COMPILED INSIDE Emerald's original
 * src/malloc.c. It inspects the actual MemBlock linked-list allocator and
 * uses only Alloc/Free/CheckHeap in the real guest CPU.
 * Source is included after the original malloc.c declarations.
 */
#ifndef XGBA_R21_EMERALD_HEAP_PRESSURE_INC
#define XGBA_R21_EMERALD_HEAP_PRESSURE_INC

#define XGBA_R21_HEAP_MAGIC 0x52323148u /* "R21H" */
#define XGBA_R21_RESERVED_BYTES 16384u
#define XGBA_R21_ERR_BOUNDARY 1u
#define XGBA_R21_ERR_ALLOC 2u
#define XGBA_R21_ERR_GUARD 4u
#define XGBA_R21_ERR_CHAIN 8u
#define XGBA_R21_ERR_REJECT 16u

_Static_assert(HEAP_SIZE==0x1C000u, "R21 original Emerald heap sizing drift");
_Static_assert(XGBA_R21_RESERVED_BYTES < HEAP_SIZE, "R21 reserve exceeds heap");

struct XgbaR21HeapProof {
    volatile u32 magic,cycles,errors,heap_start,heap_size,arena_start,reserved;
    volatile u32 alloc_success,expected_rejections,free_calls,peak_live_bytes;
    volatile u32 min_largest_free,min_total_free,audits,verified_pattern_bytes;
    volatile u32 final_block_count,peak_block_count;
};
EWRAM_DATA volatile struct XgbaR21HeapProof gXgbaR21HeapProof = {0};

static bool32 XgbaR21AuditOriginalHeap(void)
{
    const u8 *const begin=(const u8 *)gHeap;
    const u8 *const arena=begin+HEAP_SIZE-XGBA_R21_RESERVED_BYTES;
    const u8 *const end=begin+sHeapSize;
    struct MemBlock *head;
    struct MemBlock *node;
    u32 count=0,live=0,largest=0,freeBytes=0;
    if (sHeapStart != (void *)gHeap ||
        sHeapSize == 0u || sHeapSize > HEAP_SIZE-XGBA_R21_RESERVED_BYTES ||
        end>arena) {
        gXgbaR21HeapProof.errors |= XGBA_R21_ERR_BOUNDARY;
        return FALSE;
    }
    gXgbaR21HeapProof.heap_start=(u32)begin;
    gXgbaR21HeapProof.heap_size=sHeapSize;
    gXgbaR21HeapProof.arena_start=(u32)arena;
    gXgbaR21HeapProof.reserved=XGBA_R21_RESERVED_BYTES;
    head=(struct MemBlock *)sHeapStart;
    node=head;
    do {
        const u8 *start=(const u8 *)node;
        const u8 *next;
        if (start<begin || start>=end ||
            (u32)(end-start)<sizeof(struct MemBlock) ||
            node->magic!=MALLOC_SYSTEM_ID ||
            node->size>(u32)(end-start)-sizeof(struct MemBlock)) {
            gXgbaR21HeapProof.errors |= XGBA_R21_ERR_CHAIN;
            return FALSE;
        }
        next=node->data+node->size;
        if (node->flag) {
            live+=node->size;
        } else {
            freeBytes+=node->size;
            if (node->size>largest)
                largest=node->size;
        }
        if (node->next!=head && (const u8 *)node->next!=next) {
            gXgbaR21HeapProof.errors |= XGBA_R21_ERR_CHAIN;
            return FALSE;
        }
        node=node->next;
        if (++count>2048u) {
            gXgbaR21HeapProof.errors |= XGBA_R21_ERR_CHAIN;
            return FALSE;
        }
    } while (node!=head);
    if (!CheckHeap()) {
        gXgbaR21HeapProof.errors |= XGBA_R21_ERR_CHAIN;
        return FALSE;
    }
    ++gXgbaR21HeapProof.audits;
    if (live>gXgbaR21HeapProof.peak_live_bytes)
        gXgbaR21HeapProof.peak_live_bytes=live;
    if (!gXgbaR21HeapProof.min_largest_free ||
        largest<gXgbaR21HeapProof.min_largest_free)
        gXgbaR21HeapProof.min_largest_free=largest;
    if (!gXgbaR21HeapProof.min_total_free ||
        freeBytes<gXgbaR21HeapProof.min_total_free)
        gXgbaR21HeapProof.min_total_free=freeBytes;
    gXgbaR21HeapProof.final_block_count=count;
    if (count>gXgbaR21HeapProof.peak_block_count)
        gXgbaR21HeapProof.peak_block_count=count;
    return TRUE;
}

static bool32 XgbaR21WithinUnreservedHeap(const void *ptr,u32 size)
{
    const u8 *p=(const u8 *)ptr;
    const u8 *begin=(const u8 *)gHeap;
    const u8 *end=begin+sHeapSize;
    return ptr!=NULL && p>=begin && p<end && size<=(u32)(end-p) &&
           end<=begin+HEAP_SIZE-XGBA_R21_RESERVED_BYTES;
}

void XgbaR21PressureCycle(void)
{
    u8 *a=NULL,*b=NULL,*c=NULL,*replacement=NULL;
    u32 i;
    gXgbaR21HeapProof.magic=XGBA_R21_HEAP_MAGIC;
    ++gXgbaR21HeapProof.cycles;
    if (!XgbaR21AuditOriginalHeap())
        return;
    /* Keep all allocations inside native Emerald's real original heap.
     * Fragment a 12 KiB live set and test ordinary first-fit reuse.
     * This does not overwrite a single byte of the protected XGBA tail. */
    a=Alloc(4096u);
    b=Alloc(6144u);
    c=Alloc(2048u);
    if (a)++gXgbaR21HeapProof.alloc_success;
    if (b)++gXgbaR21HeapProof.alloc_success;
    if (c)++gXgbaR21HeapProof.alloc_success;
    if (!XgbaR21WithinUnreservedHeap(a,4096u) ||
        !XgbaR21WithinUnreservedHeap(b,6144u) ||
        !XgbaR21WithinUnreservedHeap(c,2048u)) {
        gXgbaR21HeapProof.errors |= XGBA_R21_ERR_ALLOC;
        goto cleanup;
    }
    for(i=0;i<4096u;++i)a[i]=0xA5u;
    for(i=0;i<6144u;++i)b[i]=0x5Au;
    for(i=0;i<2048u;++i)c[i]=0xC3u;
    if (!XgbaR21AuditOriginalHeap())
        goto cleanup;
    Free(b);b=NULL;++gXgbaR21HeapProof.free_calls;
    replacement=Alloc(5120u);
    if(replacement)++gXgbaR21HeapProof.alloc_success;
    if (!XgbaR21WithinUnreservedHeap(replacement,5120u) ||
        replacement==a || replacement==c) {
        gXgbaR21HeapProof.errors |= XGBA_R21_ERR_ALLOC;
        goto cleanup;
    }
    for(i=0;i<5120u;++i)replacement[i]=0x69u;
    for(i=0;i<4096u;++i)
        if(a[i]!=0xA5u) {
            gXgbaR21HeapProof.errors |= XGBA_R21_ERR_GUARD;
            break;
        }
    for(i=0;i<2048u;++i)
        if(c[i]!=0xC3u) {
            gXgbaR21HeapProof.errors |= XGBA_R21_ERR_GUARD;
            break;
        }
    gXgbaR21HeapProof.verified_pattern_bytes+=6144u;
cleanup:
    if(replacement){Free(replacement);++gXgbaR21HeapProof.free_calls;}
    if(c){Free(c);++gXgbaR21HeapProof.free_calls;}
    if(b){Free(b);++gXgbaR21HeapProof.free_calls;}
    if(a){Free(a);++gXgbaR21HeapProof.free_calls;}
    /* The engine's own allocator must reject an impossible allocation.
     * A successful result would imply metadata corruption or a broken bound. */
    a=Alloc(HEAP_SIZE);
    if (a) {
        gXgbaR21HeapProof.errors |= XGBA_R21_ERR_REJECT;
        Free(a);
    } else {
        ++gXgbaR21HeapProof.expected_rejections;
    }
    XgbaR21AuditOriginalHeap();
}
#endif
