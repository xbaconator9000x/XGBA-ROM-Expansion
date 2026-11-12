package org.xgba.tester;

import android.app.Activity;
import android.content.Intent;
import android.graphics.Bitmap;
import android.graphics.Canvas;
import android.graphics.Color;
import android.graphics.Paint;
import android.graphics.Rect;
import android.net.Uri;
import android.os.Bundle;
import android.os.Handler;
import android.os.Looper;
import android.view.Gravity;
import android.view.MotionEvent;
import android.view.View;
import android.view.ViewGroup;
import android.widget.Button;
import android.widget.LinearLayout;
import android.widget.TextView;

import org.json.JSONArray;
import org.json.JSONObject;

import java.io.File;
import java.io.FileInputStream;
import java.io.FileOutputStream;
import java.io.IOException;
import java.io.InputStream;
import java.io.RandomAccessFile;
import java.security.MessageDigest;
import java.util.Arrays;
import java.util.HashSet;
import java.util.Locale;
import java.util.concurrent.atomic.AtomicInteger;
import java.util.zip.ZipEntry;
import java.util.zip.ZipInputStream;

/** R43 actual Android UI for XGBA's pinned, opt-in patched mGBA native core.
 * Imports an authored/homebrew probe or a user-created GBA + XGBA sidecar.
 * No proprietary original game ROM is bundled or silently downloaded.
 */
public final class MainActivity extends Activity {
    private static final int PICK_ZIP=100;
    private static final long MAX_ROM=32L*1024L*1024L;
    private static final long MAX_PACK=512L*1024L*1024L;
    private static final long MAX_JSON=1024L*1024L;
    private static final int PIXELS=240*160;
    private static final int BG=Color.rgb(11,18,32);
    private static final int BUTTON=Color.rgb(35,52,76);
    private final AtomicInteger keys=new AtomicInteger(0);
    private final Handler handler=new Handler(Looper.getMainLooper());
    private volatile boolean active=false;
    private volatile boolean loaded=false;
    private Thread runner;
    private TextView info;
    private Screen screen;
    private File currentProject;
    private int statsTicker=0;

    static {
        System.loadLibrary("xgba");
    }
    private static native String nativeOpen(String gba, String sidecar,String save,
                                             String id,String sha256,
                                             String[] keys,long[] offsets,int[] lengths,String[] digests);
    private static native void nativeFrame(int heldButtons);
    private static native int[] nativePixels();
    private static native long[] nativeStats();
    private static native void nativeClose();

    private int dp(float n) {
        return (int)(getResources().getDisplayMetrics().density*n+0.5f);
    }
    @Override public void onCreate(Bundle state) {
        super.onCreate(state);
        getWindow().setStatusBarColor(BG);
        getWindow().setNavigationBarColor(BG);
        LinearLayout root=new LinearLayout(this);
        root.setOrientation(LinearLayout.VERTICAL);
        root.setBackgroundColor(BG);
        root.setPadding(dp(12),dp(8),dp(12),dp(8));
        setContentView(root);
        TextView heading=new TextView(this);
        heading.setText("XGBA  •  Expanded GBA tester");
        heading.setTextColor(Color.WHITE);
        heading.setTextSize(18);
        heading.setGravity(Gravity.CENTER);
        root.addView(heading,new LinearLayout.LayoutParams(-1,dp(33)));

        info=new TextView(this);
        info.setTextColor(Color.rgb(165,207,238));
        info.setTextSize(12);
        info.setText("Genuine patched mGBA. Import a probe bundle to test external reads.");
        info.setGravity(Gravity.CENTER);
        root.addView(info,new LinearLayout.LayoutParams(-1,dp(54)));

        screen=new Screen();
        root.addView(screen,new LinearLayout.LayoutParams(-1,0,1.0f));

        LinearLayout imports=new LinearLayout(this);
        imports.setGravity(Gravity.CENTER);
        Button sample=makeButton("Load XGBA probe",0);
        Button zip=makeButton("Import game + sidecar ZIP",0);
        imports.addView(sample,new LinearLayout.LayoutParams(0,dp(54),1));
        imports.addView(zip,new LinearLayout.LayoutParams(0,dp(54),1));
        root.addView(imports);
        sample.setOnClickListener(v->new Thread(()->{
            try(InputStream bundled=getAssets().open("xgba-probe.zip")){
                importBundle(bundled);
            }catch(Exception e){
                showStatus("Probe missing or rejected: "+e.getMessage());
            }
        },"xgba-demo-import").start());
        zip.setOnClickListener(v->{
            Intent intent=new Intent(Intent.ACTION_OPEN_DOCUMENT);
            intent.setType("application/zip");
            intent.addCategory(Intent.CATEGORY_OPENABLE);
            startActivityForResult(intent,PICK_ZIP);
        });

        LinearLayout shoulders=new LinearLayout(this);
        shoulders.setGravity(Gravity.CENTER);
        shoulders.addView(control("L",1<<9),new LinearLayout.LayoutParams(0,dp(46),1));
        shoulders.addView(control("SELECT",1<<2),new LinearLayout.LayoutParams(0,dp(46),1));
        shoulders.addView(control("START",1<<3),new LinearLayout.LayoutParams(0,dp(46),1));
        shoulders.addView(control("R",1<<8),new LinearLayout.LayoutParams(0,dp(46),1));
        root.addView(shoulders);

        LinearLayout pad=new LinearLayout(this);
        pad.setGravity(Gravity.CENTER);
        LinearLayout dpad=new LinearLayout(this);
        dpad.setGravity(Gravity.CENTER);
        dpad.setOrientation(LinearLayout.VERTICAL);
        dpad.addView(control("▲",1<<6),new LinearLayout.LayoutParams(-1,dp(50)));
        LinearLayout mid=new LinearLayout(this);
        mid.setGravity(Gravity.CENTER);
        mid.addView(control("◀",1<<5),new LinearLayout.LayoutParams(0,dp(54),1));
        mid.addView(control("▼",1<<7),new LinearLayout.LayoutParams(0,dp(54),1));
        mid.addView(control("▶",1<<4),new LinearLayout.LayoutParams(0,dp(54),1));
        dpad.addView(mid,new LinearLayout.LayoutParams(-1,dp(56)));
        pad.addView(dpad,new LinearLayout.LayoutParams(0,dp(110),2));

        LinearLayout ab=new LinearLayout(this);
        ab.setGravity(Gravity.CENTER);
        ab.addView(control("B",1<<1),new LinearLayout.LayoutParams(0,dp(75),1));
        ab.addView(control("A",1<<0),new LinearLayout.LayoutParams(0,dp(75),1));
        pad.addView(ab,new LinearLayout.LayoutParams(0,dp(110),1));
        root.addView(pad);
        showStatus("No game loaded. Choose Load XGBA probe to test the actual bridge.");
    }
    private Button makeButton(String text,int unused) {
        Button b=new Button(this);
        b.setText(text);
        b.setTextSize(11);
        b.setAllCaps(false);
        b.setTextColor(Color.WHITE);
        b.setBackgroundTintList(android.content.res.ColorStateList.valueOf(BUTTON));
        b.setPadding(dp(2),0,dp(2),0);
        return b;
    }
    private Button control(String label,int mask){
        Button b=makeButton(label,0);
        b.setTextSize(14);
        b.setOnTouchListener((view,event)->{
            int action=event.getActionMasked();
            if(action==MotionEvent.ACTION_DOWN||action==MotionEvent.ACTION_POINTER_DOWN)
                keys.updateAndGet(previous->previous|mask);
            else if(action==MotionEvent.ACTION_UP||action==MotionEvent.ACTION_CANCEL||
                    action==MotionEvent.ACTION_POINTER_UP)
                keys.updateAndGet(previous->previous&~mask);
            return true;
        });
        return b;
    }
    private final class Screen extends View {
        private final Bitmap bitmap=Bitmap.createBitmap(240,160,Bitmap.Config.ARGB_8888);
        private final Paint paint=new Paint(Paint.FILTER_BITMAP_FLAG);
        private final Rect src=new Rect(0,0,240,160);
        private final Rect dst=new Rect();
        Screen(){super(MainActivity.this);setLayerType(View.LAYER_TYPE_SOFTWARE,null);}
        @Override protected void onDraw(Canvas canvas){
            super.onDraw(canvas);
            canvas.drawColor(Color.BLACK);
            if(!loaded)return;
            int[] buffer=nativePixels();
            if(buffer!=null&&buffer.length==PIXELS)
                bitmap.setPixels(buffer,0,240,0,0,240,160);
            float scale=Math.min(getWidth()/240f,getHeight()/160f);
            int width=(int)(240*scale),height=(int)(160*scale);
            int x=(getWidth()-width)/2,y=(getHeight()-height)/2;
            dst.set(x,y,x+width,y+height);
            canvas.drawBitmap(bitmap,src,dst,paint);
        }
    }
    private void showStatus(String text) {
        handler.post(()->info.setText(text));
    }
    @Override protected void onActivityResult(int requestCode,int resultCode,Intent data) {
        super.onActivityResult(requestCode,resultCode,data);
        if(requestCode!=PICK_ZIP||resultCode!=RESULT_OK||data==null)return;
        Uri uri=data.getData();
        if(uri==null)return;
        new Thread(()->{
            try(InputStream stream=getContentResolver().openInputStream(uri)){
                if(stream==null)throw new IOException("Unable to open selected ZIP");
                importBundle(stream);
            }catch(Exception exc){showStatus("Import rejected: "+exc.getMessage());}
        },"xgba-import").start();
    }
    private static String sha(File file) throws Exception{
        MessageDigest digest=MessageDigest.getInstance("SHA-256");
        byte[] buf=new byte[32768];
        try(FileInputStream input=new FileInputStream(file)){
            for(int n;(n=input.read(buf))>=0;){
                if(n>0)digest.update(buf,0,n);
            }
        }
        return hex(digest.digest());
    }
    private static String hex(byte[] input){
        StringBuilder sb=new StringBuilder(input.length*2);
        for(byte b:input)sb.append(String.format(Locale.ROOT,"%02x",b&255));
        return sb.toString();
    }
    private static void copyEntry(ZipInputStream archive,File out,long cap) throws Exception {
        try(FileOutputStream file=new FileOutputStream(out)){
            byte[] buffer=new byte[32768];
            long total=0;
            for(int n;(n=archive.read(buffer))!=-1;){
                total+=n;
                if(total>cap)throw new IOException("ZIP member exceeds allowed limit");
                file.write(buffer,0,n);
            }
            file.getFD().sync();
        }
    }
    private void importBundle(InputStream raw) throws Exception{
        showStatus("Inspecting bundle and verifying full SHA-256 integrity…");
        File root=new File(getFilesDir(),"projects");
        if(!root.exists()&&!root.mkdirs())throw new IOException("Cannot create private import directory");
        File incoming=new File(root,"incoming-"+System.nanoTime());
        if(!incoming.mkdirs())throw new IOException("Cannot create private import workspace");
        boolean committed=false;
        try {
            HashSet<String> found=new HashSet<>();
            try(ZipInputStream zip=new ZipInputStream(raw)){
                ZipEntry entry;
                while((entry=zip.getNextEntry())!=null){
                    String name=entry.getName();
                    long cap;
                    if(name.equals("game.gba"))cap=MAX_ROM;
                    else if(name.equals("sidecar.bin"))cap=MAX_PACK;
                    else if(name.equals("manifest.json"))cap=MAX_JSON;
                    else throw new IOException("Unexpected ZIP member (files must stay flat)");
                    if(entry.isDirectory()||!found.add(name))
                        throw new IOException("Directory or duplicated ZIP member");
                    copyEntry(zip,new File(incoming,name),cap);
                    zip.closeEntry();
                }
            }
            if(found.size()!=3)throw new IOException("ZIP needs game.gba, sidecar.bin, manifest.json");
            File rom=new File(incoming,"game.gba");
            File data=new File(incoming,"sidecar.bin");
            File manifest=new File(incoming,"manifest.json");
            if(rom.length()<192||rom.length()>MAX_ROM)
                throw new IOException("Invalid GBA image length");
            if(manifest.length()>MAX_JSON)
                throw new IOException("Manifest too large");
            JSONObject m=new JSONObject(new String(java.nio.file.Files.readAllBytes(manifest.toPath()),
                                                    java.nio.charset.StandardCharsets.UTF_8));
            if(!"xgba-resource-manifest".equals(m.getString("format"))||
               m.getInt("version")!=1||
               !"sidecar.bin".equals(m.getString("data_file")))
                throw new IOException("Unsupported/unsafe XGBA sidecar manifest");
            JSONObject src=m.getJSONObject("source_identity");
            String sourceId=src.getString("id");
            String digest=src.getString("sha256");
            if(!sourceId.matches("[A-Za-z0-9][A-Za-z0-9._-]{0,127}")||
               !digest.matches("[0-9a-f]{64}"))
                throw new IOException("Unsafe source identity");
            if(!sha(rom).equals(digest))
                throw new IOException("ROM SHA-256 mismatch: bundle and game do not belong together");
            JSONArray entries=m.getJSONArray("resources");
            if(entries.length()<1||entries.length()>64)
                throw new IOException("Android tester currently supports 1..64 resources");
            String[] names=new String[entries.length()];
            String[] hashes=new String[entries.length()];
            long[] offsets=new long[entries.length()];
            int[] lengths=new int[entries.length()];
            HashSet<String> ids=new HashSet<>();
            try(RandomAccessFile pack=new RandomAccessFile(data,"r")){
                byte[] buffer=new byte[16384];
                for(int i=0;i<entries.length();i++){
                    JSONObject entry=entries.getJSONObject(i);
                    names[i]=entry.getString("id");
                    hashes[i]=entry.getString("sha256");
                    offsets[i]=entry.getLong("offset");
                    lengths[i]=entry.getInt("length");
                    if(!names[i].matches("[A-Za-z0-9][A-Za-z0-9._-]{0,127}")||
                       !ids.add(names[i])||
                       !hashes[i].matches("[0-9a-f]{64}")||
                       lengths[i]<1||lengths[i]>16384||
                       offsets[i]<32L*1024*1024||
                       offsets[i]>pack.length()||
                       lengths[i]>pack.length()-offsets[i])
                        throw new IOException("Untrusted source resource ID/bounds");
                    pack.seek(offsets[i]);
                    pack.readFully(buffer,0,lengths[i]);
                    MessageDigest d=MessageDigest.getInstance("SHA-256");
                    d.update(buffer,0,lengths[i]);
                    if(!hex(d.digest()).equals(hashes[i]))
                        throw new IOException("External source data digest mismatch: "+names[i]);
                }
            }
            File destination=new File(root,digest.substring(0,24));
            if(destination.exists()){
                // Reimport replaces only ROM + pack; the existing .sav remains.
                for(String file:new String[]{"game.gba","sidecar.bin","manifest.json"}){
                    File target=new File(destination,file);
                    if(!target.delete())throw new IOException("Cannot replace original imported "+file);
                    if(!new File(incoming,file).renameTo(target))
                        throw new IOException("Cannot move validated "+file);
                }
            }else if(!incoming.renameTo(destination)){
                throw new IOException("Cannot activate validated local XGBA bundle");
            }
            committed=true;
            currentProject=destination;
            getPreferences(MODE_PRIVATE).edit().putString("last_project",destination.getAbsolutePath()).apply();
            startNative(destination,sourceId,digest,names,offsets,lengths,hashes);
        }finally{
            if(!committed)for(File f:incoming.listFiles()==null?new File[0]:incoming.listFiles())f.delete();
            if(!committed)incoming.delete();
        }
    }
    private synchronized void stopEngine(){
        active=false;
        if(runner!=null&&runner!=Thread.currentThread()){
            try{runner.join(1500);}catch(InterruptedException e){Thread.currentThread().interrupt();}
        }
        runner=null;
        loaded=false;
        nativeClose(); // original GBA Flash is held within app sandbox
        keys.set(0);
    }
    private void startNative(File project,String src,String hash,String[] ids,long[] offsets,
                             int[] lengths,String[] digests){
        stopEngine();
        String response=nativeOpen(new File(project,"game.gba").getAbsolutePath(),
                                   new File(project,"sidecar.bin").getAbsolutePath(),
                                   new File(project,"private-save.sav").getAbsolutePath(),
                                   src,hash,ids,offsets,lengths,digests);
        if(!"OK".equals(response)){
            showStatus("Native XGBA launch failed: "+response);
            return;
        }
        loaded=true;active=true;
        showStatus("Patched mGBA active. Hold D-pad/A/B/L/R, inspect XGBA fetch count.");
        runner=new Thread(()->{
            long next=System.nanoTime();
            while(active){
                nativeFrame(keys.get());
                if((statsTicker++%15)==0){
                    long[] stats=nativeStats();
                    showStatus(String.format(Locale.ROOT,
                       "XGBA ACTIVE • %d frames • external reads %d • refused %d • SHA refused %d",
                       stats[0],stats[1],stats[2],stats[3]));
                }
                screen.postInvalidate();
                next+=16666667L;
                long sleep=(next-System.nanoTime())/1000000L;
                if(sleep>0&&sleep<40){
                    try{Thread.sleep(sleep);}catch(InterruptedException e){break;}
                }else if(sleep<0){next=System.nanoTime();}
            }
        },"xgba-mgba-original-native-core");
        runner.start();
    }
    @Override protected void onDestroy(){
        stopEngine();
        super.onDestroy();
    }
}
