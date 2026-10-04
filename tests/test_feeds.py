import hashlib
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch
from app import core


def rss(titles):
    return ('<rss><channel>'+''.join(f'<item><title>{t}</title><link>https://example.com/{i}</link><description>概要</description></item>' for i,t in enumerate(titles))+'</channel></rss>').encode()


class FeedTests(unittest.TestCase):
    def test_legacy_identity_and_limit(self):
        rows=core.parse(rss(['ニュース']*25),'test','政治')
        self.assertEqual(len(rows),20)
        self.assertEqual(rows[0]['id'],hashlib.sha256(b'https://example.com/0').hexdigest()[:24])

    def test_filter_after_twenty_and_category_identity(self):
        data=rss(['対象外']*21+['水道と無電柱化']*25)
        a=core.parse(data,'a','水道・インフラ',['水道'])
        b=core.parse(data,'b','無電柱化',['無電柱化'])
        self.assertEqual(len(a),20)
        self.assertTrue(a[0]['url'].endswith('/21'))
        self.assertNotEqual(a[0]['id'],b[0]['id'])
        self.assertEqual(a[0]['id'],core.parse(data,'c','水道・インフラ',['水道'])[0]['id'])

    def test_description_or_case_and_invalid_config(self):
        self.assertTrue(core.matches_keywords('対象外',core.clean('<b>上下水道</b> DX'),['dx','配水管']))
        self.assertFalse(core.matches_keywords('鉄道','概要',['水道']))
        for bad in [[],[''],[12],'水道']:
            with self.assertRaises(ValueError): core.parse(rss([]),'x','政治',bad)
        with self.assertRaises(ValueError): core.parse(b'<html/>','x','政治',['水道'])

    def test_rdf_shiftjis_date_and_link_scope(self):
        xml='''<?xml version="1.0" encoding="Shift_JIS"?><rdf:RDF xmlns:rdf="http://www.w3.org/1999/02/22-rdf-syntax-ns#" xmlns="http://purl.org/rss/1.0/" xmlns:dc="http://purl.org/dc/elements/1.1/"><item><title>水道耐震化</title><link>http://www.mlit.go.jp/report/test.html</link><dc:date>2026-10-01</dc:date></item><item><title>水道</title><link>http://www.mlit.go.jp.evil.example/test</link></item></rdf:RDF>'''.encode('shift_jis')
        self.assertEqual(core.parse(xml,'x','水道・インフラ',['水道']),[])
        rows=core.parse(xml,'x','水道・インフラ',['水道'],True)
        self.assertEqual(len(rows),1)
        self.assertEqual(rows[0]['url'],'https://www.mlit.go.jp/report/test.html')
        self.assertEqual(rows[0]['published'],'2026-10-01')

    def test_atom_alternate(self):
        xml=b'<feed xmlns="http://www.w3.org/2005/Atom"><entry><title>Water</title><link rel="self" href="https://example.com/self"/><link href="https://example.com/article"/><summary>pipe</summary></entry></feed>'
        self.assertEqual(core.parse(xml,'x','政治',['pipe'])[0]['url'],'https://example.com/article')

    def test_update_empty_dedup_failure_and_ai_order(self):
        with tempfile.TemporaryDirectory() as directory:
            root=Path(directory)
            sources=[dict(name='a',category='水道・インフラ',url='https://example.com/feed',keywords=['水道']),dict(name='b',category='水道・インフラ',url='https://example.com/feed2',keywords=['水道'])]
            (root/'sources.json').write_text(json.dumps(sources),encoding='utf-8')
            with patch.object(core,'ROOT',root),patch.object(core,'DB',root/'test.db'),patch.object(core,'fetch',return_value=rss(['鉄道'])),patch.object(core,'analyze',side_effect=lambda a:a) as ai:
                run=core.begin('local','水道・インフラ');core.update(run,'水道・インフラ')
                self.assertEqual(core.snapshot()['runs'][0]['status'],'success');ai.assert_not_called()
                with patch.object(core,'fetch',return_value=rss(['水道'])):
                    run=core.begin('local','水道・インフラ');core.update(run,'水道・インフラ')
                    self.assertEqual(len(core.snapshot()['articles']),1)
                    self.assertEqual(ai.call_count,1)
                    run=core.begin('local','水道・インフラ');core.update(run,'水道・インフラ')
                    self.assertEqual(core.snapshot()['runs'][0]['added'],0)
                with patch.object(core,'fetch',side_effect=TimeoutError):
                    run=core.begin('local','水道・インフラ');core.update(run,'水道・インフラ')
                    self.assertEqual(core.snapshot()['runs'][0]['status'],'failed')
                    self.assertEqual(len(core.snapshot()['articles']),1)
