"""Publish using a disposable DB restored from the public history."""
import json
import os
import tempfile
from pathlib import Path
from . import core

FIELDS = ('id', 'category', 'title', 'url', 'source', 'published', 'first_seen', 'summary', 'analysis')


def restore_history(path):
    payload = json.loads(Path(path).read_text(encoding='utf-8'))
    if not isinstance(payload, dict) or not isinstance(payload.get('articles'), list):
        raise ValueError('History must contain an articles array')
    ids = set()
    for a in payload['articles']:
        if not isinstance(a, dict) or any(k not in a for k in FIELDS):
            raise ValueError('Incomplete article')
        if any(not isinstance(a[k], str) for k in FIELDS[:-2]):
            raise ValueError('Invalid text field')
        if not a['id'] or a['id'] in ids or a['category'] not in core.CATEGORIES or not a['url'].startswith('https://'):
            raise ValueError('Invalid or duplicate identity')
        if not isinstance(a['summary'], list) or not all(isinstance(s, str) for s in a['summary']):
            raise ValueError('Invalid summary')
        if not isinstance(a['analysis'], dict) or set(a['analysis']) != {'importance', 'background', 'why', 'outlook'} or not all(isinstance(s, str) for s in a['analysis'].values()):
            raise ValueError('Invalid analysis')
        ids.add(a['id'])
    with core.connect() as c:
        if c.execute('SELECT COUNT(*) FROM articles').fetchone()[0]:
            raise ValueError('Restore requires an empty DB')
        c.executemany('INSERT INTO articles VALUES(?,?,?,?,?,?,?,?,?)', [tuple(json.dumps(a[k], ensure_ascii=False) if k in ('summary', 'analysis') else a[k] for k in FIELDS) for a in payload['articles']])
    return payload


def publish():
    if os.environ.get('MDB_DEMO') == '1':
        raise ValueError('Demo publishing is forbidden')
    limit = int(os.environ.get('MDB_AI_LIMIT', '12'))
    if limit < 0:
        raise ValueError('MDB_AI_LIMIT must be nonnegative')
    if limit and not os.environ.get('OPENAI_API_KEY'):
        raise ValueError('OPENAI_API_KEY required unless MDB_AI_LIMIT=0')
    old_db = core.DB
    try:
        with tempfile.TemporaryDirectory(prefix='mdb-publish-') as directory:
            core.DB = Path(directory) / 'news.db'
            history = restore_history(core.ROOT / 'docs/articles.json')
            run = core.begin('automatic', 'all')
            core.update(run, 'all')
            with core.connect() as c:
                result = dict(c.execute('SELECT * FROM runs WHERE id=?', (run,)).fetchone())
                articles = [dict(r) for r in c.execute('SELECT * FROM articles ORDER BY first_seen DESC, id')]
            print(json.dumps(result, ensure_ascii=False))
            if result['status'] not in ('success', 'partial'):
                raise RuntimeError('Update failed; public files preserved')
            for a in articles:
                a['summary'] = json.loads(a['summary'])
                a['analysis'] = json.loads(a['analysis'])
            # Preserve all history, including beyond the UI's 1000-row limit.
            payload = dict(history)
            if result['added']:
                payload.update(generated_at=core.now(), articles=articles)
            content = json.dumps(payload, ensure_ascii=False, indent=2)
            for folder in ('public', 'docs'):
                target = core.ROOT / folder / 'articles.json'
                target.parent.mkdir(parents=True, exist_ok=True)
                temporary = target.with_suffix('.json.tmp')
                temporary.write_text(content, encoding='utf-8')
                temporary.replace(target)
            if result['status'] == 'partial':
                print('::warning::Some feeds or AI analyses failed; available articles preserved')
            return result
    finally:
        core.DB = old_db


if __name__ == '__main__':
    publish()
