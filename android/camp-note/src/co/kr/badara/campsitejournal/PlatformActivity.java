package co.kr.badara.campsitejournal;

import android.app.Activity;
import android.app.AlertDialog;
import android.app.Dialog;
import android.content.Intent;
import android.graphics.Bitmap;
import android.graphics.BitmapFactory;
import android.net.Uri;
import android.os.Bundle;
import android.util.Base64;
import android.webkit.*;
import android.widget.*;
import org.json.*;
import java.io.*;
import java.net.URL;
import java.net.InetAddress;
import java.net.HttpURLConnection;
import java.util.UUID;
import java.util.HashSet;
import java.util.Set;
import java.security.MessageDigest;

/** Separate unprivileged browser. No account password or cookie is sent to HA. */
public class PlatformActivity extends Activity {
 private WebView browser;private TextView status;private Button sync;private String provider,domain,home;private int account=1;private String accountLabel="계정 1";private boolean busy=false,scanning=false;private int scanGeneration=0;private Set<String> knownIds=new HashSet<>(),knownHashes=new HashSet<>();
 @Override public void onCreate(Bundle state){
  super.onCreate(state);account=android.app.Application.getProcessName().endsWith(":platform_account_2")?2:1;provider=getIntent().getStringExtra("provider");
  if("camfit".equals(provider)){domain="camfit.co.kr";home="https://camfit.co.kr/";}
  else if("thankq".equals(provider)){domain="thankqcamping.com";home="https://m.thankqcamping.com/";}
  else if("campingtalk".equals(provider)){domain="campingtalk.me";home="https://www.campingtalk.me/member/reservationList";}
  else if("naver".equals(provider)){domain="naver.com";home="https://my.naver.com/?cat=reservation&subCat=booking";}
  else{finish();return;}
  try{JSONObject history=new JSONObject(getIntent().getStringExtra("history"));accountLabel=history.optString("label","계정 "+account);loadKnown(history.optJSONArray("booking_ids"),knownIds);loadKnown(history.optJSONArray("text_hashes"),knownHashes);}catch(Exception unavailable){}
  LinearLayout root=new LinearLayout(this);root.setOrientation(1);root.setBackgroundColor(0xfffafbf7);root.setOnApplyWindowInsetsListener((v,insets)->{root.setPadding(insets.getSystemWindowInsetLeft(),insets.getSystemWindowInsetTop(),insets.getSystemWindowInsetRight(),insets.getSystemWindowInsetBottom());return insets;});
  LinearLayout bar=new LinearLayout(this);Button close=new Button(this);close.setText("닫기");close.setOnClickListener(v->finish());bar.addView(close);Button top=new Button(this);top.setText("플랫폼 홈");top.setOnClickListener(v->browser.loadUrl(home));bar.addView(top);sync=new Button(this);sync.setText("현재 예약 동기화");sync.setOnClickListener(v->{if(scanning)cancelScan();else capture();});bar.addView(sync);root.addView(bar);
  status=new TextView(this);status.setPadding(16,8,16,8);status.setText(accountLabel+" · 직접 로그인하고 예약 내역을 열어주세요. 동기화를 눌렀을 때만 현재 페이지 아래쪽까지 스크롤하며 예약을 읽고 선택창을 엽니다. 다음 페이지·다른 예약 탭은 직접 열어 동기화하세요.");root.addView(status);
  // The window decor must exist before asking PhoneWindow for its insets controller.
  setContentView(root);
  if(android.os.Build.VERSION.SDK_INT>=30){android.view.WindowInsetsController bars=getWindow().getInsetsController();if(bars!=null)bars.setSystemBarsAppearance(android.view.WindowInsetsController.APPEARANCE_LIGHT_STATUS_BARS|android.view.WindowInsetsController.APPEARANCE_LIGHT_NAVIGATION_BARS,android.view.WindowInsetsController.APPEARANCE_LIGHT_STATUS_BARS|android.view.WindowInsetsController.APPEARANCE_LIGHT_NAVIGATION_BARS);}else getWindow().getDecorView().setSystemUiVisibility(android.view.View.SYSTEM_UI_FLAG_LIGHT_STATUS_BAR|android.view.View.SYSTEM_UI_FLAG_LIGHT_NAVIGATION_BAR);
  try{browser=createBrowser();root.addView(browser,new LinearLayout.LayoutParams(-1,0,1));browser.loadUrl(home);}catch(RuntimeException error){android.util.Log.e("CampNotePlatform","Platform browser initialization failed",error);sync.setEnabled(false);top.setEnabled(false);status.setText("플랫폼 화면을 열 수 없습니다. Android System WebView와 Chrome을 업데이트한 뒤 다시 열어주세요.");}
 }
 private WebView createBrowser(){
  WebView view=new WebView(this);view.setOnTouchListener((v,event)->busy);WebSettings settings=view.getSettings();settings.setJavaScriptEnabled(true);settings.setDomStorageEnabled(true);settings.setAllowFileAccess(false);settings.setAllowContentAccess(false);settings.setMixedContentMode(WebSettings.MIXED_CONTENT_NEVER_ALLOW);settings.setSafeBrowsingEnabled(true);settings.setSupportMultipleWindows(true);
  CookieManager.getInstance().setAcceptCookie(true);CookieManager.getInstance().setAcceptThirdPartyCookies(view,false);
  // Intentionally no JavascriptInterface on platform or authentication pages.
  view.setWebViewClient(new WebViewClient(){@Override public boolean shouldOverrideUrlLoading(WebView current,WebResourceRequest request){return !"https".equals(request.getUrl().getScheme());}});
  view.setWebChromeClient(new WebChromeClient(){@Override public boolean onCreateWindow(WebView current,boolean dialog,boolean gesture,android.os.Message message){if(!gesture)return false;WebView popup=createBrowser();Dialog box=new Dialog(PlatformActivity.this);box.setContentView(popup);box.setOnDismissListener(d->{popup.destroy();CookieManager.getInstance().flush();});box.show();box.getWindow().setLayout(-1,-1);popup.setWebChromeClient(new WebChromeClient(){@Override public void onCloseWindow(WebView child){box.dismiss();}});WebView.WebViewTransport transport=(WebView.WebViewTransport)message.obj;transport.setWebView(popup);message.sendToTarget();return true;}});
  return view;
 }
 private boolean platformHost(String host){return host!=null&&(host.equals(domain)||host.endsWith("."+domain));}
 private void cancelScan(){scanGeneration++;scanning=false;browser.evaluateJavascript("window.__campNoteReservationScan&&window.__campNoteReservationScan.cancel()",null);done("예약 읽기를 중지했습니다. 저장된 기록은 변경되지 않았습니다.");}
 private void capture(){
  if(busy)return;Uri url=Uri.parse(browser.getUrl()==null?"":browser.getUrl());if(!platformHost(url.getHost())||!"https".equals(url.getScheme())){status.setText("플랫폼 로그인을 완료한 뒤 예약 화면에서 동기화를 눌러주세요.");return;}
  busy=true;scanning=true;sync.setText("읽기 중지");sync.setEnabled(true);status.setText("현재 페이지의 아래쪽 예약도 스크롤하며 읽고 있습니다…");final int generation=++scanGeneration;
  try{String capture=new String(read(getAssets().open("platform-capture.js"),100000),"UTF-8"),scroll=new String(read(getAssets().open("platform-scroll.js"),100000),"UTF-8");String script="(function(){window.__campNoteReservationScan="+scroll+"(function(){return "+capture+"});return window.__campNoteReservationScan.step();})()";pollScan(script,generation,0);
  }catch(Exception error){done("동기화 구성요소를 읽지 못했습니다.");}
 }
 private void pollScan(String script,int generation,int attempts){
  if(generation!=scanGeneration||isFinishing()||!scanning)return;
  if(attempts>285){cancelScan();return;}
  browser.evaluateJavascript(script,value->{if(generation!=scanGeneration||isFinishing())return;try{
   Object decoded=new JSONTokener(value).nextValue();if(!(decoded instanceof String))throw new IOException();JSONObject payload=new JSONObject((String)decoded);if(payload.has("error")){done(payload.getString("error"));return;}
   JSONArray batch=payload.optJSONArray("batch");if(batch!=null)for(int i=0;i<batch.length();i++)if(alreadySynced(batch.getJSONObject(i))){pollScan("window.__campNoteReservationScan.stopAtSynced("+i+")",generation,attempts+1);return;}
   if(!payload.optBoolean("done")){status.setText("아래쪽 예약을 읽고 있습니다… "+payload.optInt("count")+"건 · 중지 가능");browser.postDelayed(()->pollScan("window.__campNoteReservationScan?window.__campNoteReservationScan.step():JSON.stringify({error:'페이지가 다시 열렸습니다. 예약 화면이 로드된 뒤 동기화해주세요.'})",generation,attempts+1),700);return;}
   scanning=false;sync.setEnabled(false);sync.setText("사진 읽는 중");status.setText("예약 "+payload.getJSONArray("cards").length()+"건의 사진을 준비하고 있습니다…");payload.put("provider",provider);payload.put("account",account);new Thread(()->prepare(payload),"camp-platform-photos").start();
  }catch(Exception error){done("예약 내용을 읽지 못했습니다. 예약 화면이 열린 상태인지 확인해주세요.");}});
 }
 private byte[] read(InputStream input,int limit)throws IOException{try(InputStream in=input;ByteArrayOutputStream out=new ByteArrayOutputStream()){byte[] buf=new byte[8192];int n;while((n=in.read(buf))!=-1){if(out.size()+n>limit)throw new IOException();out.write(buf,0,n);}return out.toByteArray();}}
 private byte[] photo(String address)throws Exception{
  URL url=new URL(address);byte[] raw=null;
  for(int redirect=0;redirect<4;redirect++){
   if(!"https".equals(url.getProtocol())||url.getUserInfo()!=null||(url.getPort()!=-1&&url.getPort()!=443)||"ha.badara.co.kr".equalsIgnoreCase(url.getHost()))throw new IOException();
   for(InetAddress ip:InetAddress.getAllByName(url.getHost()))if(ip.isAnyLocalAddress()||ip.isLoopbackAddress()||ip.isSiteLocalAddress()||ip.isLinkLocalAddress()||ip.isMulticastAddress())throw new IOException();
   HttpURLConnection c=(HttpURLConnection)url.openConnection();c.setConnectTimeout(8000);c.setReadTimeout(10000);c.setInstanceFollowRedirects(false);
   if(platformHost(url.getHost())){String cookie=CookieManager.getInstance().getCookie(url.toString());if(cookie!=null)c.setRequestProperty("Cookie",cookie);}
   try{int code=c.getResponseCode();if(code>=300&&code<400){String location=c.getHeaderField("Location");if(location==null)throw new IOException();url=new URL(url,location);continue;}if(code!=200)throw new IOException();String type=c.getContentType();if(type==null||!type.startsWith("image/"))throw new IOException();raw=read(c.getInputStream(),8*1024*1024);break;}finally{c.disconnect();}
  }
  if(raw==null)throw new IOException();BitmapFactory.Options bounds=new BitmapFactory.Options();bounds.inJustDecodeBounds=true;BitmapFactory.decodeByteArray(raw,0,raw.length,bounds);if(bounds.outWidth<=0||bounds.outHeight<=0||(long)bounds.outWidth*bounds.outHeight>25000000)throw new IOException();BitmapFactory.Options options=new BitmapFactory.Options();while(Math.max(bounds.outWidth,bounds.outHeight)/Math.max(1,options.inSampleSize)>1600)options.inSampleSize=Math.max(1,options.inSampleSize)*2;Bitmap image=BitmapFactory.decodeByteArray(raw,0,raw.length,options);if(image==null)throw new IOException();ByteArrayOutputStream out=new ByteArrayOutputStream();image.compress(Bitmap.CompressFormat.JPEG,88,out);image.recycle();if(out.size()>1500000)throw new IOException();return out.toByteArray();
 }
 private void loadKnown(JSONArray values,Set<String> target)throws JSONException{if(values!=null)for(int i=0;i<values.length();i++){String value=values.getString(i);if(value.length()<=80)target.add(value);}}
 private String textHash(String text)throws Exception{byte[] hash=MessageDigest.getInstance("SHA-256").digest(text.getBytes("UTF-8"));StringBuilder value=new StringBuilder();for(byte b:hash)value.append(String.format("%02x",b&255));return value.toString();}
 private boolean alreadySynced(JSONObject card)throws Exception{
  String text=card.optString("text","");java.util.regex.Matcher id=java.util.regex.Pattern.compile("예약\\s*(?:번호|코드)\\s*[:：#]?\\s*([A-Za-z0-9][A-Za-z0-9_-]{4,79})").matcher(text);
  // Do not skip a combined page just because its first reservation is known.
  if(card.optBoolean("single_card",false)&&id.find()){String value=id.group(1);if(!id.find()&&knownIds.contains(value))return true;}
  return knownHashes.contains(textHash(text));
 }
 private void prepare(JSONObject payload){
  try{JSONArray cards=payload.getJSONArray("cards");if(cards.length()>100)throw new IOException();int total=0,skipped=payload.optInt("already_synced",0);JSONArray fresh=new JSONArray();long deadline=System.currentTimeMillis()+45000;
   for(int i=0;i<cards.length();i++){JSONObject card=cards.getJSONObject(i);if(!card.optBoolean("cancelled")&&alreadySynced(card)){skipped++;continue;}JSONArray candidates=card.optJSONArray("media"),kept=new JSONArray();if(!card.optBoolean("cancelled")&&candidates!=null)for(int j=0;j<Math.min(4,candidates.length())&&System.currentTimeMillis()<deadline;j++)try{JSONObject candidate=candidates.getJSONObject(j);String kind=candidate.getString("kind");if(!"gallery".equals(kind)&&!"layout".equals(kind))continue;byte[] bytes=photo(candidate.getString("url"));if(total+bytes.length>4*1024*1024)continue;total+=bytes.length;kept.put(new JSONObject().put("kind",kind).put("data","data:image/jpeg;base64,"+Base64.encodeToString(bytes,Base64.NO_WRAP)));}catch(Exception unavailable){}card.put("media",kept);fresh.put(card);}
   payload.remove("batch");payload.put("cards",fresh);payload.put("already_synced",skipped);
   if(isFinishing())return;File dir=new File(getCacheDir(),"platform-sync");dir.mkdirs();File[] old=dir.listFiles();if(old!=null)for(File f:old)if(f.isFile()&&System.currentTimeMillis()-f.lastModified()>86400000L)f.delete();File file=new File(dir,UUID.randomUUID().toString()+".json");byte[] content=payload.toString().getBytes("UTF-8");if(content.length>10*1024*1024)throw new IOException();try(OutputStream out=new FileOutputStream(file)){out.write(content);}CookieManager.getInstance().flush();runOnUiThread(()->{setResult(RESULT_OK,new Intent().putExtra("payload",file.getName()));finish();});
  }catch(Exception error){done("사진을 가져오지 못했습니다. 예약 화면에서 다시 시도해주세요.");}
 }
 private void done(String message){runOnUiThread(()->{if(scanning&&browser!=null&&!isFinishing())browser.evaluateJavascript("window.__campNoteReservationScan&&window.__campNoteReservationScan.cancel()",null);busy=false;scanning=false;sync.setEnabled(true);sync.setText("현재 예약 동기화");status.setText(message);});}
 @Override public void onBackPressed(){if(scanning){cancelScan();return;}if(busy)return;if(browser!=null&&browser.canGoBack())browser.goBack();else finish();}
 @Override protected void onPause(){CookieManager.getInstance().flush();super.onPause();}
 @Override protected void onDestroy(){scanGeneration++;if(browser!=null)browser.destroy();super.onDestroy();}
}
