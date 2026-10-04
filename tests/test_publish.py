import copy
import json
import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch
from app import core, publish


class PublishTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.history = json.loads((core.ROOT / 'docs/articles.json').read_text(encoding='utf-8'))
        for folder in ('docs', 'public'):
            (self.root / folder).mkdir()
            (self.root / folder / 'articles.json').write_text(json.dumps(self.history, ensure_ascii=False, indent=2), encoding='utf-8')
        (self.root / 'sources.json').write_text(json.dumps([dict(name=c, category=c, url='https://example.com/feed') for c in core.CATEGORIES]), encoding='utf-8')
        for context in (patch.object(core, 'ROOT', self.root), patch.object(core, 'DB', self.root / 'data/news.db'), patch.dict(os.environ, {'MDB_AI_LIMIT': '1', 'OPENAI_API_KEY': 'test', 'MDB_DEMO': '0'})):
            context.start()
            self.addCleanup(context.stop)

    def output(self):
        return json.loads((self.root / 'docs/articles.json').read_text(encoding='utf-8'))

    def test_round_trip_and_dedup_before_ai_limit(self):
        existing = copy.deepcopy(self.history['articles'][0])
        new = copy.deepcopy(existing)
        new.update(id='new-article', url='https://example.com/new', first_seen=core.now())
        with patch.object(core, 'fetch', return_value=b'feed'), patch.object(core, 'parse', return_value=[existing, new]), patch.object(core, 'analyze', side_effect=lambda a: a) as ai:
            result = publish.publish()
            self.assertEqual(result['added'], 1)
            ai.assert_called_once()
            result = publish.publish()
            self.assertEqual(result['added'], 0)
            self.assertEqual(ai.call_count, 1)
        rows = {a['id']: a for a in self.output()['articles']}
        for a in self.history['articles']:
            self.assertEqual(rows[a['id']], a)
        self.assertEqual(len(rows), len(self.history['articles']) + 1)
        self.assertEqual((self.root / 'docs/articles.json').read_bytes(), (self.root / 'public/articles.json').read_bytes())
        self.assertFalse((self.root / 'data/news.db').exists())

    def test_total_failure_preserves_files_and_db_setting(self):
        before = (self.root / 'docs/articles.json').read_bytes()
        old = core.DB
        with patch.object(core, 'fetch', side_effect=TimeoutError), self.assertRaises(RuntimeError):
            publish.publish()
        self.assertEqual(core.DB, old)
        self.assertEqual((self.root / 'docs/articles.json').read_bytes(), before)
        self.assertEqual((self.root / 'public/articles.json').read_bytes(), before)

    def test_invalid_history_validated_before_insertion(self):
        history = copy.deepcopy(self.history)
        history['articles'].append(history['articles'][0])
        (self.root / 'docs/articles.json').write_text(json.dumps(history), encoding='utf-8')
        with patch.object(core, 'DB', self.root / 'restore.db'):
            with self.assertRaises(ValueError):
                publish.restore_history(self.root / 'docs/articles.json')
            with core.connect() as c:
                self.assertEqual(c.execute('SELECT COUNT(*) FROM articles').fetchone()[0], 0)

    def test_partial_failure_and_zero_ai_limit(self):
        new = copy.deepcopy(self.history['articles'][0])
        new.update(id='new-partial', url='https://example.com/new-partial')
        with patch.dict(os.environ, {'MDB_AI_LIMIT': '0', 'OPENAI_API_KEY': ''}), patch.object(core, 'fetch', side_effect=[b'feed'] + [TimeoutError()] * 5), patch.object(core, 'parse', return_value=[new]), patch.object(core, 'analyze') as ai:
            self.assertEqual(publish.publish()['status'], 'partial')
            ai.assert_not_called()
        self.assertEqual(len(self.output()['articles']), len(self.history['articles']) + 1)

    def test_configuration_fails_before_network_or_publication(self):
        for env in ({'MDB_AI_LIMIT': '-1'}, {'MDB_AI_LIMIT': 'bad'}, {'OPENAI_API_KEY': ''}, {'MDB_DEMO': '1'}):
            with patch.dict(os.environ, env), patch.object(core, 'fetch') as fetch, self.assertRaises(ValueError):
                publish.publish()
            fetch.assert_not_called()

    def test_history_over_ui_limit_is_preserved(self):
        history = copy.deepcopy(self.history)
        template = history['articles'][0]
        history['articles'] = [dict(template, id=str(i), url=f'https://example.com/{i}') for i in range(1001)]
        (self.root / 'docs/articles.json').write_text(json.dumps(history), encoding='utf-8')
        with patch.object(core, 'fetch', return_value=b'feed'), patch.object(core, 'parse', return_value=[history['articles'][0]]):
            publish.publish()
        self.assertEqual(len(self.output()['articles']), 1001)
