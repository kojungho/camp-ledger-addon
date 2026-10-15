"""Device access for the standalone app, isolated from HA Ingress administration."""
import base64, hashlib, io, json, os, secrets, time, uuid
from pathlib import Path
from urllib.parse import urlparse, quote
from flask import request, jsonify, abort, send_file
import qrcode

COOKIE='campsite_device'
DEFAULT_MOBILE={'enabled':False,'external_url':''}

def channel_app(app,channel):
    def entrypoint(environ,start_response):
        # This is set by the actual listener, never by Host or forwarded headers.
        environ['journal.entrypoint']=channel
        return app(environ,start_response)
    return entrypoint

def install_mobile(app, connection, get_settings, data_dir):
    with connection() as c:
        c.execute('CREATE TABLE IF NOT EXISTS devices(id TEXT PRIMARY KEY,name TEXT NOT NULL,token_hash TEXT NOT NULL UNIQUE,created REAL NOT NULL,last_used REAL)')

    def admin():
        port=str(request.environ.get('SERVER_PORT',''))
        channel=request.environ.get('journal.entrypoint') or ('external' if port=='8098' else 'ingress')
        if channel!='ingress': return False
        return os.environ.get('HA_INGRESS')!='1' or request.remote_addr=='172.30.32.2'

    def config(c): return {**DEFAULT_MOBILE,**get_settings(c).get('mobile',{})}

    def status():
        with connection() as c:
            prefs=config(c)
            devices=[dict(r) for r in c.execute('SELECT id,name,created,last_used FROM devices ORDER BY created DESC')] if admin() else []
        return {**prefs,'admin':admin(),'devices':devices,'apk_available':(Path(app.static_folder)/'downloads/campsite-journal.apk').exists()}

    def valid_key(key,c):
        if not isinstance(key,str) or len(key)<32 or len(key)>100: return None
        return c.execute('SELECT id,last_used FROM devices WHERE token_hash=?',(hashlib.sha256(key.encode()).hexdigest(),)).fetchone()

    def guard():
        if admin(): return None
        if request.environ.get('journal.entrypoint')!='external' and str(request.environ.get('SERVER_PORT'))!='8098': abort(403)
        public=request.path in ('/api/mobile/session','/api/mobile/health','/manifest.webmanifest','/service-worker.js') or request.path.startswith('/static/')
        if public: return None
        with connection() as c:
            prefs=config(c)
            key=request.cookies.get(COOKIE) or request.headers.get('Authorization','').removeprefix('Bearer ')
            device=valid_key(key,c) if prefs['enabled'] else None
            if not device:
                if request.path=='/': return app.send_static_file('mobile-connect.html')
                abort(401,description='애드온에서 이 기기를 연결해주세요.')
            if device['last_used'] is None or device['last_used']<time.time()-60:
                c.execute('UPDATE devices SET last_used=? WHERE id=?',(time.time(),device['id']))
        return None

    def require_admin():
        if not admin(): abort(403,description='이 설정은 Home Assistant 안에서만 변경할 수 있습니다.')

    @app.get('/api/mobile/health')
    def mobile_health(): return jsonify(service='campsite-journal',status='ready')

    @app.get('/api/mobile/status')
    def mobile_status(): return jsonify(status())

    @app.put('/api/mobile/config')
    def mobile_config():
        require_admin(); raw=request.get_json() or {}; url=raw.get('external_url','').strip()
        parsed=urlparse(url)
        if type(raw.get('enabled')) is not bool: raise ValueError('외부 앱 연결 설정을 확인해주세요.')
        if url and (parsed.scheme!='https' or not parsed.hostname or parsed.username or parsed.password or parsed.query or parsed.fragment): raise ValueError('HTTPS 주소만 입력해주세요.')
        if raw['enabled'] and not url: raise ValueError('외부 앱 주소를 입력해주세요.')
        url=url.rstrip('/')+'/' if url else ''
        with connection() as c:
            c.execute('BEGIN IMMEDIATE'); s=get_settings(c); s['mobile']={'enabled':raw['enabled'],'external_url':url}
            c.execute('UPDATE settings SET body=? WHERE id=1',(json.dumps(s,ensure_ascii=False),))
        return jsonify(status())

    @app.post('/api/mobile/devices')
    def mobile_device():
        require_admin(); name=(request.get_json() or {}).get('name','휴대폰')
        if not isinstance(name,str) or not name.strip() or len(name)>80: raise ValueError('기기 이름을 입력해주세요.')
        key=secrets.token_urlsafe(32); ident=str(uuid.uuid4())
        with connection() as c:
            prefs=config(c)
            if not prefs['enabled'] or not prefs['external_url']: raise ValueError('외부 앱 주소를 먼저 설정해주세요.')
            c.execute('INSERT INTO devices VALUES(?,?,?,?,NULL)',(ident,name.strip(),hashlib.sha256(key.encode()).hexdigest(),time.time()))
        link=prefs['external_url']+'#key='+key
        native='intent://connect?url='+quote(prefs['external_url'],safe='')+'#Intent;scheme=campsite-journal;package=co.kr.badara.campsitejournal;S.key='+key+';S.browser_fallback_url='+quote(link,safe='')+';end'
        qr=qrcode.make(native if (request.get_json() or {}).get('platform')=='android' else link); buf=io.BytesIO(); qr.save(buf,format='PNG')
        return jsonify(id=ident,name=name.strip(),token=key,url=prefs['external_url'],link=link,native=native,qr='data:image/png;base64,'+base64.b64encode(buf.getvalue()).decode())

    @app.post('/api/mobile/devices/<ident>/revoke')
    def mobile_revoke(ident):
        require_admin()
        with connection() as c: c.execute('DELETE FROM devices WHERE id=?',(ident,))
        return jsonify(ok=True)

    @app.post('/api/mobile/session')
    def mobile_session():
        raw=request.get_json() or {}; key=raw.get('key')
        with connection() as c:
            prefs=config(c)
            if not prefs['enabled'] or not valid_key(key,c): abort(401,description='연결키가 만료되었거나 해제되었습니다. 애드온에서 다시 연결해주세요.')
        response=jsonify(ok=True)
        response.set_cookie(COOKIE,key,max_age=60*60*24*365*5,secure=True,httponly=True,samesite='Strict',path=urlparse(prefs['external_url']).path or '/')
        return response

    @app.get('/api/mobile/apk')
    def mobile_apk():
        require_admin()
        path=Path(app.static_folder)/'downloads/campsite-journal.apk'
        if not path.exists(): abort(404,description='설치 파일을 준비 중입니다.')
        return send_file(path,as_attachment=True,download_name='campsite-journal.apk',mimetype='application/vnd.android.package-archive')

    @app.get('/api/mobile/bridge')
    def mobile_bridge():
        require_admin()
        return send_file(Path(app.static_folder)/'downloads/campsite-journal-bridge.zip',as_attachment=True,download_name='campsite-journal-bridge.zip')

    @app.get('/manifest.webmanifest')
    def manifest():
        return jsonify(name='캠핑 노트',short_name='캠핑 노트',id='./',start_url='./hub',scope='./',display='standalone',background_color='#f6f7f2',theme_color='#285345',icons=[{'src':'static/icons/icon-192.png','sizes':'192x192','type':'image/png','purpose':'any'},{'src':'static/icons/icon-512.png','sizes':'512x512','type':'image/png','purpose':'any maskable'}])

    @app.get('/service-worker.js')
    def worker(): return send_file(Path(app.static_folder)/'service-worker.js',mimetype='application/javascript')

    return {'guard':guard,'admin':admin,'status':status,'config':config}
