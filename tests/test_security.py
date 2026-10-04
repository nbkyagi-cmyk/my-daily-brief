import concurrent.futures
import json
import os
import subprocess
import sys
import tempfile
import threading
import time
import unittest
import urllib.error
import urllib.request
from pathlib import Path
from unittest.mock import patch
from app import core, main

PASSWORD='MyDailyBrief-Test-2026!'

def request(base,path,body=None,headers=None):
    req=urllib.request.Request(base+path,data=body,headers=headers or {})
    try: response=urllib.request.urlopen(req,timeout=10)
    except urllib.error.HTTPError as e: response=e
    with response:
        raw=response.read()
        return response.status,response.headers,json.loads(raw)

class SecurityTests(unittest.TestCase):
    def setUp(self):
        self.server=main.Server(('127.0.0.1',0),main.Handler,PASSWORD,'http://127.0.0.1:8000')
        self.base='http://127.0.0.1:'+str(self.server.server_port)
        self.server.origin=self.base
        self.thread=threading.Thread(target=self.server.serve_forever,daemon=True);self.thread.start()
    def tearDown(self):
        self.server.shutdown();self.server.server_close();self.thread.join()
    def post(self,path,value,headers=None):
        return request(self.base,path,json.dumps(value,ensure_ascii=False).encode('utf-8'),{'Origin':self.base,'Content-Type':'application/json',**(headers or {})})
    def login(self):
        status,headers,data=self.post('/api/login',{'password':PASSWORD})
        self.assertEqual(status,200)
        return {'Cookie':headers['Set-Cookie'].split(';')[0],'X-CSRF-Token':data['csrf']}
    def test_exact_password_and_session_logout(self):
        auth=self.login()
        status,_,data=request(self.base,'/api/session',headers=auth)
        self.assertEqual(status,200);self.assertTrue(data['authenticated'])
        self.assertEqual(data['csrf'],auth['X-CSRF-Token'])
        self.assertEqual(self.post('/api/logout',{},auth)[0],200)
        self.assertFalse(request(self.base,'/api/session',headers=auth)[2]['authenticated'])
    def test_origin_and_csrf(self):
        for origin in ('','https://evil.example',self.base+'/'):
            self.assertEqual(self.post('/api/login',{'password':PASSWORD},{'Origin':origin})[0],403)
        auth=self.login()
        for token in ('','wrong'):
            self.assertEqual(self.post('/api/update',{'category':'政治'},{**auth,'X-CSRF-Token':token})[0],401)
        self.assertEqual(self.post('/api/update',{'category':'invalid'},auth)[0],400)
    def test_json_validation_and_bom(self):
        for raw in (b'[]',b'null',b'1',b'"text"',b'{',b'\xff',b'',b'{}'*3000):
            self.assertIn(request(self.base,'/api/login',raw,{'Origin':self.base,'Content-Type':'application/json'})[0],(400,413))
        self.assertEqual(request(self.base,'/api/login',b'{}',{'Origin':self.base,'Content-Type':'text/plain'})[0],415)
        raw=b'\xef\xbb\xbf'+json.dumps({'password':PASSWORD}).encode()
        self.assertEqual(request(self.base,'/api/login',raw,{'Origin':self.base,'Content-Type':'application/json; charset=utf-8'})[0],200)
    def test_five_failures_and_window(self):
        for _ in range(5): self.assertEqual(self.post('/api/login',{'password':'wrong'})[0],401)
        self.assertEqual(self.post('/api/login',{'password':PASSWORD})[0],429)
        self.server.attempts['127.0.0.1']=[time.monotonic()-901]*5
        self.assertEqual(self.post('/api/login',{'password':PASSWORD})[0],200)
    def test_concurrent_failure_limit(self):
        with concurrent.futures.ThreadPoolExecutor(max_workers=8) as executor:
            statuses=list(executor.map(lambda _:self.post('/api/login',{'password':'wrong'})[0],range(8)))
        self.assertEqual(statuses.count(401),5);self.assertEqual(statuses.count(429),3)
    def test_config_frozen_cookie_and_expiry(self):
        with patch.dict(os.environ,{'MDB_ADMIN_PASSWORD':'different-long-password'}): auth=self.login()
        self.server.sessions[auth['Cookie'].split('=',1)[1]]['expires']=time.monotonic()-1
        self.assertFalse(request(self.base,'/api/session',headers=auth)[2]['authenticated'])
        _,headers,_=self.post('/api/login',{'password':PASSWORD})
        for flag in ('HttpOnly','SameSite=Strict','Max-Age=3600','Path=/'):self.assertIn(flag,headers['Set-Cookie'])
        self.server.origin='https://brief.example'
        _,headers,_=self.post('/api/login',{'password':PASSWORD},{'Origin':self.server.origin})
        self.assertIn('Secure',headers['Set-Cookie'])
    def test_utf8_assets(self):
        for p in (core.ROOT/'static').iterdir():
            p.read_bytes().decode('utf-8')
        for p in [core.ROOT/'app/main.py',core.ROOT/'app/core.py',core.ROOT/'README.md']:
            text=p.read_text(encoding='utf-8')
            for marker in ('\ufffd','譖ｴ譁ｰ','縺励','繧ｹ'):self.assertNotIn(marker,text)
    def test_scheduled_token_and_password_types(self):
        for value in (None,23,{},[],PASSWORD+' '):
            self.assertEqual(self.post('/api/login',{'password':value})[0],401)
        with tempfile.TemporaryDirectory() as temp, patch.object(core,'DB',Path(temp)/'test.db'), patch.dict(os.environ,{'MDB_SCHEDULE_TOKEN':'x'*32}):
            self.assertEqual(self.post('/api/scheduled',{}, {'Authorization':'Bearer wrong'})[0],401)
            with patch('app.main.launch',return_value=42) as launch:
                self.assertEqual(self.post('/api/scheduled',{}, {'Authorization':'Bearer '+'x'*32})[0],202)
                launch.assert_called_once_with('automatic','all')

class ProcessTests(unittest.TestCase):
    def test_real_demo_server_and_category_workers(self):
        # Actual subprocess and real workers; no mocked launch or network sources.
        import socket
        with socket.socket() as sock:
            sock.bind(('127.0.0.1',0));port=sock.getsockname()[1]
        base=f'http://127.0.0.1:{port}'
        with tempfile.TemporaryDirectory() as temp:
            env={**os.environ,'MDB_ADMIN_PASSWORD':PASSWORD,'MDB_DEMO':'1','MDB_ORIGIN':base,'MDB_DEMO_DB':str(Path(temp)/'demo.db')}
            command=[sys.executable,'-m','app.main']
            seed=subprocess.run(command+['demo'],cwd=core.ROOT,env=env,capture_output=True,timeout=20)
            self.assertEqual(seed.returncode,0,seed.stderr.decode('utf-8',errors='replace'))
            process=subprocess.Popen(command+['serve','--port',str(port)],cwd=core.ROOT,env=env,stdout=subprocess.PIPE,stderr=subprocess.PIPE)
            try:
                deadline=time.monotonic()+15
                while True:
                    try: status,_,snapshot=request(base,'/api/news');break
                    except OSError:
                        if process.poll() is not None or time.monotonic()>deadline: self.fail('Server did not start')
                        time.sleep(.1)
                self.assertTrue(snapshot['demo']);self.assertEqual(len(snapshot['articles']),6)
                # PowerShell makes a separate real HTTP POST to the running process.
                import shutil
                ps=shutil.which('pwsh') or shutil.which('powershell')
                if ps:
                    script="$body=[Text.Encoding]::UTF8.GetBytes((@{password=$env:MDB_ADMIN_PASSWORD}|ConvertTo-Json -Compress)); $r=Invoke-RestMethod -Uri ($env:MDB_ORIGIN+'/api/login') -Method Post -ContentType 'application/json; charset=utf-8' -Headers @{Origin=$env:MDB_ORIGIN} -Body $body -SessionVariable s; if(-not $r.csrf){exit 1}; $v=Invoke-RestMethod -Uri ($env:MDB_ORIGIN+'/api/session') -WebSession $s; if(-not $v.authenticated){exit 2}"
                    check=subprocess.run([str(ps),'-NoProfile','-Command',script],env=env,capture_output=True,timeout=15)
                    self.assertEqual(check.returncode,0,check.stderr.decode('utf-8',errors='replace'))
                raw=json.dumps({'password':PASSWORD}).encode()
                status,headers,data=request(base,'/api/login',raw,{'Origin':base,'Content-Type':'application/json'})
                self.assertEqual(status,200)
                auth={'Origin':base,'Content-Type':'application/json','Cookie':headers['Set-Cookie'].split(';')[0],'X-CSRF-Token':data['csrf']}
                self.assertTrue(request(base,'/api/session',headers=auth)[2]['authenticated'])
                for category in core.CATEGORIES+['all']:
                    status,_,result=request(base,'/api/update',json.dumps({'category':category},ensure_ascii=False).encode(),auth)
                    self.assertEqual(status,202)
                    deadline=time.monotonic()+20
                    while True:
                        snapshot=request(base,'/api/news')[2]
                        run=next(r for r in snapshot['runs'] if r['id']==result['id'])
                        if run['status']!='running':break
                        if time.monotonic()>deadline:self.fail('Worker timed out')
                        time.sleep(.1)
                    self.assertEqual(run['status'],'success',run)
                    self.assertEqual(run['category'],category);self.assertEqual(run['added'],0)
                    self.assertEqual(len(snapshot['articles']),6)
                self.assertEqual(request(base,'/api/logout',b'{}',auth)[0],200)
                self.assertFalse(request(base,'/api/session',headers=auth)[2]['authenticated'])
            finally:
                process.terminate();process.communicate(timeout=10)

if __name__=='__main__':unittest.main()
