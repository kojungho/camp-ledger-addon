"""Forward only the camping-ledger path; device authorization remains in the app."""
from aiohttp import web, ClientError, ClientTimeout, ClientSession, DummyCookieJar
import re
from homeassistant.components.http import HomeAssistantView
from homeassistant.const import EVENT_HOMEASSISTANT_STOP
import voluptuous as vol
from homeassistant.helpers import config_validation as cv

DOMAIN='camp_ledger_bridge'
DEFAULT_BACKEND='http://5ec8f074-camp-ledger:8098'
CONFIG_SCHEMA=vol.Schema({DOMAIN:vol.Schema({vol.Optional('backend_url',default=DEFAULT_BACKEND):cv.url})},extra=vol.ALLOW_EXTRA)

async def async_setup(hass, config):
    opts=config.get(DOMAIN) or {}
    backend=opts.get('backend_url',DEFAULT_BACKEND).rstrip('/')
    session=ClientSession(cookie_jar=DummyCookieJar(),timeout=ClientTimeout(total=600))
    async def close_session(event): await session.close()
    hass.bus.async_listen_once(EVENT_HOMEASSISTANT_STOP,close_session)
    hass.http.register_view(LedgerView(hass,backend,session))
    return True

class LedgerView(HomeAssistantView):
    url='/camp-ledger'
    extra_urls=['/camp-ledger/','/camp-ledger/{tail:.*}']
    name='camp_ledger_bridge:proxy'
    requires_auth=False

    def __init__(self,hass,backend,session):self.hass=hass;self.backend=backend;self.session=session

    async def handle(self,request,tail=''):
        if request.path=='/camp-ledger':raise web.HTTPPermanentRedirect('/camp-ledger/')
        # Never proxy unrelated HA paths, management APIs or user-supplied destinations.
        if tail.startswith('/') or '..' in tail.split('/') or '\\' in tail:return web.Response(status=400)
        headers={k:request.headers[k] for k in ('Content-Type','X-Camp-Request','Accept') if k in request.headers}
        cookie=request.cookies.get('camp_device','')
        if re.fullmatch(r'[A-Za-z0-9_-]{40,100}',cookie):headers['Cookie']='camp_device='+cookie
        url=self.backend+'/'+tail
        if request.query_string:url+='?'+request.query_string
        session=self.session
        body=request.content.iter_chunked(65536) if request.can_read_body else None
        try:
            async with session.request(request.method,url,headers=headers,data=body,allow_redirects=False,timeout=ClientTimeout(total=600)) as upstream:
                out={k:v for k,v in upstream.headers.items() if k.lower() not in ('connection','transfer-encoding','content-length','content-encoding','keep-alive')}
                if 'Location' in out and out['Location'].startswith('/'):out['Location']='/camp-ledger'+out['Location']
                response=web.StreamResponse(status=upstream.status,headers=out)
                await response.prepare(request)
                async for chunk in upstream.content.iter_chunked(65536):await response.write(chunk)
                await response.write_eof()
                return response
        except (ClientError,TimeoutError):
            return web.Response(status=503,text='캠핑 장부를 시작한 뒤 다시 열어주세요.',content_type='text/plain')

    get=handle
    post=handle
    put=handle
    delete=handle
    options=handle
