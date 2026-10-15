package co.kr.badara.campsitejournal;

import android.content.ContentProvider;
import android.content.ContentValues;
import android.database.Cursor;
import android.database.MatrixCursor;
import android.net.Uri;
import android.os.ParcelFileDescriptor;
import android.provider.OpenableColumns;
import android.webkit.MimeTypeMap;
import java.io.File;
import java.io.FileNotFoundException;

public final class LedgerFileProvider extends ContentProvider {
    @Override public boolean onCreate(){return true;}
    private File file(Uri uri) throws FileNotFoundException {
        String group=uri.getPathSegments().size()==2?uri.getPathSegments().get(0):"",name=uri.getLastPathSegment();
        if(!uri.getAuthority().equals(getContext().getPackageName()+".files")||name==null||name.contains("/")||name.equals("..")||name.equals(".")||!("photos".equals(group)||("updates".equals(group)&&"campsite-journal.apk".equals(name))))throw new FileNotFoundException();
        File result=new File(new File(getContext().getCacheDir(),group),name);if(!result.isFile())throw new FileNotFoundException();return result;
    }
    public static Uri uri(android.content.Context context,String group,File file){return new Uri.Builder().scheme("content").authority(context.getPackageName()+".files").appendPath(group).appendPath(file.getName()).build();}
    @Override public ParcelFileDescriptor openFile(Uri uri,String mode) throws FileNotFoundException {if(!"r".equals(mode))throw new FileNotFoundException();return ParcelFileDescriptor.open(file(uri),ParcelFileDescriptor.MODE_READ_ONLY);}
    @Override public String getType(Uri uri){String name=uri.getLastPathSegment();if(name!=null&&name.endsWith(".apk"))return "application/vnd.android.package-archive";String ext=name!=null&&name.contains(".")?name.substring(name.lastIndexOf('.')+1).toLowerCase():"";String type=MimeTypeMap.getSingleton().getMimeTypeFromExtension(ext);return type==null?"application/octet-stream":type;}
    @Override public Cursor query(Uri uri,String[] projection,String selection,String[] args,String sort){try{File f=file(uri);String[] columns=projection==null?new String[]{OpenableColumns.DISPLAY_NAME,OpenableColumns.SIZE}:projection;MatrixCursor result=new MatrixCursor(columns);Object[] row=new Object[columns.length];for(int i=0;i<columns.length;i++){if(OpenableColumns.DISPLAY_NAME.equals(columns[i]))row[i]=f.getParentFile().getName().equals("photos")&&f.getName().length()>37?f.getName().substring(37):f.getName();else if(OpenableColumns.SIZE.equals(columns[i]))row[i]=f.length();}result.addRow(row);return result;}catch(Exception e){return null;}}
    @Override public Uri insert(Uri uri,ContentValues values){throw new UnsupportedOperationException();}
    @Override public int delete(Uri uri,String selection,String[] args){throw new UnsupportedOperationException();}
    @Override public int update(Uri uri,ContentValues values,String selection,String[] args){throw new UnsupportedOperationException();}
}
