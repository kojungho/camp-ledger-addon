package co.kr.badara.campsitejournal;

import android.app.Activity;
import android.app.DownloadManager;
import android.content.Context;
import android.content.Intent;
import android.content.SharedPreferences;
import android.graphics.Color;
import android.net.Uri;
import android.os.Bundle;
import android.os.Build;
import android.provider.MediaStore;
import android.webkit.JavascriptInterface;
import android.database.Cursor;
import android.provider.OpenableColumns;
import java.io.*;
import java.util.ArrayList;
import java.util.UUID;
import android.view.ViewGroup;
import android.os.Environment;
import android.security.keystore.KeyGenParameterSpec;
import android.security.keystore.KeyProperties;
import android.util.Base64;
import android.view.View;
import android.view.WindowInsets;
import android.webkit.CookieManager;
import android.webkit.ValueCallback;
import android.webkit.WebChromeClient;
import android.webkit.WebResourceRequest;
import android.webkit.WebResourceError;
import android.webkit.WebSettings;
import android.webkit.WebView;
import android.webkit.WebViewClient;
import android.widget.Button;
import android.widget.EditText;
import android.widget.LinearLayout;
import android.widget.TextView;
import android.widget.Toast;
import java.security.KeyStore;
import javax.crypto.Cipher;
import javax.crypto.KeyGenerator;
import javax.crypto.SecretKey;
import javax.crypto.spec.GCMParameterSpec;

public class MainActivity extends Activity {
    private static final String BASE="https://ha.badara.co.kr/campsite-journal/";

    private static final String ALIAS="campsite-journal-device-key";
    private WebView web;
    private ValueCallback<Uri[]> chooser;
    private volatile String requestedPhotoPickerMode;
    private volatile boolean editing=false,journalEditing=false,ledgerEditing=false;
    private boolean chooserPhotos=false;
    private AppUpdater updater;
    public final class PhotoPickerBridge {
        private final boolean ledger;
        PhotoPickerBridge(boolean ledger){this.ledger=ledger;}
        @JavascriptInterface public void preparePhotoPicker(String mode) {requestedPhotoPickerMode="gallery".equals(mode)?"gallery":"files";}
        @JavascriptInterface public void setEditing(boolean value){if(ledger)ledgerEditing=value;else journalEditing=value;editing=journalEditing||ledgerEditing;if(!editing&&updater!=null)runOnUiThread(()->updater.maybeInstall());}
        @JavascriptInterface public void flushCookies(){CookieManager.getInstance().flush();}
        @JavascriptInterface public String getVersion() {return appVersion();}
    }
    private String appVersion(){try{return getPackageManager().getPackageInfo(getPackageName(),0).versionName;}catch(Exception e){return "";}}
    private String key;
    private SharedPreferences prefs;

    @Override public void onCreate(Bundle state) {
        super.onCreate(state);
        prefs=getSharedPreferences("campsite-journal",MODE_PRIVATE);
        try {key=readKey();} catch(Exception e) {key=null;}
        File photos=new File(getCacheDir(),"photos");File[] old=photos.listFiles();if(old!=null)for(File f:old)if(f.isFile()&&System.currentTimeMillis()-f.lastModified()>7L*24*60*60*1000)f.delete();
        handleIntent(getIntent());
        if(key==null)showConnect(); else showLedger();
        updater=new AppUpdater(this,()->editing||chooser!=null);updater.check();
        
    }
    @Override protected void onNewIntent(Intent intent) {
        super.onNewIntent(intent);setIntent(intent);String previousKey=key;handleIntent(intent);
        if(key!=null&&(web==null||!key.equals(previousKey)))showLedger();
    }
    private void handleIntent(Intent intent) {
        Uri uri=intent.getData();
        if(uri==null||!"campsite-journal".equals(uri.getScheme())||!"connect".equals(uri.getHost()))return;
        String url=uri.getQueryParameter("url");
        String value=intent.getStringExtra("key");
        if(value==null)value=Uri.parse("https://local/?"+(uri.getFragment()==null?"":uri.getFragment())).getQueryParameter("key");
        if(!BASE.equals(url)||value==null||!value.matches("[A-Za-z0-9_-]{40,100}")) {
            Toast.makeText(this,"기록 설정에서 만든 연결 주소를 사용해주세요.",Toast.LENGTH_LONG).show();return;
        }
        try {saveKey(value);key=value;intent.setData(null);}catch(Exception e){Toast.makeText(this,"이 기기에 연결 정보를 저장하지 못했습니다.",Toast.LENGTH_LONG).show();}
    }
    private SecretKey secret() throws Exception {
        KeyStore store=KeyStore.getInstance("AndroidKeyStore");store.load(null);
        if(store.containsAlias(ALIAS))return (SecretKey)store.getKey(ALIAS,null);
        KeyGenerator generator=KeyGenerator.getInstance(KeyProperties.KEY_ALGORITHM_AES,"AndroidKeyStore");
        generator.init(new KeyGenParameterSpec.Builder(ALIAS,KeyProperties.PURPOSE_ENCRYPT|KeyProperties.PURPOSE_DECRYPT).setBlockModes(KeyProperties.BLOCK_MODE_GCM).setEncryptionPaddings(KeyProperties.ENCRYPTION_PADDING_NONE).build());
        return generator.generateKey();
    }
    private void saveKey(String value) throws Exception {
        Cipher cipher=Cipher.getInstance("AES/GCM/NoPadding");cipher.init(Cipher.ENCRYPT_MODE,secret());
        prefs.edit().putString("iv",Base64.encodeToString(cipher.getIV(),Base64.NO_WRAP)).putString("key",Base64.encodeToString(cipher.doFinal(value.getBytes("UTF-8")),Base64.NO_WRAP)).commit();
    }
    private String readKey() throws Exception {
        String encrypted=prefs.getString("key",null);if(encrypted==null)return null;
        Cipher cipher=Cipher.getInstance("AES/GCM/NoPadding");cipher.init(Cipher.DECRYPT_MODE,secret(),new GCMParameterSpec(128,Base64.decode(prefs.getString("iv",""),Base64.NO_WRAP)));
        return new String(cipher.doFinal(Base64.decode(encrypted,Base64.NO_WRAP)),"UTF-8");
    }
    private void showConnect() {
        LinearLayout layout=new LinearLayout(this);layout.setOrientation(LinearLayout.VERTICAL);layout.setPadding(48,100,48,48);layout.setBackgroundColor(Color.rgb(246,247,242));
        TextView title=new TextView(this);title.setText("△  캠핑 노트");title.setTextSize(28);title.setTextColor(Color.rgb(40,83,69));layout.addView(title);
        TextView text=new TextView(this);text.setText("처음 한 번만 기기를 연결하세요.\n\n기록의 앱 설치·연결에서 만든 연결키를 붙여넣으면, 이후에는 이 앱에서 기록만 바로 열립니다.");text.setTextSize(16);text.setPadding(0,32,0,32);layout.addView(text);
        EditText entry=new EditText(this);entry.setHint("기기 연결키 붙여넣기");entry.setSingleLine(true);entry.setInputType(android.text.InputType.TYPE_CLASS_TEXT|android.text.InputType.TYPE_TEXT_VARIATION_PASSWORD);layout.addView(entry);
        Button open=new Button(this);open.setText("기록 연결");open.setOnClickListener(v->{String value=entry.getText().toString().trim();if(!value.matches("[A-Za-z0-9_-]{40,100}")){entry.setError("기록에서 만든 연결키를 붙여넣어주세요.");return;}try{saveKey(value);key=value;showLedger();}catch(Exception e){entry.setError("연결 정보를 저장하지 못했습니다.");}});layout.addView(open);setContentView(layout);
    }
    private void showLedger() {
        if(web!=null)web.destroy();web=new WebView(this);web.setBackgroundColor(Color.rgb(246,247,242));
        web.setOnApplyWindowInsetsListener((v,insets)->{
            int left=insets.getSystemWindowInsetLeft(),top=insets.getSystemWindowInsetTop(),right=insets.getSystemWindowInsetRight(),bottom=insets.getSystemWindowInsetBottom();
            if(Build.VERSION.SDK_INT>=30){android.graphics.Insets bars=insets.getInsets(WindowInsets.Type.systemBars()|WindowInsets.Type.displayCutout());android.graphics.Insets keyboard=insets.getInsets(WindowInsets.Type.ime());left=bars.left;top=bars.top;right=bars.right;bottom=Math.max(bars.bottom,keyboard.bottom);}
            ViewGroup.LayoutParams raw=v.getLayoutParams();if(raw instanceof ViewGroup.MarginLayoutParams){ViewGroup.MarginLayoutParams params=(ViewGroup.MarginLayoutParams)raw;if(params.leftMargin!=left||params.topMargin!=top||params.rightMargin!=right||params.bottomMargin!=bottom){params.setMargins(left,top,right,bottom);v.setLayoutParams(params);}}return insets;
        });
        WebSettings settings=web.getSettings();settings.setJavaScriptEnabled(true);settings.setDomStorageEnabled(true);settings.setAllowFileAccess(false);settings.setAllowContentAccess(true);settings.setGeolocationEnabled(false);settings.setMixedContentMode(WebSettings.MIXED_CONTENT_NEVER_ALLOW);settings.setSafeBrowsingEnabled(true);
        settings.setUserAgentString(settings.getUserAgentString()+" CampsiteJournalAndroid/"+appVersion());
        web.addJavascriptInterface(new PhotoPickerBridge(false),"CampsiteJournalNative");
        web.addJavascriptInterface(new PhotoPickerBridge(true),"CampLedgerNative");
        CookieManager cookies=CookieManager.getInstance();cookies.setAcceptCookie(true);cookies.setAcceptThirdPartyCookies(web,false);
        web.setWebViewClient(new WebViewClient(){
            @Override public boolean shouldOverrideUrlLoading(WebView view,WebResourceRequest request){
                Uri uri=request.getUrl();if(!request.isForMainFrame()){return !("https".equals(uri.getScheme())&&(("ha.badara.co.kr".equals(uri.getHost())&&(uri.getPath().startsWith("/campsite-journal/")||uri.getPath().startsWith("/camp-ledger/")))||"postcode.map.kakao.com".equals(uri.getHost())||"postcode.map.daum.net".equals(uri.getHost())||"www.openstreetmap.org".equals(uri.getHost()))); }if("https".equals(uri.getScheme())&&"ha.badara.co.kr".equals(uri.getHost())&&(uri.getPath().startsWith("/campsite-journal/")||uri.getPath().startsWith("/camp-ledger/")))return false;
                try{startActivity(new Intent(Intent.ACTION_VIEW,uri));}catch(Exception ignored){}return true;
            }
            @Override public void onReceivedError(WebView view,WebResourceRequest request,WebResourceError error){if(request.isForMainFrame())Toast.makeText(MainActivity.this,"기록에 연결하지 못했습니다. 인터넷 연결을 확인해주세요.",Toast.LENGTH_LONG).show();}
        });
        web.setWebChromeClient(new WebChromeClient(){
            @Override public boolean onShowFileChooser(WebView view,ValueCallback<Uri[]> callback,FileChooserParams params){
                if(chooser!=null)chooser.onReceiveValue(null);chooser=callback;
                String requested=requestedPhotoPickerMode;requestedPhotoPickerMode=null;
                boolean image=false;for(String type:params.getAcceptTypes())if(type!=null&&type.startsWith("image/"))image=true;
                chooserPhotos=requested!=null||image;
                openChooser(params,"gallery".equals(requested)&&image,image);return true;
            }
        });
        web.setDownloadListener((url,agent,disposition,mime,length)->{
            Uri uri=Uri.parse(url);if(!"https".equals(uri.getScheme())||!"ha.badara.co.kr".equals(uri.getHost())||!(uri.getPath().startsWith("/campsite-journal/")||uri.getPath().startsWith("/camp-ledger/")))return;
            try{DownloadManager.Request download=new DownloadManager.Request(uri);download.addRequestHeader("Cookie",CookieManager.getInstance().getCookie(url));download.setNotificationVisibility(DownloadManager.Request.VISIBILITY_VISIBLE_NOTIFY_COMPLETED);download.setMimeType(mime);String name=android.webkit.URLUtil.guessFileName(url,disposition,mime);download.setDestinationInExternalPublicDir(Environment.DIRECTORY_DOWNLOADS,name);((DownloadManager)getSystemService(Context.DOWNLOAD_SERVICE)).enqueue(download);Toast.makeText(this,"다운로드를 시작했습니다.",Toast.LENGTH_SHORT).show();}catch(Exception e){Toast.makeText(this,"다운로드하지 못했습니다.",Toast.LENGTH_LONG).show();}
        });
        setContentView(web);
        cookies.setCookie(BASE,"campsite_device="+key+"; Path=/campsite-journal/; Max-Age=157680000; Secure; HttpOnly; SameSite=Strict",value->{cookies.flush();web.loadUrl(BASE+"hub");});
    }
    private void openChooser(WebChromeClient.FileChooserParams params,boolean gallery,boolean image) {
        boolean multiple=params.getMode()==WebChromeClient.FileChooserParams.MODE_OPEN_MULTIPLE;
        Intent select;
        if(gallery&&Build.VERSION.SDK_INT>=33){
            select=new Intent(MediaStore.ACTION_PICK_IMAGES);select.setType("image/*");
            if(multiple)select.putExtra(MediaStore.EXTRA_PICK_IMAGES_MAX,MediaStore.getPickImagesMaxLimit());
        }else if(gallery){
            select=new Intent(Intent.ACTION_GET_CONTENT);select.setType("image/*");select.addCategory(Intent.CATEGORY_OPENABLE);select.putExtra(Intent.EXTRA_ALLOW_MULTIPLE,multiple);
        }else{
            select=new Intent(Intent.ACTION_OPEN_DOCUMENT);select.addCategory(Intent.CATEGORY_OPENABLE);select.setType(image?"image/*":"*/*");select.putExtra(Intent.EXTRA_ALLOW_MULTIPLE,multiple);
        }
        select.addFlags(Intent.FLAG_GRANT_READ_URI_PERMISSION);
        try{startActivityForResult(select,10);}catch(Exception first){
            if(gallery){Intent fallback=new Intent(Intent.ACTION_GET_CONTENT);fallback.setType("image/*");fallback.addCategory(Intent.CATEGORY_OPENABLE);fallback.putExtra(Intent.EXTRA_ALLOW_MULTIPLE,multiple);try{startActivityForResult(fallback,10);return;}catch(Exception ignored){}}
            if(chooser!=null){chooser.onReceiveValue(null);chooser=null;}Toast.makeText(this,"사진 선택 앱을 열지 못했습니다.",Toast.LENGTH_LONG).show();
        }
    }
    private Uri[] selectedUris(int result,Intent data){if(result!=RESULT_OK||data==null)return null;ArrayList<Uri> list=new ArrayList<>();if(data.getClipData()!=null)for(int i=0;i<data.getClipData().getItemCount();i++)list.add(data.getClipData().getItemAt(i).getUri());else if(data.getData()!=null)list.add(data.getData());return list.isEmpty()?null:list.toArray(new Uri[0]);}
    private Uri cachePhoto(Uri source) throws Exception {
        File dir=new File(getCacheDir(),"photos");dir.mkdirs();String name="photo.jpg";
        try(Cursor cursor=getContentResolver().query(source,new String[]{OpenableColumns.DISPLAY_NAME},null,null,null)){if(cursor!=null&&cursor.moveToFirst())name=cursor.getString(0);}catch(Exception ignored){}
        if(name==null||name.trim().isEmpty())name="photo.jpg";name=name.replaceAll("[^\\p{L}\\p{N}._ -]","_");if(name.length()>100)name=name.substring(name.length()-100);
        File target=new File(dir,UUID.randomUUID().toString()+"-"+name);
        try(InputStream in=getContentResolver().openInputStream(source);OutputStream out=new FileOutputStream(target)){if(in==null)throw new IOException();byte[] buffer=new byte[16384];int n;while((n=in.read(buffer))!=-1)out.write(buffer,0,n);}catch(Exception e){target.delete();throw e;}
        if(target.length()==0){target.delete();throw new IOException();}return LedgerFileProvider.uri(this,"photos",target);
    }
    @Override protected void onActivityResult(int request,int result,Intent data){super.onActivityResult(request,result,data);if(request!=10||chooser==null)return;ValueCallback<Uri[]> pending=chooser;chooser=null;Uri[] uris=selectedUris(result,data);if(uris==null||!chooserPhotos){pending.onReceiveValue(uris);return;}
        new Thread(()->{ArrayList<Uri> copied=new ArrayList<>();for(Uri uri:uris)try{copied.add(cachePhoto(uri));}catch(Exception ignored){}runOnUiThread(()->{if(copied.isEmpty()){pending.onReceiveValue(null);Toast.makeText(this,"선택한 사진을 읽지 못했습니다. 파일 앱으로 다시 선택해주세요.",Toast.LENGTH_LONG).show();}else pending.onReceiveValue(copied.toArray(new Uri[0]));});},"campsite-journal-photos").start();
    }
    @Override protected void onResume(){super.onResume();if(updater!=null){updater.resumed();}}
    @Override public void onBackPressed(){if(web!=null&&web.canGoBack())web.goBack();else super.onBackPressed();}
    @Override protected void onDestroy(){if(web!=null)web.destroy();super.onDestroy();}
}
