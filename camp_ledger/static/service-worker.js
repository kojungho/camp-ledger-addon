'use strict';
self.addEventListener('install',()=>self.skipWaiting());
self.addEventListener('activate',event=>event.waitUntil(self.clients.claim()));
// Financial records and photos are always read from the server, without an offline cache.
self.addEventListener('fetch',()=>{});
