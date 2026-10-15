"""Shared invalidation stream for Ingress and paired devices."""
import threading
CONDITION=threading.Condition();revision=0

def publish():
 global revision
 with CONDITION:
  revision+=1;CONDITION.notify_all()
 return revision

def events():
 with CONDITION:current=revision
 yield f'event: ready\ndata: {current}\n\n'
 while True:
  with CONDITION:
   CONDITION.wait_for(lambda:revision!=current,timeout=15)
   changed=revision!=current;current=revision
  yield f'event: change\ndata: {current}\n\n' if changed else ': keepalive\n\n'
