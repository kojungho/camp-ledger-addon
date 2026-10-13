package co.kr.badara.campledger;

import android.app.Activity;
import android.app.DownloadManager;
import android.content.Context;
import android.content.Intent;
import android.content.SharedPreferences;
import android.graphics.Color;
import android.net.Uri;
import android.os.Bundle;
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
    private static final String BASE="https://ha.badara.co.kr/camp-ledger/";
    
    private static final String ALIAS="camp-ledger-device-key";
    private WebView web;
    private ValueCallback<Uri[]> chooser;
    private String key;
    private SharedPreferences prefs;

    @Override public void onCreate(Bundle state) {
        super.onCreate(state);
        prefs=getSharedPreferences("camp-ledger",MODE_PRIVATE);
        try {key=readKey();} catch(Exception e) {key=null;}
        handleIntent(getIntent());
        if(key==null)showConnect(); else showLedger();
    }
    @Override protected void onNewIntent(Intent intent) {
        super.onNewIntent(intent);setIntent(intent);handleIntent(intent);
        if(key!=null)showLedger();
    }
    private void handleIntent(Intent intent) {
        Uri uri=intent.getData();
        if(uri==null||!"camp-ledger".equals(uri.getScheme())||!"connect".equals(uri.getHost()))return;
        String url=uri.getQueryParameter("url");
        String value=intent.getStringExtra("key");
        if(value==null)value=Uri.parse("https://local/?"+(uri.getFragment()==null?"":uri.getFragment())).getQueryParameter("key");
        if(!BASE.equals(url)||value==null||!value.matches("[A-Za-z0-9_-]{40,100}")) {
            Toast.makeText(this,"장부 설정에서 만든 연결 주소를 사용해주세요.",Toast.LENGTH_LONG).show();return;
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
        TextView title=new TextView(this);title.setText("△  캠핑 장부");title.setTextSize(28);title.setTextColor(Color.rgb(40,83,69));layout.addView(title);
        TextView text=new TextView(this);text.setText("처음 한 번만 기기를 연결하세요.\n\n장부의 앱 설치·연결에서 만든 연결키를 붙여넣으면, 이후에는 이 앱에서 장부만 바로 열립니다.");text.setTextSize(16);text.setPadding(0,32,0,32);layout.addView(text);
        EditText entry=new EditText(this);entry.setHint("기기 연결키 붙여넣기");entry.setSingleLine(true);entry.setInputType(android.text.InputType.TYPE_CLASS_TEXT|android.text.InputType.TYPE_TEXT_VARIATION_PASSWORD);layout.addView(entry);
        Button open=new Button(this);open.setText("장부 연결");open.setOnClickListener(v->{String value=entry.getText().toString().trim();if(!value.matches("[A-Za-z0-9_-]{40,100}")){entry.setError("장부에서 만든 연결키를 붙여넣어주세요.");return;}try{saveKey(value);key=value;showLedger();}catch(Exception e){entry.setError("연결 정보를 저장하지 못했습니다.");}});layout.addView(open);setContentView(layout);
    }
    private void showLedger() {
        if(web!=null)web.destroy();web=new WebView(this);web.setBackgroundColor(Color.rgb(246,247,242));
        web.setOnApplyWindowInsetsListener((v,insets)->{v.setPadding(insets.getSystemWindowInsetLeft(),insets.getSystemWindowInsetTop(),insets.getSystemWindowInsetRight(),insets.getSystemWindowInsetBottom());return insets;});
        WebSettings settings=web.getSettings();settings.setJavaScriptEnabled(true);settings.setDomStorageEnabled(true);settings.setAllowFileAccess(false);settings.setAllowContentAccess(true);settings.setGeolocationEnabled(false);settings.setMixedContentMode(WebSettings.MIXED_CONTENT_NEVER_ALLOW);settings.setSafeBrowsingEnabled(true);
        CookieManager cookies=CookieManager.getInstance();cookies.setAcceptCookie(true);cookies.setAcceptThirdPartyCookies(web,false);
        web.setWebViewClient(new WebViewClient(){
            @Override public boolean shouldOverrideUrlLoading(WebView view,WebResourceRequest request){
                Uri uri=request.getUrl();if("https".equals(uri.getScheme())&&"ha.badara.co.kr".equals(uri.getHost())&&uri.getPath().startsWith("/camp-ledger/"))return false;
                try{startActivity(new Intent(Intent.ACTION_VIEW,uri));}catch(Exception ignored){}return true;
            }
            @Override public void onReceivedError(WebView view,WebResourceRequest request,WebResourceError error){if(request.isForMainFrame())Toast.makeText(MainActivity.this,"장부에 연결하지 못했습니다. 인터넷 연결을 확인해주세요.",Toast.LENGTH_LONG).show();}
        });
        web.setWebChromeClient(new WebChromeClient(){
            @Override public boolean onShowFileChooser(WebView view,ValueCallback<Uri[]> callback,FileChooserParams params){
                if(chooser!=null)chooser.onReceiveValue(null);chooser=callback;
                Intent select=new Intent(Intent.ACTION_OPEN_DOCUMENT);select.addCategory(Intent.CATEGORY_OPENABLE);select.setType("*/*");select.putExtra(Intent.EXTRA_ALLOW_MULTIPLE,params.getMode()==FileChooserParams.MODE_OPEN_MULTIPLE);
                try{startActivityForResult(select,10);}catch(Exception e){chooser.onReceiveValue(null);chooser=null;}return true;
            }
        });
        web.setDownloadListener((url,agent,disposition,mime,length)->{
            Uri uri=Uri.parse(url);if(!"https".equals(uri.getScheme())||!"ha.badara.co.kr".equals(uri.getHost())||!uri.getPath().startsWith("/camp-ledger/"))return;
            try{DownloadManager.Request download=new DownloadManager.Request(uri);download.addRequestHeader("Cookie",CookieManager.getInstance().getCookie(url));download.setNotificationVisibility(DownloadManager.Request.VISIBILITY_VISIBLE_NOTIFY_COMPLETED);download.setMimeType(mime);String name=android.webkit.URLUtil.guessFileName(url,disposition,mime);download.setDestinationInExternalPublicDir(Environment.DIRECTORY_DOWNLOADS,name);((DownloadManager)getSystemService(Context.DOWNLOAD_SERVICE)).enqueue(download);Toast.makeText(this,"다운로드를 시작했습니다.",Toast.LENGTH_SHORT).show();}catch(Exception e){Toast.makeText(this,"다운로드하지 못했습니다.",Toast.LENGTH_LONG).show();}
        });
        setContentView(web);
        cookies.setCookie(BASE,"camp_device="+key+"; Path=/camp-ledger/; Max-Age=157680000; Secure; HttpOnly; SameSite=Strict",value->{cookies.flush();web.loadUrl(BASE);});
    }
    @Override protected void onActivityResult(int request,int result,Intent data){super.onActivityResult(request,result,data);if(request==10&&chooser!=null){chooser.onReceiveValue(WebChromeClient.FileChooserParams.parseResult(result,data));chooser=null;}}
    @Override public void onBackPressed(){if(web!=null&&web.canGoBack())web.goBack();else super.onBackPressed();}
    @Override protected void onDestroy(){if(web!=null)web.destroy();super.onDestroy();}
}
