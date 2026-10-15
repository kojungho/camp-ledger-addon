self.addEventListener('install',()=>self.skipWaiting());
self.addEventListener('activate',e=>e.waitUntil(self.clients.claim()));
// Sensitive journal responses are never cached for offline access.
self.addEventListener('fetch',()=>{});
