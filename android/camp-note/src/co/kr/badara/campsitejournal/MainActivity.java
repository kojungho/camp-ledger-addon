package co.kr.badara.campsitejournal;

import android.app.Activity;
import android.app.DownloadManager;
import android.content.Context;
import android.content.ClipboardManager;
import android.content.ClipData;
import android.content.res.Configuration;
import android.graphics.drawable.ColorDrawable;
import android.view.WindowInsetsController;
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
    private AppUpdater updater;private boolean platformConnecting=false;private String pendingPlatformPayload;private int platformDeliveryAttempts=0;
    public final class PhotoPickerBridge {
        private final boolean ledger;
        PhotoPickerBridge(boolean ledger){this.ledger=ledger;}
        @JavascriptInterface public void preparePhotoPicker(String mode) {requestedPhotoPickerMode="gallery".equals(mode)?"gallery":"files";}
        @JavascriptInterface public void setEditing(boolean value){if(ledger)ledgerEditing=value;else journalEditing=value;editing=journalEditing||ledgerEditing;if(!editing&&updater!=null)runOnUiThread(()->updater.maybeInstall());}
        @JavascriptInterface public void flushCookies(){CookieManager.getInstance().flush();}
        @JavascriptInterface public String readReservationClipboard(){
            try{ClipboardManager clipboard=(ClipboardManager)getSystemService(Context.CLIPBOARD_SERVICE);if(clipboard==null||!clipboard.hasPrimaryClip())return "";ClipData clip=clipboard.getPrimaryClip();if(clip==null||clip.getItemCount()==0)return "";CharSequence value=clip.getItemAt(0).getText();if(value==null)return "";String text=value.toString();return text.length()>10000?text.substring(0,10000):text;}catch(Exception unavailable){return "";}
        }
        @JavascriptInterface public int getPlatformSyncVersion(){return 8;}
        @JavascriptInterface public void openPlatform(String provider){openPlatformIncremental(provider,"{}");}
        @JavascriptInterface public void openPlatformIncremental(String provider,String history){openPlatformAccount(provider,1,history);}
        @JavascriptInterface public void openPlatformAccount(String provider,int account,String history){
            if(!"camfit".equals(provider)&&!"thankq".equals(provider)&&!"campingtalk".equals(provider)&&!"naver".equals(provider))return;
            if(account!=1&&account!=2)return;
            final String known=history!=null&&history.length()<=150000?history:"{}";
            runOnUiThread(()->{if(platformConnecting)return;platformConnecting=true;try{startActivityForResult(new Intent(MainActivity.this,account==2?PlatformAccountTwoActivity.class:PlatformAccountOneActivity.class).putExtra("provider",provider).putExtra("history",known),901);}catch(RuntimeException error){platformConnecting=false;android.util.Log.e("CampNotePlatform","Platform launch failed",error);Toast.makeText(MainActivity.this,"플랫폼 화면을 열지 못했습니다. 앱 업데이트를 확인해주세요.",Toast.LENGTH_LONG).show();}});
        }
        @JavascriptInterface public String getVersion() {return appVersion();}
        @JavascriptInterface public boolean isMapAppInstalled(String kind){
            String packageName="kakaomap".equals(kind)?"net.daum.android.map":"navermap".equals(kind)?"com.nhn.android.nmap":"kakaonavi".equals(kind)?"com.locnall.KimGiSa":"tmap".equals(kind)?"com.skt.tmap.ku":null;
            if(packageName==null)return false;
            try{return getPackageManager().getApplicationInfo(packageName,0).enabled;}catch(Exception unavailable){return false;}
        }
        @JavascriptInterface public void openMapFallback(String url){
            try{Uri uri=Uri.parse(url);String host=uri.getHost();if(!"https".equals(uri.getScheme())||!("map.kakao.com".equals(host)||"map.naver.com".equals(host)||"play.google.com".equals(host)||"apps.apple.com".equals(host)))return;
                runOnUiThread(()->{try{startActivity(new Intent(Intent.ACTION_VIEW,uri));}catch(Exception unavailable){Toast.makeText(MainActivity.this,"브라우저나 스토어 앱을 확인해주세요.",Toast.LENGTH_SHORT).show();}});
            }catch(Exception ignored){}
        }
        @JavascriptInterface public void openMapUrl(String url){runOnUiThread(()->{try{if(!openMappingUri(Uri.parse(url)))Toast.makeText(MainActivity.this,"지도 연결 주소를 확인해주세요.",Toast.LENGTH_SHORT).show();}catch(Exception ignored){}});}
    }
    private String appVersion(){try{return getPackageManager().getPackageInfo(getPackageName(),0).versionName;}catch(Exception e){return "";}}
    private String key;
    private SharedPreferences prefs;

    @Override public void onCreate(Bundle state) {
        super.onCreate(state);
        applySystemBars();
        prefs=getSharedPreferences("campsite-journal",MODE_PRIVATE);
        try {key=readKey();} catch(Exception e) {key=null;}
        File photos=new File(getCacheDir(),"photos");File[] old=photos.listFiles();if(old!=null)for(File f:old)if(f.isFile()&&System.currentTimeMillis()-f.lastModified()>7L*24*60*60*1000)f.delete();
        handleIntent(getIntent());
        if(key==null)showConnect(); else showLedger();
        updater=new AppUpdater(this,()->editing||chooser!=null||platformConnecting);updater.check();
        
    }
    @Override protected void onNewIntent(Intent intent) {
        super.onNewIntent(intent);setIntent(intent);String previousKey=key;handleIntent(intent);
        if(key!=null&&(web==null||!key.equals(previousKey)))showLedger();
    }
    private void applySystemBars(){
        boolean dark=(getResources().getConfiguration().uiMode&Configuration.UI_MODE_NIGHT_MASK)==Configuration.UI_MODE_NIGHT_YES;
        int background=dark?Color.rgb(23,37,31):Color.rgb(250,251,247);
        getWindow().setBackgroundDrawable(new ColorDrawable(background));
        View decor=getWindow().getDecorView();decor.setBackgroundColor(background);
        getWindow().setStatusBarColor(background);getWindow().setNavigationBarColor(background);
        if(Build.VERSION.SDK_INT>=29){getWindow().setStatusBarContrastEnforced(false);getWindow().setNavigationBarContrastEnforced(false);}
        if(Build.VERSION.SDK_INT>=30){WindowInsetsController controller=getWindow().getInsetsController();if(controller!=null){int mask=WindowInsetsController.APPEARANCE_LIGHT_STATUS_BARS|WindowInsetsController.APPEARANCE_LIGHT_NAVIGATION_BARS;controller.setSystemBarsAppearance(dark?0:mask,mask);}}
        else{int flags=decor.getSystemUiVisibility(),mask=View.SYSTEM_UI_FLAG_LIGHT_STATUS_BAR|View.SYSTEM_UI_FLAG_LIGHT_NAVIGATION_BAR;decor.setSystemUiVisibility(dark?flags&~mask:flags|mask);}
    }
    @Override public void onConfigurationChanged(Configuration configuration){super.onConfigurationChanged(configuration);applySystemBars();}
    @Override public void onWindowFocusChanged(boolean focused){super.onWindowFocusChanged(focused);if(focused)applySystemBars();}
    private boolean openMappingUri(Uri uri){
        String fallback=null;Uri destination=uri;
        try{if("intent".equals(uri.getScheme())){Intent parsed=Intent.parseUri(uri.toString(),Intent.URI_INTENT_SCHEME);destination=parsed.getData();fallback=parsed.getStringExtra("browser_fallback_url");}}catch(Exception error){return false;}
        if(destination==null)return false;
        String scheme=destination.getScheme(),packageName;
        if("kakaomap".equals(scheme))packageName="net.daum.android.map";
        else if("nmap".equals(scheme))packageName="com.nhn.android.nmap";
        else if("kakaonavi-sdk".equals(scheme)||"kakaonavi".equals(scheme))packageName="com.locnall.KimGiSa";
        else if("tmap".equals(scheme))packageName="com.skt.tmap.ku";
        else return false;
        try{startActivity(new Intent(Intent.ACTION_VIEW,destination).setPackage(packageName).addCategory(Intent.CATEGORY_BROWSABLE));}
        catch(Exception unavailable){
            Uri backup=fallback==null?null:Uri.parse(fallback);String host=backup==null?null:backup.getHost();
            if(backup==null||!"https".equals(backup.getScheme())||!("kakaonavi.kakao.com".equals(host)||"play.google.com".equals(host)))backup=Uri.parse("https://play.google.com/store/apps/details?id="+packageName);
            try{startActivity(new Intent(Intent.ACTION_VIEW,backup));Toast.makeText(this,"지도 앱 설치 안내를 엽니다.",Toast.LENGTH_SHORT).show();}catch(Exception ignored){Toast.makeText(this,"지도 앱을 설치한 뒤 다시 선택해주세요.",Toast.LENGTH_LONG).show();}
        }
        return true;
    }
    private void handleIntent(Intent intent) {
        Uri uri=intent.getData();
        if(uri==null||!"campsite-journal".equals(uri.getScheme())||!"connect".equals(uri.getHost()))return;
        String url=uri.getQueryParameter("url");
        String value=intent.getStringExtra("key");
        if(value==null)value=Uri.parse("https://local/?"+(uri.getFragment()==null?"":uri.getFragment())).getQueryParameter("key");
        if(!BASE.equals(url)||value==null||!value.matches("[A-Za-z0-9_-]{40,100}")) {
            Toast.makeText(this,"캠핑 노트 설치·연결에서 만든 연결 주소를 사용해주세요.",Toast.LENGTH_LONG).show();return;
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
        TextView text=new TextView(this);text.setText("처음 한 번만 기기를 연결하세요.\n\n홈어시스턴트 상단의 캠핑 노트 설치·연결에서 이 휴대폰 연결을 누르세요. PC에서는 새 기기 연결의 QR을 읽으면 됩니다. 연결키를 복사할 필요가 없습니다.");text.setTextSize(16);text.setPadding(0,32,0,32);layout.addView(text);
        Button quick=new Button(this);quick.setText("홈어시스턴트에서 자동 연결");quick.setOnClickListener(v->{try{startActivity(new Intent(Intent.ACTION_VIEW,Uri.parse("https://ha.badara.co.kr/5ec8f074_camp_ledger")));}catch(Exception e){Toast.makeText(this,"홈어시스턴트에서 캠핑 노트 설치·연결을 열어주세요.",Toast.LENGTH_LONG).show();}});layout.addView(quick);
        EditText entry=new EditText(this);entry.setHint("기기 연결키 붙여넣기");entry.setSingleLine(true);entry.setInputType(android.text.InputType.TYPE_CLASS_TEXT|android.text.InputType.TYPE_TEXT_VARIATION_PASSWORD);layout.addView(entry);
        Button open=new Button(this);open.setText("캠핑 노트 연결");open.setOnClickListener(v->{String value=entry.getText().toString().trim();if(!value.matches("[A-Za-z0-9_-]{40,100}")){entry.setError("캠핑 노트에서 만든 연결키를 붙여넣어주세요.");return;}try{saveKey(value);key=value;showLedger();}catch(Exception e){entry.setError("연결 정보를 저장하지 못했습니다.");}});layout.addView(open);entry.setVisibility(View.GONE);open.setVisibility(View.GONE);Button manual=new Button(this);manual.setText("연결키 직접 입력 (고급)");manual.setOnClickListener(v->{entry.setVisibility(View.VISIBLE);open.setVisibility(View.VISIBLE);manual.setVisibility(View.GONE);});layout.addView(manual);setContentView(layout);
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
                Uri uri=request.getUrl();if(openMappingUri(uri))return true;if(!request.isForMainFrame()){return !("https".equals(uri.getScheme())&&(("ha.badara.co.kr".equals(uri.getHost())&&(uri.getPath().startsWith("/campsite-journal/")||uri.getPath().startsWith("/camp-ledger/")))||"postcode.map.kakao.com".equals(uri.getHost())||"postcode.map.daum.net".equals(uri.getHost())||"www.openstreetmap.org".equals(uri.getHost()))); }if("https".equals(uri.getScheme())&&"ha.badara.co.kr".equals(uri.getHost())&&(uri.getPath().startsWith("/campsite-journal/")||uri.getPath().startsWith("/camp-ledger/")))return false;
                try{startActivity(new Intent(Intent.ACTION_VIEW,uri));}catch(Exception ignored){}return true;
            }
            @Override public void onPageFinished(WebView view,String url){deliverPlatformPayload();}
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
    @Override protected void onActivityResult(int request,int result,Intent data){super.onActivityResult(request,result,data);
        if(request==901){platformConnecting=false;if(result==RESULT_OK&&data!=null){String name=data.getStringExtra("payload");if(name!=null&&name.matches("[a-f0-9-]{36}\\.json")){File file=new File(new File(getCacheDir(),"platform-sync"),name);try{if(file.length()>10*1024*1024)throw new IOException();try(InputStream in=new FileInputStream(file);ByteArrayOutputStream out=new ByteArrayOutputStream()){byte[] bytes=new byte[8192];int n;while((n=in.read(bytes))!=-1){if(out.size()+n>10*1024*1024)throw new IOException();out.write(bytes,0,n);}pendingPlatformPayload=new String(out.toByteArray(),"UTF-8");platformDeliveryAttempts=0;}deliverPlatformPayload();}catch(Exception unavailable){Toast.makeText(this,"동기화 내용을 읽지 못했습니다.",Toast.LENGTH_LONG).show();}finally{file.delete();}}}return;}
        if(request!=10||chooser==null)return;ValueCallback<Uri[]> pending=chooser;chooser=null;Uri[] uris=selectedUris(result,data);if(uris==null||!chooserPhotos){pending.onReceiveValue(uris);return;}
        new Thread(()->{ArrayList<Uri> copied=new ArrayList<>();for(Uri uri:uris)try{copied.add(cachePhoto(uri));}catch(Exception ignored){}runOnUiThread(()->{if(copied.isEmpty()){pending.onReceiveValue(null);Toast.makeText(this,"선택한 사진을 읽지 못했습니다. 파일 앱으로 다시 선택해주세요.",Toast.LENGTH_LONG).show();}else pending.onReceiveValue(copied.toArray(new Uri[0]));});},"campsite-journal-photos").start();
    }
    private void deliverPlatformPayload(){
        if(web==null||pendingPlatformPayload==null)return;String address=web.getUrl();if(address==null)return;Uri url=Uri.parse(address);if(!"https".equals(url.getScheme())||!"ha.badara.co.kr".equals(url.getHost())||!(url.getPath().startsWith("/campsite-journal/")||url.getPath().startsWith("/camp-ledger/")))return;
        String value=pendingPlatformPayload;
        web.evaluateJavascript("(function(raw){var message={type:'camp-platform-capture',payload:JSON.parse(raw)},sent=false;if(window.campPlatformSyncReady&&window.campAppReady){window.postMessage(message,location.origin);sent=true;}document.querySelectorAll('iframe').forEach(function(frame){try{if(frame.contentWindow.campPlatformSyncReady&&frame.contentWindow.campAppReady){frame.contentWindow.postMessage(message,location.origin);sent=true;}}catch(ignored){}});return sent;})("+org.json.JSONObject.quote(value)+")",result->{if("true".equals(result)&&value.equals(pendingPlatformPayload)){pendingPlatformPayload=null;}else if(++platformDeliveryAttempts<20&&web!=null){web.postDelayed(()->deliverPlatformPayload(),500);}});
    }
    @Override protected void onResume(){super.onResume();applySystemBars();if(updater!=null){updater.resumed();}}
    @Override public void onBackPressed(){if(web!=null&&web.canGoBack())web.goBack();else super.onBackPressed();}
    @Override protected void onDestroy(){if(web!=null)web.destroy();super.onDestroy();}
}
