import argparse
import hmac
import json
import os
import secrets
import sqlite3
import subprocess
import sys
import threading
import time
from http.cookies import SimpleCookie
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import urlsplit
from . import core

class Server(ThreadingHTTPServer):
    """One process owns its startup configuration, sessions and failure window."""
    def __init__(self, address, handler, password, origin):
        parsed=urlsplit(origin)
        if parsed.scheme not in ('http','https') or not parsed.hostname or parsed.username or parsed.password or parsed.path or parsed.query or parsed.fragment:
            raise ValueError('MDB_ORIGINはパスや末尾の/を含まないhttp/httpsのURLにしてください')
        if len(password)<16:
            raise ValueError('MDB_ADMIN_PASSWORDに16文字以上のパスワードを設定してください')
        self.password=password; self.origin=origin
        self.sessions={}; self.attempts={}; self.auth_lock=threading.RLock()
        super().__init__(address,handler)

def equal(a,b):
    return hmac.compare_digest(str(a).encode('utf-8'),str(b).encode('utf-8'))

def launch(mode, category):
    run=core.begin(mode,category)
    def work():
        try:
            result=subprocess.run([sys.executable,'-m','app.main','worker','--run',str(run),'--category',category],cwd=core.ROOT,timeout=890)
            if result.returncode: core.finish(run,'failed',error='更新プロセスが停止しました')
        except subprocess.TimeoutExpired: core.finish(run,'failed',error='15分の処理時間上限に達しました')
        except Exception: core.finish(run,'failed',error='更新処理を開始できませんでした')
    threading.Thread(target=work,daemon=True).start()
    return run

class Handler(BaseHTTPRequestHandler):
    def log_message(self, *args): pass
    def send(self, code, body, mime='application/json', cookie=None):
        self.send_response(code)
        self.send_header('Content-Type',mime+'; charset=utf-8')
        self.send_header('Cache-Control','no-store' if self.path.startswith('/api') else 'no-cache')
        self.send_header('X-Content-Type-Options','nosniff')
        self.send_header('Content-Security-Policy',"default-src 'self'; style-src 'self'; script-src 'self'; connect-src 'self'; img-src 'self'; frame-ancestors 'none'; base-uri 'self'")
        if cookie: self.send_header('Set-Cookie',cookie)
        self.end_headers()
        self.wfile.write(body if isinstance(body,bytes) else json.dumps(body,ensure_ascii=False).encode())
    def session(self):
        try:
            cookie=SimpleCookie(self.headers.get('Cookie',''))
            with self.server.auth_lock:
                sid=cookie['mdb'].value
                s=self.server.sessions.get(sid)
                if s and s['expires']<=time.monotonic():
                    self.server.sessions.pop(sid,None); return None
            return s
        except Exception: return None
    def do_GET(self):
        if self.path=='/api/news': return self.send(200,core.snapshot())
        if self.path=='/api/session':
            s=self.session(); return self.send(200,{'authenticated':bool(s),'csrf':s['csrf'] if s else ''})
        files={'/':'index.html','/app.js':'app.js','/style.css':'style.css','/sw.js':'sw.js','/manifest.webmanifest':'manifest.webmanifest','/icon.svg':'icon.svg'}
        name=files.get(self.path.split('?')[0])
        if not name: return self.send(404,{'error':'見つかりません'})
        mime={'html':'text/html','js':'text/javascript','css':'text/css','webmanifest':'application/manifest+json','svg':'image/svg+xml'}[name.split('.')[-1]]
        self.send(200,(core.ROOT/'static'/name).read_bytes(),mime)
    def do_POST(self):
        try:
            if self.headers.get('Transfer-Encoding'):
                return self.send(400,{'error':'Transfer-Encodingには対応していません'})
            if len(self.headers.get_all('Content-Length',[]))!=1:
                return self.send(400,{'error':'Content-Lengthが必要です'})
            length=int(self.headers.get('Content-Length','0'))
            if length>4096:
                # Drain small rejected bodies so Windows can deliver the 413
                # before closing; never buffer an unbounded request.
                self.connection.settimeout(2)
                if length<=65536: self.rfile.read(length)
                return self.send(413,{'error':'入力が大きすぎます'})
            if length<=0: return self.send(400,{'error':'JSONオブジェクトが必要です'})
            if self.headers.get_content_type()!='application/json':
                return self.send(415,{'error':'Content-Typeをapplication/jsonにしてください'})
            self.connection.settimeout(10)
            raw=self.rfile.read(length)
            if len(raw)!=length: return self.send(400,{'error':'入力が途中で終了しました'})
            data=json.loads(raw.decode('utf-8-sig'))
            if not isinstance(data,dict): return self.send(400,{'error':'JSONオブジェクトが必要です'})
        except (ValueError,UnicodeError,OSError): return self.send(400,{'error':'UTF-8のJSONを送信してください'})
        if self.path=='/api/scheduled':
            token=os.environ.get('MDB_SCHEDULE_TOKEN','')
            if not token or not equal(self.headers.get('Authorization',''),'Bearer '+token): return self.send(401,{'error':'認証が必要です'})
            mode='automatic'; category='all'
            with core.connect() as c:
                done=c.execute("SELECT id FROM runs WHERE mode='automatic' AND status='success' AND started LIKE ?",(core.now()[:10]+'%',)).fetchone()
            if done: return self.send(200,{'id':done['id'],'skipped':True})
        else:
            origin=self.server.origin
            if self.headers.get_all('Origin',[])!=[origin]: return self.send(403,{'error':'操作元が不正です'})
            if self.path=='/api/login':
                with self.server.auth_lock:
                    now=time.monotonic(); ip=self.client_address[0]
                    self.server.attempts={key:[t for t in times if now-t<900] for key,times in self.server.attempts.items() if any(now-t<900 for t in times)}
                    recent=self.server.attempts.setdefault(ip,[])
                    if len(recent)>=5: return self.send(429,{'error':'15分後に再試行してください'})
                    password=data.get('password')
                    if not isinstance(password,str) or not equal(password,self.server.password):
                        recent.append(now); return self.send(401,{'error':'認証できませんでした'})
                    self.server.sessions={key:s for key,s in self.server.sessions.items() if s['expires']>now}
                    try: old=SimpleCookie(self.headers.get('Cookie',''))
                    except Exception: old=SimpleCookie()
                    if 'mdb' in old: self.server.sessions.pop(old['mdb'].value,None)
                    sid=secrets.token_urlsafe(32); csrf=secrets.token_urlsafe(32)
                    self.server.sessions[sid]={'csrf':csrf,'expires':now+3600}
                return self.send(200,{'csrf':csrf},cookie='mdb='+sid+'; HttpOnly; SameSite=Strict; Path=/; Max-Age=3600'+('; Secure' if origin.startswith('https://') else ''))
            s=self.session()
            if not s or not equal(self.headers.get('X-CSRF-Token',''),s['csrf']): return self.send(401,{'error':'再ログインしてください'})
            if self.path=='/api/logout':
                cookie=SimpleCookie(self.headers.get('Cookie',''))
                with self.server.auth_lock: self.server.sessions.pop(cookie['mdb'].value,None)
                return self.send(200,{},cookie='mdb=; HttpOnly; SameSite=Strict; Path=/; Max-Age=0'+('; Secure' if origin.startswith('https://') else ''))
            if self.path!='/api/update': return self.send(404,{'error':'見つかりません'})
            mode='manual'; category=data.get('category','all')
            if category not in ['all']+core.CATEGORIES: return self.send(400,{'error':'カテゴリが不正です'})
        try: return self.send(202,{'id':launch(mode,category)})
        except sqlite3.IntegrityError: return self.send(409,{'error':'更新中です。完了をお待ちください'})

def main():
    p=argparse.ArgumentParser(); p.add_argument('command',choices=['serve','update','worker','demo']); p.add_argument('--category',default='all',choices=['all']+core.CATEGORIES); p.add_argument('--run',type=int); p.add_argument('--port',type=int,default=8000); p.add_argument('--host',default='127.0.0.1'); a=p.parse_args()
    if os.environ.get('MDB_DEMO')=='1' or a.command=='demo':
        os.environ['MDB_DEMO']='1'; core.DB=core.Path(os.environ.get('MDB_DEMO_DB',str(core.ROOT/'data/demo.db')))
    if a.command=='worker': core.update(a.run,a.category,os.environ.get('MDB_DEMO')=='1'); return
    if a.command in ['demo','update']:
        run=core.begin('local',a.category); core.update(run,a.category,os.environ.get('MDB_DEMO')=='1'); print(json.dumps(core.snapshot()['runs'][0],ensure_ascii=False)); return
    password=os.environ.get('MDB_ADMIN_PASSWORD','')
    if len(password)<16: raise SystemExit('MDB_ADMIN_PASSWORDに16文字以上のパスワードを設定してください')
    if os.environ.get('MDB_ORIGIN','').startswith('https://') and len(os.environ.get('MDB_SCHEDULE_TOKEN',''))<32: raise SystemExit('本番用MDB_SCHEDULE_TOKENを32文字以上で設定してください')
    origin=os.environ.get('MDB_ORIGIN',f'http://{a.host}:{a.port}')
    try: server=Server((a.host,a.port),Handler,password,origin)
    except (OSError,ValueError) as e: raise SystemExit(f'起動できません: {e}')
    with core.connect() as c: c.execute("UPDATE runs SET status='failed',ended=?,error='サーバー再起動により中断' WHERE status='running'",(core.now(),))
    print(f'My Daily Brief: {origin}\nPID: {os.getpid()} / Source: {__file__}\nMode: '+('demo' if os.environ.get('MDB_DEMO')=='1' else 'live'),flush=True)
    try: server.serve_forever()
    except KeyboardInterrupt: pass
    finally: server.server_close()

if __name__=='__main__': main()
