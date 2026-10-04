import copy
import json
import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch
from app import core, publish


def article(identity, category, title):
    return dict(id=identity, category=category, title=title, url='https://example.com/' + identity,
                source='test', published='', first_seen=core.now(), summary=['出典の概要'],
                analysis=dict(importance='未評価', background='未生成', why='未生成', outlook='未生成'))


class AISelectionTests(unittest.TestCase):
    def test_sport_requires_multiple_signals_and_public_interest_wins(self):
        for title in ('女子ゴルフ 国内大会で優勝', '大谷 大リーグで本塁打', 'サッカー 決勝で勝利'):
            for category in core.CATEGORIES:
                self.assertEqual(core.ai_selection(article('x', category, title)), 'sports')
        for title in ('五輪 予算の不正で逮捕', 'サッカー大会 政府が補助金政策を見直し',
                      '大谷選手の経済効果', 'ゴルフ場の水道管を耐震化', '金利政策の決勝点'):
            self.assertEqual(core.ai_selection(article('x', '政治', title)), 'priority')
        self.assertEqual(core.ai_selection(article('x', '政治', 'スポーツ振興について')), 'priority')
        self.assertEqual(core.ai_selection(article('x', '総合ニュース', '地震で避難指示')), 'public_interest')
        self.assertEqual(core.ai_selection(article('x', '総合ニュース', '季節の花が見頃')), 'outside_scope')
        a = article('x', '総合ニュース', '五輪 大会の開幕')
        a['summary'] = ['開催費の予算を国会が審議。']
        self.assertEqual(core.ai_selection(a), 'public_interest')

    def test_priority_round_robin_prevents_infrastructure_starvation(self):
        rows = [article('general', '総合ニュース', '地震で避難')]
        rows += [article(str(i), '政治', '政策') for i in range(20)]
        rows += [article(c, c, '新着') for c in core.AI_CATEGORIES[1:]]
        result = core.ai_candidates(rows)
        self.assertEqual([a['category'] for a in result[:5]], core.AI_CATEGORIES)
        self.assertEqual(result[-1]['id'], 'general')

    def test_publish_sports_do_not_spend_budget_failure_does_and_history_is_unchanged(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            old = article('old-sport', '総合ニュース', '女子ゴルフ 大会で優勝')
            old['analysis']['importance'] = '高'
            history = dict(generated_at='2026-10-01', articles=[old])
            for folder in ('docs', 'public'):
                (root / folder).mkdir()
                (root / folder / 'articles.json').write_text(json.dumps(history), encoding='utf-8')
            sources = [dict(name=c, category=c, url='https://example.com/' + str(i)) for i, c in enumerate(core.CATEGORIES)]
            (root / 'sources.json').write_text(json.dumps(sources), encoding='utf-8')
            sport = article('sport', '総合ニュース', '女子ゴルフ 大会で優勝')
            general = article('general', '総合ニュース', '地震で避難')
            duplicate = article('duplicate', '総合ニュース', '政府が政策を発表')
            political = dict(duplicate, category='政治')
            feeds = [[copy.deepcopy(old), sport, general, duplicate], [political]]
            feeds += [[article(c, c, '新着')] for c in core.AI_CATEGORIES[1:]]
            with patch.object(core, 'ROOT', root), patch.object(core, 'DB', root / 'unused.db'), patch.dict(os.environ, {'MDB_AI_LIMIT': '5', 'OPENAI_API_KEY': 'fake', 'MDB_DEMO': '0'}), patch.object(core, 'fetch', return_value=b'feed'), patch.object(core, 'parse', side_effect=feeds), patch.object(core, 'analyze', side_effect=RuntimeError) as ai:
                result = publish.publish()
                self.assertEqual(result['status'], 'partial')
                self.assertEqual(ai.call_count, 5)
                self.assertEqual([call.args[0]['category'] for call in ai.call_args_list], core.AI_CATEGORIES)
                data = json.loads((root / 'docs/articles.json').read_text(encoding='utf-8'))
                saved = {a['id']: a for a in data['articles']}
                self.assertEqual(saved['old-sport'], old)
                self.assertEqual(saved['sport']['summary'], sport['summary'])
                self.assertEqual(saved['sport']['analysis']['importance'], '対象外')
                self.assertEqual(saved['general']['analysis']['importance'], '未評価')
                self.assertEqual(saved['duplicate']['category'], '政治')
                self.assertEqual(len(saved), 8)
                with patch.object(core, 'parse', side_effect=feeds):
                    self.assertEqual(publish.publish()['added'], 0)
                self.assertEqual(ai.call_count, 5)

    def test_default_limit(self):
        self.assertEqual(core.DEFAULT_AI_LIMIT, 10)

