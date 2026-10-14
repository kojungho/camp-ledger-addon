"""Commit revision notifications shared by ingress and external device clients."""
import hashlib,json,threading,time
from flask import Response,jsonify,request,stream_with_context

class LiveSync:
    def __init__(self,app,connection,release):
        self.connection=connection;self.release=release;self.condition=threading.Condition()
        with connection() as c:
            c.execute('CREATE TABLE IF NOT EXISTS ledger_revision(id INTEGER PRIMARY KEY,revision INTEGER NOT NULL)')
            c.execute('INSERT OR IGNORE INTO ledger_revision VALUES(1,0)')
            for table in ('items','attachments','settings'):
                for operation in ('INSERT','UPDATE','DELETE'):
                    c.execute(f'CREATE TRIGGER IF NOT EXISTS ledger_sync_{table}_{operation.lower()} AFTER {operation} ON {table} BEGIN UPDATE ledger_revision SET revision=revision+1 WHERE id=1; END')
        self.current=self.metadata()
        app.add_url_rule('/api/revision','ledger_revision',lambda:jsonify(self.refresh()))
        app.add_url_rule('/api/events','ledger_events',self.events)
        @app.after_request
        def published(response):
            if request.method in ('POST','PUT','DELETE') and 200<=response.status_code<300:self.refresh()
            return response
    def revision(self,c):return c.execute('SELECT revision FROM ledger_revision WHERE id=1').fetchone()[0]
    def settings_version(self,c):return hashlib.sha256(c.execute('SELECT body FROM settings WHERE id=1').fetchone()[0].encode()).hexdigest()
    def metadata(self):
        with self.connection() as c:return {'revision':self.revision(c),'release':self.release}
    def refresh(self):
        value=self.metadata()
        with self.condition:
            if value['revision']>self.current['revision'] or value['release']!=self.current['release']:
                self.current=value;self.condition.notify_all()
            return dict(self.current)
    def events(self):
        self.refresh()
        @stream_with_context
        def generate():
            seen=None;started=time.monotonic()
            yield 'retry: 1500\n\n'
            while time.monotonic()-started<540:
                with self.condition:
                    if seen==self.current:self.condition.wait(timeout=15)
                    value=dict(self.current)
                if value!=seen:
                    yield 'id: '+str(value['revision'])+'\nevent: change\ndata: '+json.dumps(value)+'\n\n';seen=value
                else:yield ': heartbeat\n\n'
        return Response(generate(),mimetype='text/event-stream',headers={'X-Accel-Buffering':'no','Cache-Control':'no-cache'})
