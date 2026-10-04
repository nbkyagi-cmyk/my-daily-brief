import copy
import json
import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch
from app import core, publish


ONE = 'https://news.web.nhk/newsweb/na/nd-20261004de54280'
NORMAL = 'https://www3.nhk.or.jp/news/html/20260901/k10000000001000.html'


def article(url):
    return dict(id=url, category='政治', title='NHK ONEについて政府が政策を発表',
                url=url, source='NHK 政治', published='', first_seen='2026-10-01',
                summary=['概要'], analysis=dict(importance='高', background='既存分析',
                                               why='既存分析', outlook='既存分析'))


class NHKOneTests(unittest.TestCase):
    def test_precise_url_matching(self):
        for url in (ONE, ONE + '?x=1#top', ONE.replace('news.web.nhk', 'NEWS.WEB.NHK.'),
                    'https://news.web.nhk/%6eewsweb/na/test'):
            self.assertTrue(core.is_nhk_one_url(url), url)
        for url in (NORMAL, 'https://www.nhk.or.jp/news/test',
                    'https://www3.nhk.or.jp/news/easy/test',
                    'https://www.mlit.go.jp/NHKONE',
                    'https://news.web.nhk.evil.example/newsweb/na/test',
                    'https://news.web.nhk@other.example/newsweb/test',
                    'https://example.com/?url=' + ONE,
                    'https://news.web.nhk/newsweb-other/test'):
            self.assertFalse(core.is_nhk_one_url(url), url)

    def test_rss_atom_and_limit_filter_before_candidates(self):
        items = ''.join(f'<item><title>政策</title><link>{ONE}/{i}</link></item>' for i in range(25))
        items += f'<item><title>NHK ONEの政策</title><link>{NORMAL}</link></item>'
        rows = core.parse(('<rss><channel>' + items + '</channel></rss>').encode(), 'NHK 政治', '政治')
        self.assertEqual([a['url'] for a in rows], [NORMAL])
        atom = f'<feed xmlns="http://www.w3.org/2005/Atom"><entry><title>政策</title><link href="{ONE}"/></entry></feed>'
        self.assertEqual(core.parse(atom.encode(), 'NHK', '政治'), [])
        self.assertEqual(core.ai_candidates([article(ONE), article(NORMAL)]), [article(NORMAL)])

    def test_publish_cleanup_without_new_articles_or_ai_and_no_reanalysis(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            kept = [article(NORMAL), article('https://www.mlit.go.jp/test')]
            history = dict(generated_at='original', articles=[article(ONE)] + kept)
            for folder in ('docs', 'public'):
                (root / folder).mkdir()
                (root / folder / 'articles.json').write_text(json.dumps(history), encoding='utf-8')
            sources = [dict(name=c, category=c, url='https://example.com/feed') for c in core.CATEGORIES]
            (root / 'sources.json').write_text(json.dumps(sources), encoding='utf-8')
            feed = f'<rss><channel><item><title>政府の政策</title><link>{ONE}</link></item></channel></rss>'.encode()
            with patch.object(core, 'ROOT', root), patch.object(core, 'DB', root / 'unused.db'), patch.dict(os.environ, {'MDB_AI_LIMIT': '10', 'OPENAI_API_KEY': 'fake', 'MDB_DEMO': '0'}), patch.object(core, 'fetch', return_value=feed), patch.object(core, 'analyze') as ai:
                result = publish.publish()
                self.assertEqual(result['status'], 'success')
                self.assertEqual(result['added'], 0)
                ai.assert_not_called()
                output = json.loads((root / 'docs/articles.json').read_text(encoding='utf-8'))
                self.assertEqual(output, dict(history, articles=kept))
                self.assertEqual((root / 'docs/articles.json').read_bytes(), (root / 'public/articles.json').read_bytes())
                self.assertFalse((root / 'unused.db').exists())
                # A filtered source cannot consume the sole available AI slot.
                with patch.object(core, 'parse', return_value=[article(ONE), article(NORMAL), article('https://example.com/new')]), patch.dict(os.environ, {'MDB_AI_LIMIT': '1'}):
                    publish.publish()
                ai.assert_called_once()
                self.assertEqual(ai.call_args.args[0]['url'], 'https://example.com/new')

    def test_checked_in_history_is_clean_and_mirrored(self):
        self.assertEqual((core.ROOT / 'docs/articles.json').read_bytes(), (core.ROOT / 'public/articles.json').read_bytes())
        rows = json.loads((core.ROOT / 'docs/articles.json').read_text(encoding='utf-8'))['articles']
        self.assertFalse(any(core.is_nhk_one_url(a['url']) for a in rows))
