import json
import os
import sqlite3
import tempfile
import threading
import unittest
import urllib.request
import urllib.error
from pathlib import Path
from unittest.mock import patch
from app import core, main

class Tests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory(); self.old=core.DB; core.DB=Path(self.temp.name)/'test.db'
    def tearDown(self): core.DB=self.old; self.temp.cleanup()
    def test_demo_dedup_category(self):
        r=core.begin('local','all');core.update(r,'all',True)
        self.assertEqual(len(core.snapshot()['articles']),6)
        r=core.begin('manual','政治');core.update(r,'政治',True)
        self.assertEqual(core.snapshot()['runs'][0]['added'],0)
        self.assertEqual(len(core.snapshot()['articles']),6)
    def test_lock_and_failure_preserve(self):
        r=core.begin('manual','all')
        with self.assertRaises(sqlite3.IntegrityError): core.begin('manual','all')
        core.finish(r,'failed',error='timeout')
        r=core.begin('local','all');core.update(r,'all',True)
        r=core.begin('manual','政治')
        with patch('app.core.fetch',side_effect=TimeoutError): core.update(r,'政治')
        self.assertEqual(core.snapshot()['runs'][0]['status'],'failed')
        self.assertEqual(len(core.snapshot()['articles']),6)
    def test_parser_safety(self):
        data=b'<rss><channel><item><title>&lt;script&gt;x&lt;/script&gt;Good</title><link>javascript:alert(1)</link></item><item><title>OK</title><link>https://example.com/news</link></item></channel></rss>'
        rows=core.parse(data,'test','政治');self.assertEqual(len(rows),1);self.assertEqual(rows[0]['analysis']['why'],'未生成')
    def test_http_auth_csrf(self):
        server=main.Server(('127.0.0.1',0),main.Handler,'a-long-test-password','http://127.0.0.1:8000')
        thread=threading.Thread(target=server.serve_forever,daemon=True);thread.start()
        base='http://127.0.0.1:'+str(server.server_port)
        server.origin=base
        def post(path,body,headers={}):
            return urllib.request.urlopen(urllib.request.Request(base+path,data=json.dumps(body).encode(),headers={'Content-Type':'application/json',**headers}))
        try:
            with patch.dict(os.environ,{'MDB_ADMIN_PASSWORD':'a-long-test-password','MDB_ORIGIN':base}):
                with self.assertRaises(urllib.error.HTTPError) as e:post('/api/update',{'category':'all'},{'Origin':base})
                self.assertEqual(e.exception.code,401)
                with post('/api/login',{'password':'a-long-test-password'},{'Origin':base}) as r:cookie=r.headers['Set-Cookie'].split(';')[0];csrf=json.load(r)['csrf']
                with self.assertRaises(urllib.error.HTTPError) as e:post('/api/update',{}, {'Origin':'https://evil.example','Cookie':cookie,'X-CSRF-Token':csrf})
                self.assertEqual(e.exception.code,403)
                with patch('app.main.launch',return_value=42) as launch:
                    with post('/api/update',{'category':'政治'},{'Origin':base,'Cookie':cookie,'X-CSRF-Token':csrf}) as r:self.assertEqual(r.status,202)
                    launch.assert_called_once_with('manual','政治')
                with self.assertRaises(urllib.error.HTTPError) as e:post('/api/scheduled',{})
                self.assertEqual(e.exception.code,401)
        finally:server.shutdown();server.server_close()

if __name__=='__main__':unittest.main()
