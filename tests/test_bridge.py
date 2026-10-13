"""Exercise the custom route with a real HTTP upstream, without a HA installation."""
import importlib.util,sys,types,unittest
from pathlib import Path
from unittest.mock import patch
from aiohttp import web,ClientSession,DummyCookieJar
from aiohttp.test_utils import TestServer,TestClient

modules={name:types.ModuleType(name) for name in ('homeassistant','homeassistant.components','homeassistant.components.http','homeassistant.const','homeassistant.helpers','homeassistant.helpers.config_validation')}
modules['homeassistant.components.http'].HomeAssistantView=object
modules['homeassistant.const'].EVENT_HOMEASSISTANT_STOP='stop'
modules['homeassistant.helpers.config_validation'].url=lambda value:value
with patch.dict(sys.modules,modules):
    spec=importlib.util.spec_from_file_location('ledger_bridge',Path(__file__).resolve().parents[1]/'custom_components/camp_ledger_bridge/__init__.py')
    bridge=importlib.util.module_from_spec(spec);spec.loader.exec_module(bridge)

class BridgeTests(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        async def echo(request):
            response=web.json_response({'path':request.path,'query':request.query_string,'cookie':request.headers.get('Cookie',''),'authorization':request.headers.get('Authorization',''),'body':(await request.read()).decode()})
            response.set_cookie('upstream_cookie','must-not-be-shared')
            return response
        app=web.Application();app.router.add_route('*','/{tail:.*}',echo)
        self.backend=TestServer(app);await self.backend.start_server()
        self.session=ClientSession(cookie_jar=DummyCookieJar())
        self.view=bridge.LedgerView(None,str(self.backend.make_url('')).rstrip('/'),self.session)
        async def delegate(request):return await self.view.handle(request,**request.match_info)
        proxy=web.Application();proxy.router.add_route('*','/camp-ledger',delegate);proxy.router.add_route('*','/camp-ledger/',delegate);proxy.router.add_route('*','/camp-ledger/{tail:.*}',delegate)
        self.client=TestClient(TestServer(proxy),cookie_jar=DummyCookieJar());await self.client.start_server()
    async def asyncTearDown(self):
        await self.client.close();await self.session.close();await self.backend.close()
    async def test_scoped_proxy_and_cookie_isolation(self):
        key='A'*43
        r=await self.client.post('/camp-ledger/api/items?one=1',headers={'Cookie':'camp_device='+key+'; unrelated_ha_cookie=private','Authorization':'Bearer unrelated_ha_token','X-Camp-Request':'1','Content-Type':'application/json'},data='{"name":"gear"}')
        x=await r.json();self.assertEqual(x['path'],'/api/items');self.assertEqual(x['query'],'one=1');self.assertEqual(x['cookie'],'camp_device='+key);self.assertEqual(x['authorization'],'');self.assertEqual(x['body'],'{"name":"gear"}')
        self.assertIn('upstream_cookie',r.headers.get('Set-Cookie',''))
        r=await self.client.get('/camp-ledger/api/state');self.assertEqual((await r.json())['cookie'],'')
        self.assertFalse(list(self.session.cookie_jar))
        r=await self.client.get('/unrelated-ha-path');self.assertEqual(r.status,404)
        r=await self.client.get('/camp-ledger',allow_redirects=False);self.assertEqual(r.status,308);self.assertEqual(r.headers['Location'],'/camp-ledger/')
    async def test_reject_traversal(self):
        # Raw escaped traversal is rejected rather than becoming an unrelated HA request.
        r=await self.client.get('/camp-ledger/%2E%2E/api/state');self.assertIn(r.status,(400,404))

if __name__=='__main__':unittest.main()
