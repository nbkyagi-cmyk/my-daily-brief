# NHK ONE exclusion (2026-10-05 JST)

The configured RSS endpoint https://www.nhk.or.jp/rss/news/cat4.xml
redirected to https://news.web.nhk/n-data/conf/na/rss/cat4.xml during
verification. Its channel title was `NHKONEニュース|政治`, and article
links used `https://news.web.nhk/newsweb/na/nd-…`.
An actual stored article page also contained NHK ONE branding.

Exclude only the normalized hostname `news.web.nhk` with path
`/newsweb` or `/newsweb/…`. Do not use article titles, summaries, source
labels, or a blanket NHK domain exclusion. Ordinary `nhk.or.jp` links
remain eligible. This rule identifies direct links in the current feeds;
it does not probe arbitrary redirects or infer that unrelated NHK URLs
require an account. Recheck the rule if NHK changes feed link formats.

The parser filters before its 20-article limit, persistence, and AI selection.
AI selection and public-history restoration also enforce the same rule.
Local DB snapshots and exports hide previously stored matching articles.
Valid feeds containing only excluded articles count as successful empty
updates. Communication/XML errors still fail. Restoration validates the
entire original history before filtering and never analyzes old articles.
Publishing writes filtered history even when no new articles are added.

Both public JSON files originally contained 70 articles: 68 matching NHK
ONE URLs and two MLIT articles. Only those 68 rows were removed. The two
surviving rows and payload metadata were checked against the original
Git version for exact equality. There were no ordinary NHK articles in
that history; synthetic ordinary NHK articles remain eligible in tests.

Validation: all 35 unittest tests passed, including Node UI behavior,
daily publishing, preserved history, AI category selection/budgets,
RSS/Atom exclusion, exact host/path boundaries, and title false positives.
No real OpenAI API call or production daily update was run for this repair.
The 18:07 JST schedule, AI limit, category priorities, sources, and UI
assets were left unchanged. No secrets, DBs, or backups are included.
