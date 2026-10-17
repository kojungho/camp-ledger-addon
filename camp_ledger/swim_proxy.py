"""Authenticated bridge to this installation's existing reservation add-on."""
import http.client
import socket
from urllib.parse import unquote
from flask import Response, abort, request, stream_with_context

HOST = '76980dac-swim-reservation'
PORT = 8099
MAX_BODY = 64 * 1024 * 1024
RESPONSE_HEADERS = {'content-type', 'content-disposition', 'etag', 'last-modified', 'accept-ranges', 'content-range'}


def install_swim_proxy(app):
    @app.route('/swim/', defaults={'tail': ''}, methods=['GET', 'HEAD', 'POST', 'PUT', 'DELETE'])
    @app.route('/swim/<path:tail>', methods=['GET', 'HEAD', 'POST', 'PUT', 'DELETE'])
    def swim_proxy(tail):
        # The app's existing device/Ingress guard and X-Camp-Request check run first.
        decoded = tail
        for _ in range(3):
            decoded = unquote(decoded)
        if decoded.startswith('/') or '\\' in decoded or any(part in ('.', '..') for part in decoded.split('/')) or any(ord(char) < 32 for char in decoded):
            abort(400)
        body = request.stream.read(MAX_BODY + 1)
        if len(body) > MAX_BODY:
            abort(413)
        target = '/' + tail
        if request.query_string:
            target += '?' + request.query_string.decode('ascii')
        headers = {key: request.headers[key] for key in ('Content-Type', 'Accept', 'Range', 'If-None-Match', 'If-Modified-Since') if key in request.headers}
        # Cookies, authorization and Home Assistant credentials never reach the peer.
        upstream = http.client.HTTPConnection(HOST, PORT, timeout=5)
        try:
            upstream.connect()
            upstream.sock.settimeout(90)
            upstream.request(request.method, target, body=body or None, headers=headers)
            reply = upstream.getresponse()
        except (OSError, socket.timeout, http.client.HTTPException):
            upstream.close()
            if tail.startswith('api/'):
                return {'error': '쉼오지 예약 도우미를 시작한 뒤 다시 시도해주세요.'}, 503
            html = '<!doctype html><html lang="ko"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><link rel="stylesheet" href="../static/style.css"><link rel="stylesheet" href="../static/theme.css"><script src="../static/theme.js"></script></head><body><main><h2>쉼오지 예약을 열 수 없습니다</h2><p>쉼오지 예약 도우미 애드온을 시작한 뒤 다시 시도해주세요.</p><button id="swimRetry" type="button">다시 시도</button><script src="../static/swim-embed.js"></script></main></body></html>'
            return Response(html, status=503, mimetype='text/html')
        out = {key: value for key, value in reply.getheaders() if key.lower() in RESPONSE_HEADERS}
        out['Cache-Control'] = 'no-store'
        if reply.status in (301, 302, 303, 307, 308):
            upstream.close()
            return {'error': '예약 도우미의 연결 경로를 확인해주세요.'}, 502
        if 'text/html' in reply.getheader('Content-Type', ''):
            try:
                content = reply.read(MAX_BODY + 1)
                if len(content) > MAX_BODY:
                    abort(502)
                html = content.decode('utf-8')
                # Relative assets/API paths stay underneath /swim/ in both entrypoints.
                html = html.replace('<head>', '<head><script src="../static/swim-embed.js"></script>', 1)
                return Response(html, status=reply.status, headers=out)
            finally:
                upstream.close()

        @stream_with_context
        def chunks():
            try:
                while chunk := reply.read(65536):
                    yield chunk
            finally:
                upstream.close()
        response = Response(chunks(), status=reply.status, headers=out)
        response.call_on_close(upstream.close)
        return response
