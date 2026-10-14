package co.kr.badara.campledger;

import android.app.Activity;
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
    private static final String ROOT="https://ha.badara.co.kr/camp-ledger/static/downloads/";
    private final Activity activity;private final BooleanSupplier busy;private File pending;private boolean installing=false,permissionOpened=false;
    AppUpdater(Activity activity,BooleanSupplier busy){this.activity=activity;this.busy=busy;}
    private HttpURLConnection connect(String path) throws IOException {HttpURLConnection c=(HttpURLConnection)new URL(ROOT+path).openConnection();c.setConnectTimeout(10000);c.setReadTimeout(20000);c.setInstanceFollowRedirects(false);if(c.getResponseCode()!=200){c.disconnect();throw new IOException();}return c;}
    private byte[] read(HttpURLConnection c,int limit) throws IOException {try(InputStream input=c.getInputStream();ByteArrayOutputStream output=new ByteArrayOutputStream()){byte[] buffer=new byte[8192];int n;while((n=input.read(buffer))!=-1){if(output.size()+n>limit)throw new IOException();output.write(buffer,0,n);}return output.toByteArray();}finally{c.disconnect();}}
    private String digest(File file) throws Exception {MessageDigest sha=MessageDigest.getInstance("SHA-256");try(InputStream in=new FileInputStream(file)){byte[] bytes=new byte[8192];int n;while((n=in.read(bytes))!=-1)sha.update(bytes,0,n);}StringBuilder out=new StringBuilder();for(byte b:sha.digest())out.append(String.format("%02x",b&255));return out.toString();}
    private boolean signedByThisApp(File file,long expected) throws Exception {PackageManager pm=activity.getPackageManager();PackageInfo own=pm.getPackageInfo(activity.getPackageName(),PackageManager.GET_SIGNING_CERTIFICATES),next=pm.getPackageArchiveInfo(file.getPath(),PackageManager.GET_SIGNING_CERTIFICATES);if(next==null||!own.packageName.equals(next.packageName)||next.getLongVersionCode()!=expected||next.getLongVersionCode()<=own.getLongVersionCode()||own.signingInfo==null||next.signingInfo==null)return false;for(Signature a:own.signingInfo.getApkContentsSigners())for(Signature b:next.signingInfo.getApkContentsSigners())if(Arrays.equals(a.toByteArray(),b.toByteArray()))return true;return false;}
    void check(){new Thread(()->{try{JSONObject meta=new JSONObject(new String(read(connect("android-version.json"),16384),"UTF-8"));long version=meta.getLong("version_code");PackageInfo own=activity.getPackageManager().getPackageInfo(activity.getPackageName(),0);if(version<=own.getLongVersionCode())return;String hash=meta.getString("sha256");if(!hash.matches("[0-9a-f]{64}"))return;File dir=new File(activity.getCacheDir(),"updates");dir.mkdirs();File apk=new File(dir,"camp-ledger.apk");if(!apk.isFile()||!hash.equals(digest(apk))){activity.runOnUiThread(()->Toast.makeText(activity,"새 앱 버전을 다운로드하고 있습니다.",Toast.LENGTH_LONG).show());HttpURLConnection c=connect("camp-ledger.apk");File part=new File(dir,"download.part");try(InputStream in=c.getInputStream();OutputStream out=new FileOutputStream(part)){byte[] bytes=new byte[16384];int n,total=0;while((n=in.read(bytes))!=-1){total+=n;if(total>20*1024*1024)throw new IOException();out.write(bytes,0,n);}}finally{c.disconnect();}if(!hash.equals(digest(part))||!signedByThisApp(part,version)){part.delete();throw new IOException();}if(apk.exists())apk.delete();if(!part.renameTo(apk))throw new IOException();}if(!signedByThisApp(apk,version))return;activity.runOnUiThread(()->{pending=apk;if(busy.getAsBoolean())Toast.makeText(activity,"앱 업데이트가 준비됐습니다. 저장 후 설치 화면이 열립니다.",Toast.LENGTH_LONG).show();maybeInstall();});}catch(Exception ignored){/* Keep the ledger usable when update checks are unavailable. */}},"camp-ledger-update").start();}
    void maybeInstall(){if(pending==null||installing||busy.getAsBoolean()||activity.isFinishing())return;if(!activity.getPackageManager().canRequestPackageInstalls()){if(!permissionOpened){permissionOpened=true;Toast.makeText(activity,"앱 업데이트 설치를 허용한 뒤 돌아오세요.",Toast.LENGTH_LONG).show();try{activity.startActivity(new Intent(Settings.ACTION_MANAGE_UNKNOWN_APP_SOURCES,Uri.parse("package:"+activity.getPackageName())));}catch(Exception e){Toast.makeText(activity,"휴대폰 설정에서 캠핑 장부의 앱 설치를 허용해주세요.",Toast.LENGTH_LONG).show();}}return;}
        Intent install=new Intent(Intent.ACTION_VIEW);install.setDataAndType(LedgerFileProvider.uri(activity,"updates",pending),"application/vnd.android.package-archive");install.addFlags(Intent.FLAG_GRANT_READ_URI_PERMISSION);try{installing=true;activity.startActivity(install);}catch(Exception e){installing=false;Toast.makeText(activity,"설정에서 앱 설치 파일을 다운로드해 업데이트해주세요.",Toast.LENGTH_LONG).show();}}
}
