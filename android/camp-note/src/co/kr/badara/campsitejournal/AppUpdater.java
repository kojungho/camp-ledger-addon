package co.kr.badara.campsitejournal;

import android.app.Activity;
import android.app.AlertDialog;
import android.content.Intent;
import android.content.pm.PackageInfo;
import android.content.pm.PackageManager;
import android.content.pm.Signature;
import android.net.Uri;
import android.provider.Settings;
import android.widget.Toast;
import java.io.*;
import java.net.*;
import java.security.MessageDigest;
import java.util.Arrays;
import java.util.function.BooleanSupplier;
import org.json.JSONObject;

final class AppUpdater {
    private static final String ROOT="https://ha.badara.co.kr/campsite-journal/static/downloads/";
    private final Activity activity;private final BooleanSupplier busy;private File pending;private JSONObject offered;
    private volatile boolean checking=false,downloading=false,installing=false,promptShowing=false;private boolean permissionOpened=false;private long lastCheck=0;
    AppUpdater(Activity activity,BooleanSupplier busy){this.activity=activity;this.busy=busy;}
    private HttpURLConnection connect(String path) throws IOException {HttpURLConnection c=(HttpURLConnection)new URL(ROOT+path).openConnection();c.setConnectTimeout(10000);c.setReadTimeout(20000);c.setInstanceFollowRedirects(false);if(c.getResponseCode()!=200){c.disconnect();throw new IOException();}return c;}
    private byte[] read(HttpURLConnection c,int limit) throws IOException {try(InputStream input=c.getInputStream();ByteArrayOutputStream output=new ByteArrayOutputStream()){byte[] buffer=new byte[8192];int n;while((n=input.read(buffer))!=-1){if(output.size()+n>limit)throw new IOException();output.write(buffer,0,n);}return output.toByteArray();}finally{c.disconnect();}}
    private String digest(File file) throws Exception {MessageDigest sha=MessageDigest.getInstance("SHA-256");try(InputStream in=new FileInputStream(file)){byte[] bytes=new byte[8192];int n;while((n=in.read(bytes))!=-1)sha.update(bytes,0,n);}StringBuilder out=new StringBuilder();for(byte b:sha.digest())out.append(String.format("%02x",b&255));return out.toString();}
    private boolean signedByThisApp(File file,long expected) throws Exception {PackageManager pm=activity.getPackageManager();PackageInfo own=pm.getPackageInfo(activity.getPackageName(),PackageManager.GET_SIGNING_CERTIFICATES),next=pm.getPackageArchiveInfo(file.getPath(),PackageManager.GET_SIGNING_CERTIFICATES);if(next==null||!own.packageName.equals(next.packageName)||next.getLongVersionCode()!=expected||next.getLongVersionCode()<=own.getLongVersionCode()||own.signingInfo==null||next.signingInfo==null)return false;for(Signature a:own.signingInfo.getApkContentsSigners())for(Signature b:next.signingInfo.getApkContentsSigners())if(Arrays.equals(a.toByteArray(),b.toByteArray()))return true;return false;}
    synchronized void check(){long now=System.currentTimeMillis();if(checking||downloading||installing||promptShowing||now-lastCheck<60000)return;lastCheck=now;checking=true;new Thread(()->{try{JSONObject meta=new JSONObject(new String(read(connect("android-version.json"),16384),"UTF-8"));PackageInfo own=activity.getPackageManager().getPackageInfo(activity.getPackageName(),0);if(meta.getLong("version_code")<=own.getLongVersionCode()||!meta.getString("sha256").matches("[0-9a-f]{64}"))return;activity.runOnUiThread(()->{offered=meta;maybeOffer();});}catch(Exception ignored){/* Keep the journal usable while offline. */}finally{checking=false;}},"campsite-update-check").start();}
    private void maybeOffer(){if(offered==null||promptShowing||downloading||installing||busy.getAsBoolean()||activity.isFinishing())return;JSONObject meta=offered;promptShowing=true;new AlertDialog.Builder(activity).setTitle("캠핑 노트 업데이트").setMessage("새 버전 "+meta.optString("version_name","")+"이 있습니다. 업데이트를 누르면 새 APK를 다운로드한 뒤 설치 화면이 열립니다. 설치 버튼을 눌러 완료해주세요. 연결 정보는 유지됩니다.").setPositiveButton("업데이트",(dialog,which)->{promptShowing=false;offered=null;download(meta);}).setNegativeButton("나중에",(dialog,which)->{promptShowing=false;offered=null;}).setCancelable(false).show();}
    private void download(JSONObject meta){if(downloading)return;downloading=true;Toast.makeText(activity,"업데이트를 다운로드하고 있습니다.",Toast.LENGTH_LONG).show();new Thread(()->{try{long version=meta.getLong("version_code");String hash=meta.getString("sha256");File dir=new File(activity.getCacheDir(),"updates");dir.mkdirs();File apk=new File(dir,"campsite-journal.apk");if(!apk.isFile()||!hash.equals(digest(apk))){HttpURLConnection c=connect("campsite-journal.apk");File part=new File(dir,"download.part");try(InputStream in=c.getInputStream();OutputStream out=new FileOutputStream(part)){byte[] bytes=new byte[16384];int n,total=0;while((n=in.read(bytes))!=-1){total+=n;if(total>20*1024*1024)throw new IOException();out.write(bytes,0,n);}}finally{c.disconnect();}if(!hash.equals(digest(part))||!signedByThisApp(part,version)){part.delete();throw new IOException();}if(apk.exists())apk.delete();if(!part.renameTo(apk))throw new IOException();}if(!signedByThisApp(apk,version))throw new IOException();activity.runOnUiThread(()->{pending=apk;if(busy.getAsBoolean())Toast.makeText(activity,"업데이트가 준비됐습니다. 작성·사진 선택을 마치면 설치합니다.",Toast.LENGTH_LONG).show();maybeInstall();});}catch(Exception ignored){activity.runOnUiThread(()->Toast.makeText(activity,"업데이트를 받지 못했습니다. 앱 설치·연결에서 설치 파일을 받아주세요.",Toast.LENGTH_LONG).show());}finally{downloading=false;}},"campsite-update-download").start();}
    void resumed(){if(installing){installing=false;pending=null;}maybeInstall();check();}
    void maybeInstall(){if(pending==null){maybeOffer();return;}if(installing||busy.getAsBoolean()||activity.isFinishing())return;if(!activity.getPackageManager().canRequestPackageInstalls()){if(!permissionOpened){permissionOpened=true;Toast.makeText(activity,"이 앱의 업데이트 설치를 허용한 뒤 돌아오세요.",Toast.LENGTH_LONG).show();try{activity.startActivity(new Intent(Settings.ACTION_MANAGE_UNKNOWN_APP_SOURCES,Uri.parse("package:"+activity.getPackageName())));}catch(Exception e){Toast.makeText(activity,"휴대폰 설정에서 캠핑 노트의 앱 설치를 허용해주세요.",Toast.LENGTH_LONG).show();}}return;}
        Intent install=new Intent(Intent.ACTION_VIEW);install.setDataAndType(LedgerFileProvider.uri(activity,"updates",pending),"application/vnd.android.package-archive");install.addFlags(Intent.FLAG_GRANT_READ_URI_PERMISSION);try{installing=true;activity.startActivity(install);}catch(Exception e){installing=false;Toast.makeText(activity,"설정에서 설치 파일을 내려받아 업데이트해주세요.",Toast.LENGTH_LONG).show();}}
}
