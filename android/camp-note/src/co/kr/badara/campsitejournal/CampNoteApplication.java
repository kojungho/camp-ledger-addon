package co.kr.badara.campsitejournal;
import android.app.Application;
import android.webkit.WebView;
/** Separate persistent cookie/storage directories for the two platform accounts. */
public final class CampNoteApplication extends Application {
 @Override public void onCreate(){super.onCreate();String process=Application.getProcessName();if(process.endsWith(":platform_account_1"))WebView.setDataDirectorySuffix("platform-account-1");else if(process.endsWith(":platform_account_2"))WebView.setDataDirectorySuffix("platform-account-2");}
}
