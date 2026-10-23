"""Guide UI + RO/HU content (English recipes live in docs_content.py)."""

from __future__ import annotations

LANGS = ("en", "ro", "hu")
NAMES = {"ro": "Română", "hu": "Magyar", "en": "English"}
ORDER = ("ro", "hu", "en")

RECIPES = {'browse': {'ro': ('Răsfoiți arborele TEMPO',
                   'Găsiți seturi de date și coduri: listați domeniile rădăcină (social, economic, '
                   '…), apoi deschideți o ramură. <code>lang=en</code> sau <code>lang=ro</code> '
                   'alege limba etichetelor din amonte.'),
            'hu': ('TEMPO-fa böngészése',
                   'Adatkészletek és kódok keresése: listázza a gyökérterületeket (társadalmi, '
                   'gazdasági, …), majd nyisson egy ágat. A <code>lang=en</code> vagy '
                   '<code>lang=ro</code> az upstream címkék nyelvét választja.')},
 'meta': {'ro': ('Inspectați o matrice și dimensiunile ei',
                 'Înainte de interogare, inspectați matricea: etichetele dimensiunilor și '
                 'opțiunile <code>nom_item_id</code> pe care le veți trimite în '
                 '<code>selections</code> (ex. <code>POP105A</code>).'),
          'hu': ('Mátrix és dimenziói',
                 'Lekérdezés előtt nézze meg a mátrixot: dimenziócímkék és a '
                 '<code>selections</code>-ben átadandó <code>nom_item_id</code> opciók (pl. '
                 '<code>POP105A</code>).')},
 'query-get': {'ro': ('Interogare rapidă (GET, prietenos în browser)',
                      'Pentru un panou sau o verificare rapidă: fără corp, API-ul alege valori '
                      'implicite (totaluri / ultimul an). Deschideți URL-ul în browser — răspunsul '
                      'este JSON indentat.'),
               'hu': ('Gyors lekérdezés (böngészőbarát GET)',
                      'Irányítópulthoz vagy gyors ellenőrzéshez: törzs nélkül az API ésszerű '
                      'alapértelmezéseket választ (összesen / legutóbbi év). Nyissa meg az URL-t '
                      'böngészőben — a válasz behúzott JSON.')},
 'query-post': {'ro': ('Interogare cu selecții explicite pe dimensiuni',
                       'Alegeți serii cu filtre pe dimensiuni: <code>selections</code> mapează '
                       'fiecare cod de dimensiune la o listă de <code>nom_item_id</code>. Folosiți '
                       'POST când felia e prea mare pentru un query string.'),
                'hu': ('Lekérdezés explicit dimenzióválasztással',
                       'Idősorok dimenziószűrőkkel: a <code>selections</code> minden dimenziókódot '
                       '<code>nom_item_id</code> listához rendel. POST-ot használjon, ha a szelet '
                       'nagyobb, mint ami kényelmesen elfér a query stringben.')},
 'csv': {'ro': ('Descărcați CSV pentru analiză',
                'Un tabel întreg, gata pentru pandas sau Excel: adăugați <code>?format=csv</code> '
                '(POST cu același corp <code>selections</code>). CSV UTF-8 cu antet și punct '
                'zecimal.'),
         'hu': ('CSV letöltése elemzéshez',
                'Teljes tábla pandashoz vagy Excelhez: adja hozzá a <code>?format=csv</code> '
                'paramétert (POST ugyanezzel a <code>selections</code> törzzsel). UTF-8 CSV '
                'fejlécsorral, tizedesponttal.')},
 'news': {'ro': ('Ce a actualizat recent INSSE',
                 'Extras din tabelul de noutăți TEMPO: coduri de matrice, date și domenii — util '
                 'pentru joburi de reîmprospătare.'),
          'hu': ('INSSE legutóbbi frissítései',
                 'A TEMPO hír-táblájából: mátrixkódok, dátumok, területek — frissítő '
                 'feladatokhoz.')},
 'package': {'ro': ('Folosiți pachetul Python',
                    'Pe <a href="https://pypi.org/project/insseption/" target="_blank" rel="noopener">PyPI</a>: '
                    '<code>pip install insseption</code>. <code>Client</code> oglindește '
                    'fiecare rută HTTP și întoarce JSON parsat.'),
             'hu': ('A Python csomag használata',
                    'A <a href="https://pypi.org/project/insseption/" target="_blank" rel="noopener">PyPI</a>-n: '
                    '<code>pip install insseption</code>. A <code>Client</code> minden '
                    'HTTP-útvonalat tükröz, és parse-olt JSON-t ad.')}}

REFERENCE = {'/api/v1/health|GET': {'ro': ('Disponibilitate și accesibilitatea amonte',
                               'JSON: ok, version, upstream_ok, attribution',
                               []),
                        'hu': ('Élőség és upstream elérhetőség',
                               'JSON: ok, version, upstream_ok, attribution',
                               [])},
 '/api/v1/meta|GET': {'ro': ('Metadatele serviciului',
                             'JSON: version, languages, translate_enabled, …',
                             []),
                      'hu': ('Szolgáltatás metaadatai',
                             'JSON: version, languages, translate_enabled, …',
                             [])},
 '/api/v1/context|GET': {'ro': ('Domeniile rădăcină TEMPO',
                                'JSON: nodes[{code,name,…}]',
                                [('lang', 'query', 'ro|en — limba etichetelor')]),
                         'hu': ('TEMPO gyökérterületek',
                                'JSON: nodes[{code,name,…}]',
                                [('lang', 'query', 'ro|en — címkék nyelve')])},
 '/api/v1/context/{code}|GET': {'ro': ('Copiii unui nod de context',
                                       'JSON: nodes (foldere sau matrice)',
                                       [('code', 'path', 'cod context TEMPO'),
                                        ('lang', 'query', 'ro|en')]),
                                'hu': ('Egy kontextuscsomópont gyermekei',
                                       'JSON: nodes (mappák vagy mátrixok)',
                                       [('code', 'path', 'TEMPO kontextuskód'),
                                        ('lang', 'query', 'ro|en')])},
 '/api/v1/matrices/{code}|GET': {'ro': ('Metadate matrice și opțiuni pe dimensiuni',
                                        'JSON: name, dimensions, definition',
                                        [('code', 'path', 'cod matrice'),
                                         ('lang', 'query', 'ro|en')]),
                                 'hu': ('Mátrix metaadat és dimenzióopciók',
                                        'JSON: name, dimensions, definition',
                                        [('code', 'path', 'mátrixkód'),
                                         ('lang', 'query', 'ro|en')])},
 '/api/v1/matrices/{code}/query|GET': {'ro': ('Interogare cu selecții implicite',
                                              'JSON: columns, rows, row_count (sau CSV)',
                                              [('lang', 'query', 'ro|en'),
                                               ('format', 'query', 'json|csv')]),
                                       'hu': ('Lekérdezés alapértelmezett választással',
                                              'JSON: columns, rows, row_count (vagy CSV)',
                                              [('lang', 'query', 'ro|en'),
                                               ('format', 'query', 'json|csv')])},
 '/api/v1/matrices/{code}/query|POST': {'ro': ('Interogare cu corp JSON',
                                               'Rânduri JSON sau CSV',
                                               [('body.lang', 'body', 'ro|en'),
                                                ('body.selections',
                                                 'body',
                                                 'dim_code → [nom_item_id,…]'),
                                                ('format', 'query', 'json|csv')]),
                                        'hu': ('Lekérdezés JSON törzzsel',
                                               'JSON sorok vagy CSV',
                                               [('body.lang', 'body', 'ro|en'),
                                                ('body.selections',
                                                 'body',
                                                 'dim_code → [nom_item_id,…]'),
                                                ('format', 'query', 'json|csv')])},
 '/api/v1/news|GET': {'ro': ('Actualizări recente TEMPO', 'JSON: items, count', []),
                      'hu': ('TEMPO friss frissítések', 'JSON: items, count', [])},
 '/api/v1/translate|POST': {'ro': ('Traducere etichete (OpenRouter)',
                                   'JSON: {target, texts[]}',
                                   [('body.texts', 'body', '1–50 șiruri'),
                                    ('body.target', 'body', 'hu|ro|en')]),
                            'hu': ('Címkefordítás (OpenRouter)',
                                   'JSON: {target, texts[]}',
                                   [('body.texts', 'body', '1–50 szöveg'),
                                    ('body.target', 'body', 'hu|ro|en')])}}

ERRORS = {404: {'ro': 'Cod de matrice necunoscut sau cale invalidă.',
       'hu': 'Ismeretlen mátrixkód vagy érvénytelen útvonal.'},
 422: {'ro': 'Cod invalid, dimensiune goală, nom_item_id necunoscut sau produsul selecțiilor este '
             'prea mare.',
       'hu': 'Hibás kód, üres dimenzió, ismeretlen nom_item_id, vagy a kiválasztás szorzata túl '
             'nagy.'},
 502: {'ro': 'Eroare amonte TEMPO-Online sau răspuns non-JSON.',
       'hu': 'TEMPO-Online upstream hiba vagy nem JSON válasz.'},
 503: {'ro': 'Circuit amonte deschis, sau traducerea dezactivată (fără cheie OpenRouter).',
       'hu': 'Upstream kör megszakítva, vagy fordítás kikapcsolva (nincs OpenRouter kulcs).'}}

CHANGELOG = {'2026-10-23': {'ro': 'v0.1.0 — Tunel API JSON pentru TEMPO-Online, client Python, deploy Traefik '
                      'deploy Traefik, ghid trilingv.',
                'hu': 'v0.1.0 — JSON API-alagút a TEMPO-Online-hoz, Python kliens, Traefik '
                      'telepítés, háromnyelvű útmutató.'}}

COMMENTS = {'// Power Query > Blank Query > Advanced Editor': {'ro': '// Power Query > Blank Query > Advanced '
                                                          'Editor (meniuri în engleză)',
                                                    'hu': '// Power Query > Blank Query > Advanced '
                                                          'Editor (angol menünevek)'},
 '# the package wraps these HTTP calls': {'ro': '# pachetul învelește aceste apeluri HTTP',
                                          'hu': '# a csomag ezeket a HTTP-hívásokat burkolja'},
 '# ids come from c.matrix(...)["dimensions"][*]["options"][*]["nom_item_id"]': {'ro': '# id-urile '
                                                                                       'vin din '
                                                                                       'c.matrix(...)["dimensions"][*]["options"][*]["nom_item_id"]',
                                                                                 'hu': '# az '
                                                                                       'azonosítók: '
                                                                                       'c.matrix(...)["dimensions"][*]["options"][*]["nom_item_id"]'}}

UI = {
    "en": {'html_title': 'Guide',
 'site': 'insseption API',
 'description': 'JSON API for Romania INSSE TEMPO-Online: browse matrices, query dimensions, '
                'download CSV — with examples in curl, Python, R, JavaScript and Excel.',
 'nav_guide': 'About the data',
 'nav_ref': 'For developers',
 'nav_ui': 'App',
 'nav_chat': 'Explore',
 'nav_github': 'GitHub',
 'lang_label': 'Language',
 'h1': 'insseption data API',
 'lead': 'HTTPS JSON tunnel to <b>INSSE TEMPO-Online</b>. Browse the statistical tree, inspect '
         'matrix dimensions, run queries and download CSV — in the browser or from any language. '
         'Unofficial mirror; always credit INSSE.',
 'base_label': 'Base address',
 'btn_ref': 'Interactive reference',
 'btn_ui': 'Open app',
 'fact_open_b': 'Open',
 'fact_open': 'no API key for read endpoints',
 'fact_langs_b': 'RO · EN · HU',
 'fact_langs': 'guide languages (data labels: RO/EN upstream)',
 'fact_formats_b': 'JSON · CSV',
 'fact_formats': 'pretty JSON in the browser; CSV for analysis',
 'fact_client_b': 'Python',
 'fact_client': 'PyPI: pip install insseption',
 'examples_in': 'Examples in',
 'toc_start': 'Quick start',
 'toc_access': 'Access and limits',
 'toc_model': 'How the data is organised',
 'toc_recipes': 'Recipes',
 'toc_catalogue': 'Matrix catalogue',
 'toc_reference': 'Reference',
 'toc_errors': 'Errors and caching',
 'toc_cite': 'Cite the data',
 'toc_history': 'Changes',
 'start': '<ol class="steps">\n'
          '<li><b>Open a URL.</b> Every <code>/api/v1/…</code> response is\n'
          '<code>application/json</code>, indented — paste it in the browser or copy a recipe '
          'below.\n'
          'No key for the read endpoints.</li>\n'
          '<li><b>Ask for a matrix.</b> Population by age and sex (defaults = totals / latest '
          'year):[[START_CODE]]</li>\n'
          '<li><b>Read the answer.</b> Columns, rows and a row count:[[SAMPLE]]\n'
          '<code>columns</code> are dimension labels, <code>rows</code> are the cells (last value '
          'is the\n'
          'measure). Then pick a <a href="#recipes">recipe</a> or a code from the\n'
          '<a href="#catalogue">catalogue</a>.</li></ol>',
 'access': '<p>All <b>read</b> endpoints under <code>/api/v1</code> are <b>open</b>: context,\n'
           'matrix metadata, queries, news and health. No Authorization header. The optional\n'
           '<code>POST /api/v1/translate</code> uses a server-side OpenRouter key (503 if '
           'unset).</p>\n'
           '<p>Practical limits, returned as JSON errors when exceeded:</p>',
 'access_code': '# cell budget per query (rows × measure columns)\n'
                'INSSEPTION_MAX_CELLS=20000   # default; 413 if a selection would exceed it\n'
                '\n'
                '# upstream (HTTP only — this API is the HTTPS front)\n'
                'http://statistici.insse.ro:8077/tempo-ins',
 'access_callout': 'This service is an unofficial HTTPS mirror of INSSE TEMPO-Online. It does not '
                   'replace the national portal and carries no endorsement. Prefer small, precise '
                   'dimension selections over downloading entire matrices.',
 'access_2': '<p>Responses advertise short public caching; the process also keeps in-memory TTLs '
             'for context/metadata (24h), news (1h) and query results (6h).</p>',
 'h_limits': 'Limits',
 'model': '<p>TEMPO organises statistics as a <b>tree of contexts</b> that ends in\n'
          '<b>matrices</b> (codes like <code>POP105A</code>). Each matrix has <b>dimensions</b>\n'
          '(age, sex, year, …); every option has a <code>nom_item_id</code> you pass in a '
          'query.</p>\n'
          '<ul>\n'
          '<li><code>GET /api/v1/context</code> — root domains; <code>/context/{code}</code> opens '
          'a branch;</li>\n'
          '<li><code>GET /api/v1/matrices/{code}</code> — labels, dimensions and option ids;</li>\n'
          '<li><code>GET|POST /api/v1/matrices/{code}/query</code> — cells as JSON (or\n'
          '<code>?format=csv</code>);</li>\n'
          '<li><code>GET /api/v1/news</code> — what INSSE published recently.</li>\n'
          '</ul>\n'
          '<p class="muted">Upstream talks HTTP only (<code>statistici.insse.ro:8077</code>). '
          'Other clients:\n'
          '<code>RProjectRomania/TEMPO</code>, <code>ins.gov2.ro</code>.</p>',
 'recipes': '<p>Complete examples for common tasks. Pick a language in the bar above: it applies '
            'to the whole page.</p>',
 'catalogue': '<p>Matrices from the shipped catalogue (searchable). “meta” opens dimensions and '
              'option ids; “query” runs the GET defaults.</p>',
 'filter_placeholder': 'Filter: POP105A, population, labour…',
 'filter_label': 'Filter the catalogue',
 'cat_about': 'meta',
 'cat_empty': 'The list could not be loaded just now — try <code>/api/v1/context</code>.',
 'cat_head': ['Code', 'Name', ''],
 'reference': '<p>Every endpoint. For Try-it-out open the <a href="/docs/reference">interactive '
              'reference</a> (same OpenAPI as <code>/openapi.json</code>).</p>',
 'ref_head': ['Endpoint', 'Access', 'What it returns'],
 'eg': 'e.g.',
 'badge_open': 'open',
 'errors': '<p>Errors come as JSON with a single shape: <code>{"error": {"code", "message", '
           '"upstream_status?"}}</code>. A wrong request says what is wrong in '
           '<code>message</code>.</p>',
 'err_head': ['Status', '', 'When'],
 'h_formats': 'Formats',
 'formats': '<p>JSON is UTF-8, indented for browsers (<code>application/json</code>). Queries '
            'accept <code>?format=csv</code> for a UTF-8 CSV with a header row (dot decimal '
            'separator). <code>GET</code> uses defaults; <code>POST</code> sends explicit '
            '<code>selections</code>.</p>',
 'h_caching': 'Caching',
 'caching': '<p>Every answer carries <code>Cache-Control: public, max-age=60</code>. The process '
            'also caches context/metadata (24h), news (1h) and queries (6h) in memory. Force a '
            'refresh by waiting out the TTL or restarting the service.</p>',
 'h_web': 'From a web page',
 'web': '<p>Open endpoints can be called from any website (CORS). Always credit INSSE '
        'TEMPO-Online. Reuse terms: <a '
        'href="https://insse.ro/cms/ro/content/reutilizarea-statisticilor-sse" target="_blank" '
        'rel="noopener">INSSE</a>.</p>',
 'cite': '<p>Name <b>INSSE</b> and this API, and point at the matrix or query you used:</p>',
 'cite_text': 'National Institute of Statistics (Romania), TEMPO-Online, via insseption ({YEAR}): '
              '{URL}, accessed {DATE}.',
 'cite_note': 'Replace the URL with the matrix or query you used.',
 'cite_software': '<p><b>Software.</b> <code>insseption</code> is <b>MIT</b>-licensed by '
                  '<a href="https://github.com/csaladenes" target="_blank" rel="noopener">Dénes Csala</a> '
                  '(<a href="[[GITHUB]]" target="_blank" rel="noopener">[[GITHUB]]</a>), hosted on the '
                  '<a href="[[ROEM]]" target="_blank" rel="noopener">ROEM</a> AWS / Traefik stack. '
                  'Data remains subject to '
                  '<a href="[[INSSE]]" target="_blank" rel="noopener">INSSE</a> reuse terms.</p>',
 'history_note': 'Documentation version [[VERSION]]. Breaking changes will get a new path '
                 '(<code>/api/v2</code>); <code>/api/v1</code> stays.',
 'copy': 'Copy',
 'copied': 'Copied',
 'open_answer': 'Open the answer ↗',
 'only_shown': 'This one is shown in [[NAMES]].',
 'key_invalid': 'A key has letters, digits, - and _ only',
 'title_no_key': 'Open — no key needed',
 'title_with_key': 'Opens with your key in the address',
 'freq': {}},
}

UI["ro"] = {'html_title': 'Ghid',
 'site': 'insseption API',
 'description': 'API JSON pentru TEMPO-Online INSSE: răsfoiți matrice, interogați dimensiuni, '
                'descărcați CSV — cu exemple în curl, Python, R, JavaScript și Excel.',
 'nav_guide': 'Despre date',
 'nav_ref': 'Pentru dezvoltatori',
 'nav_ui': 'Aplicație',
 'nav_chat': 'Explorează',
 'nav_github': 'GitHub',
 'lang_label': 'Limbă',
 'h1': 'API de date insseption',
 'lead': 'Tunel HTTPS JSON către <b>INSSE TEMPO-Online</b>. Răsfoiți arborele statistic, '
         'inspectați dimensiunile, rulați interogări și descărcați CSV — în browser sau din orice '
         'limbă. Oglindă neoficială; citați întotdeauna INSSE.',
 'base_label': 'Adresa de bază',
 'btn_ref': 'Referință interactivă',
 'btn_ui': 'Deschide aplicația',
 'fact_open_b': 'Deschis',
 'fact_open': 'fără cheie API pentru endpoint-urile de citire',
 'fact_langs_b': 'RO · EN · HU',
 'fact_langs': 'limbi ale ghidului (etichete date: RO/EN amonte)',
 'fact_formats_b': 'JSON · CSV',
 'fact_formats': 'JSON indentat în browser; CSV pentru analiză',
 'fact_client_b': 'Python',
 'fact_client': 'PyPI: pip install insseption',
 'examples_in': 'Exemple în',
 'toc_start': 'Start rapid',
 'toc_access': 'Acces și limite',
 'toc_model': 'Cum sunt organizate datele',
 'toc_recipes': 'Exemple',
 'toc_catalogue': 'Catalog de matrice',
 'toc_reference': 'Referință',
 'toc_errors': 'Erori și cache',
 'toc_cite': 'Citarea datelor',
 'toc_history': 'Modificări',
 'start': '<ol class="steps">\n'
          '<li><b>Deschideți un URL.</b> Orice răspuns <code>/api/v1/…</code> este\n'
          '<code>application/json</code>, indentat — lipiți-l în browser sau copiați un exemplu de '
          'mai jos.\n'
          'Fără cheie pentru citire.</li>\n'
          '<li><b>Cereți o matrice.</b> Populație pe vârstă și sex (implicite = totaluri / ultimul '
          'an):[[START_CODE]]</li>\n'
          '<li><b>Citiți răspunsul.</b> Coloane, rânduri și numărul de rânduri:[[SAMPLE]]\n'
          '<code>columns</code> sunt etichetele dimensiunilor, <code>rows</code> sunt celulele '
          '(ultima\n'
          'valoare e măsura). Apoi alegeți un <a href="#recipes">exemplu</a> sau un cod din\n'
          '<a href="#catalogue">catalog</a>.</li></ol>',
 'access': '<p>Toate endpoint-urile de <b>citire</b> de sub <code>/api/v1</code> sunt '
           '<b>deschise</b>:\n'
           'context, metadate, interogări, știri și health. Fără antet Authorization. Opționalul\n'
           '<code>POST /api/v1/translate</code> folosește o cheie OpenRouter pe server (503 dacă '
           'lipsește).</p>\n'
           '<p>Limite practice, returnate ca erori JSON când sunt depășite:</p>',
 'access_code': '# cell budget per query (rows × measure columns)\n'
                'INSSEPTION_MAX_CELLS=20000   # default; 413 if a selection would exceed it\n'
                '\n'
                '# upstream (HTTP only — this API is the HTTPS front)\n'
                'http://statistici.insse.ro:8077/tempo-ins',
 'access_callout': 'Acest serviciu este o oglindă HTTPS neoficială a TEMPO-Online INSSE. Nu '
                   'înlocuiește portalul național și nu implică vreun endorsement. Preferăți '
                   'selecții mici și precise în loc să descărcați matrice întregi.',
 'access_2': '<p>Răspunsurile anunță un cache public scurt; procesul păstrează și TTL-uri în '
             'memorie pentru context/metadate (24h), știri (1h) și rezultate de interogare '
             '(6h).</p>',
 'h_limits': 'Limite',
 'model': '<p>TEMPO organizează statisticile ca un <b>arbore de contexte</b> care se termină în\n'
          '<b>matrice</b> (coduri precum <code>POP105A</code>). Fiecare matrice are '
          '<b>dimensiuni</b>\n'
          '(vârstă, sex, an, …); fiecare opțiune are un <code>nom_item_id</code> pe care îl '
          'trimiteți\n'
          'într-o interogare.</p>\n'
          '<ul>\n'
          '<li><code>GET /api/v1/context</code> — domenii rădăcină; <code>/context/{code}</code> '
          'deschide o ramură;</li>\n'
          '<li><code>GET /api/v1/matrices/{code}</code> — etichete, dimensiuni și id-uri de '
          'opțiuni;</li>\n'
          '<li><code>GET|POST /api/v1/matrices/{code}/query</code> — celule ca JSON (sau\n'
          '<code>?format=csv</code>);</li>\n'
          '<li><code>GET /api/v1/news</code> — ce a publicat recent INSSE.</li>\n'
          '</ul>\n'
          '<p class="muted">Amonte vorbește doar HTTP (<code>statistici.insse.ro:8077</code>). '
          'Alți clienți:\n'
          '<code>RProjectRomania/TEMPO</code>, <code>ins.gov2.ro</code>.</p>',
 'recipes': '<p>Exemple complete pentru sarcini uzuale. Alegeți o limbă în bara de mai sus: se '
            'aplică întregii pagini.</p>',
 'catalogue': '<p>Matrice din catalogul livrat (căutabil). „meta” deschide dimensiunile și '
              'id-urile; „query” rulează implicitele GET.</p>',
 'filter_placeholder': 'Filtru: POP105A, populație, forță de muncă…',
 'filter_label': 'Filtrați catalogul',
 'cat_about': 'meta',
 'cat_empty': 'Lista nu a putut fi încărcată acum — încercați <code>/api/v1/context</code>.',
 'cat_head': ['Code', 'Name', ''],
 'reference': '<p>Fiecare endpoint. Pentru Try-it-out deschideți <a '
              'href="/docs/reference">referința interactivă</a> (același OpenAPI ca '
              '<code>/openapi.json</code>).</p>',
 'ref_head': ['Endpoint', 'Access', 'What it returns'],
 'eg': 'ex.',
 'badge_open': 'deschis',
 'errors': '<p>Erorile vin ca JSON într-o singură formă: <code>{"error": {"code", "message", '
           '"upstream_status?"}}</code>. O cerere greșită spune ce e greșit în '
           '<code>message</code>.</p>',
 'err_head': ['Status', '', 'When'],
 'h_formats': 'Formate',
 'formats': '<p>JSON este UTF-8, indentat pentru browsere (<code>application/json</code>). '
            'Interogările acceptă <code>?format=csv</code> pentru CSV UTF-8 cu antet (separator '
            'zecimal punct). <code>GET</code> folosește implicite; <code>POST</code> trimite '
            '<code>selections</code> explicite.</p>',
 'h_caching': 'Cache',
 'caching': '<p>Fiecare răspuns poartă <code>Cache-Control: public, max-age=60</code>. Procesul '
            'cache-uiește și în memorie context/metadate (24h), știri (1h) și interogări (6h).</p>',
 'h_web': 'Dintr-o pagină web',
 'web': '<p>Endpoint-urile deschise pot fi apelate de pe orice site (CORS). Citați întotdeauna '
        'INSSE TEMPO-Online. Termeni: <a '
        'href="https://insse.ro/cms/ro/content/reutilizarea-statisticilor-sse" target="_blank" '
        'rel="noopener">INSSE</a>.</p>',
 'cite': '<p>Menționați <b>INSSE</b> și acest API, și indicați matricea sau interogarea folosită:</p>',
 'cite_text': 'Institutul Național de Statistică (România), TEMPO-Online, via insseption ({YEAR}): '
              '{URL}, accesat la {DATE}.',
 'cite_note': 'Înlocuiți URL-ul cu matricea sau interogarea folosită.',
 'cite_software': '<p><b>Software.</b> <code>insseption</code> este licențiat <b>MIT</b> de '
                  '<a href="https://github.com/csaladenes" target="_blank" rel="noopener">Dénes Csala</a> '
                  '(<a href="[[GITHUB]]" target="_blank" rel="noopener">[[GITHUB]]</a>), găzduit pe stiva '
                  'AWS / Traefik <a href="[[ROEM]]" target="_blank" rel="noopener">ROEM</a>. '
                  'Datele rămân sub termenii '
                  '<a href="[[INSSE]]" target="_blank" rel="noopener">INSSE</a>.</p>',
 'history_note': 'Versiunea documentației [[VERSION]]. Schimbările care sparg apelurile existente '
                 'vor primi o cale nouă (<code>/api/v2</code>); <code>/api/v1</code> rămâne.',
 'copy': 'Copiază',
 'copied': 'Copiat',
 'open_answer': 'Deschideți răspunsul ↗',
 'only_shown': 'Acesta este afișat în [[NAMES]].',
 'key_invalid': 'O cheie are doar litere, cifre, - și _',
 'title_no_key': 'Deschis — fără cheie',
 'title_with_key': 'Se deschide cu cheia în adresă',
 'freq': {}}

UI["hu"] = {'html_title': 'Útmutató',
 'site': 'insseption API',
 'description': 'JSON API a romániai INSSE TEMPO-Online-hoz: mátrixok böngészése, dimenziók '
                'lekérdezése, CSV letöltés — példákkal curl, Python, R, JavaScript és Excel '
                'nyelven.',
 'nav_guide': 'Az adatokról',
 'nav_ref': 'Fejlesztőknek',
 'nav_ui': 'Alkalmazás',
 'nav_chat': 'Felfedezés',
 'nav_github': 'GitHub',
 'lang_label': 'Nyelv',
 'h1': 'insseption adat-API',
 'lead': 'HTTPS JSON-alagút az <b>INSSE TEMPO-Online</b>-hoz. Böngéssze a statisztikai fát, nézze '
         'meg a dimenziókat, futtasson lekérdezéseket és töltsön le CSV-t — böngészőben vagy '
         'bármely nyelvből. Nem hivatalos tükör; mindig tüntesse fel az INSSE-t.',
 'base_label': 'Alapcím',
 'btn_ref': 'Interaktív referencia',
 'btn_ui': 'Alkalmazás megnyitása',
 'fact_open_b': 'Nyílt',
 'fact_open': 'nincs API-kulcs az olvasó végpontokhoz',
 'fact_langs_b': 'RO · EN · HU',
 'fact_langs': 'útmutató nyelvei (adatcímkék: RO/EN upstream)',
 'fact_formats_b': 'JSON · CSV',
 'fact_formats': 'behúzott JSON a böngészőben; CSV elemzéshez',
 'fact_client_b': 'Python',
 'fact_client': 'PyPI: pip install insseption',
 'examples_in': 'Példák',
 'toc_start': 'Gyors kezdés',
 'toc_access': 'Hozzáférés és korlátok',
 'toc_model': 'Hogyan vannak az adatok felépítve',
 'toc_recipes': 'Példák',
 'toc_catalogue': 'Mátrixkatalógus',
 'toc_reference': 'Referencia',
 'toc_errors': 'Hibák és gyorsítótár',
 'toc_cite': 'Az adatok idézése',
 'toc_history': 'Változások',
 'start': '<ol class="steps">\n'
          '<li><b>Nyisson meg egy URL-t.</b> Minden <code>/api/v1/…</code> válasz\n'
          '<code>application/json</code>, behúzva — illessze be a böngészőbe, vagy másoljon egy '
          'receptet lent.\n'
          'Olvasáshoz nincs kulcs.</li>\n'
          '<li><b>Kérjen egy mátrixot.</b> Népesség kor és nem szerint (alapértelmezés = összesen '
          '/ legutóbbi év):[[START_CODE]]</li>\n'
          '<li><b>Olvassa el a választ.</b> Oszlopok, sorok és sorszám:[[SAMPLE]]\n'
          'A <code>columns</code> a dimenziócímkék, a <code>rows</code> a cellák (az utolsó érték '
          'a mutató).\n'
          'Ezután válasszon egy <a href="#recipes">példát</a> vagy egy kódot a\n'
          '<a href="#catalogue">katalógusból</a>.</li></ol>',
 'access': '<p>Az <code>/api/v1</code> alatti összes <b>olvasó</b> végpont <b>nyílt</b>: '
           'kontextus,\n'
           'mátrix-metaadat, lekérdezések, hírek és health. Nincs Authorization fejléc. Az '
           'opcionális\n'
           '<code>POST /api/v1/translate</code> szerveroldali OpenRouter-kulcsot használ (503, ha '
           'nincs beállítva).</p>\n'
           '<p>Gyakorlati korlátok — túllépéskor JSON hibaként:</p>',
 'access_code': '# cell budget per query (rows × measure columns)\n'
                'INSSEPTION_MAX_CELLS=20000   # default; 413 if a selection would exceed it\n'
                '\n'
                '# upstream (HTTP only — this API is the HTTPS front)\n'
                'http://statistici.insse.ro:8077/tempo-ins',
 'access_callout': 'Ez a szolgáltatás az INSSE TEMPO-Online nem hivatalos HTTPS-tükre. Nem '
                   'helyettesíti a nemzeti portált, és nem jelent támogatást. Kis, pontos '
                   'dimenzióválasztást részesítsen előnyben a teljes mátrixok letöltésével '
                   'szemben.',
 'access_2': '<p>A válaszok rövid nyilvános cache-t hirdetnek; a folyamat memóriában is tart '
             'TTL-eket kontextus/meta (24ó), hírek (1ó) és lekérdezések (6ó) számára.</p>',
 'h_limits': 'Korlátok',
 'model': '<p>A TEMPO a statisztikákat <b>kontextusfában</b> szervezi, amely\n'
          '<b>mátrixokban</b> végződik (pl. <code>POP105A</code>). Minden mátrixnak vannak\n'
          '<b>dimenziói</b> (kor, nem, év, …); minden opciónak <code>nom_item_id</code>-ja van, '
          'amelyet\n'
          'a lekérdezésben ad át.</p>\n'
          '<ul>\n'
          '<li><code>GET /api/v1/context</code> — gyökérterületek; a <code>/context/{code}</code> '
          'ágat nyit;</li>\n'
          '<li><code>GET /api/v1/matrices/{code}</code> — címkék, dimenziók és '
          'opció-azonosítók;</li>\n'
          '<li><code>GET|POST /api/v1/matrices/{code}/query</code> — cellák JSON-ként (vagy\n'
          '<code>?format=csv</code>);</li>\n'
          '<li><code>GET /api/v1/news</code> — mit tett közzé nemrég az INSSE.</li>\n'
          '</ul>\n'
          '<p class="muted">Az upstream csak HTTP-t beszél '
          '(<code>statistici.insse.ro:8077</code>). Más kliensek:\n'
          '<code>RProjectRomania/TEMPO</code>, <code>ins.gov2.ro</code>.</p>',
 'recipes': '<p>Teljes példák gyakori feladatokra. Válasszon nyelvet a fenti sávban: az egész '
            'oldalra érvényes.</p>',
 'catalogue': '<p>A szállított katalógus mátrixai (kereshetők). A „meta” a dimenziókat és '
              'azonosítókat nyitja; a „query” a GET-alapértelmezéseket futtatja.</p>',
 'filter_placeholder': 'Szűrés: POP105A, népesség, munkaerő…',
 'filter_label': 'Katalógusszűrő',
 'cat_about': 'meta',
 'cat_empty': 'A lista most nem tölthető be — próbálja: <code>/api/v1/context</code>.',
 'cat_head': ['Code', 'Name', ''],
 'reference': '<p>Minden végpont. Kipróbáláshoz: <a href="/docs/reference">interaktív '
              'referencia</a> (ugyanaz az OpenAPI, mint a <code>/openapi.json</code>).</p>',
 'ref_head': ['Endpoint', 'Access', 'What it returns'],
 'eg': 'pl.',
 'badge_open': 'nyílt',
 'errors': '<p>A hibák egyetlen JSON-alakban jönnek: <code>{"error": {"code", "message", '
           '"upstream_status?"}}</code>. Hibás kérésnél a <code>message</code> megmondja, mi a '
           'baj.</p>',
 'err_head': ['Status', '', 'When'],
 'h_formats': 'Formátumok',
 'formats': '<p>A JSON UTF-8, böngészőhöz behúzva (<code>application/json</code>). A lekérdezések '
            'elfogadják a <code>?format=csv</code> paramétert (UTF-8 CSV, fejlécsor, tizedespont). '
            'A <code>GET</code> alapértékeket használ; a <code>POST</code> explicit '
            '<code>selections</code>-t küld.</p>',
 'h_caching': 'Gyorsítótár',
 'caching': '<p>Minden válasz visel <code>Cache-Control: public, max-age=60</code> fejlécet. A '
            'folyamat memóriában is cache-eli a kontextust/metát (24ó), híreket (1ó) és '
            'lekérdezéseket (6ó).</p>',
 'h_web': 'Weboldalról',
 'web': '<p>A nyílt végpontok bármely webhelyről hívhatók (CORS). Mindig tüntesse fel: INSSE '
        'TEMPO-Online. Feltételek: <a '
        'href="https://insse.ro/cms/ro/content/reutilizarea-statisticilor-sse" target="_blank" '
        'rel="noopener">INSSE</a>.</p>',
 'cite': '<p>Nevezze meg az <b>INSSE</b>-t és ezt az API-t, és adja meg a használt mátrixot vagy '
         'lekérdezést:</p>',
 'cite_text': 'Románia Országos Statisztikai Intézete, TEMPO-Online, insseptionen keresztül '
              '({YEAR}): {URL}, letöltve: {DATE}.',
 'cite_note': 'Cserélje az URL-t a használt mátrixra vagy lekérdezésre.',
 'cite_software': '<p><b>Szoftver.</b> Az <code>insseption</code> <b>MIT</b> licencű, szerző: '
                  '<a href="https://github.com/csaladenes" target="_blank" rel="noopener">Dénes Csala</a> '
                  '(<a href="[[GITHUB]]" target="_blank" rel="noopener">[[GITHUB]]</a>), a '
                  '<a href="[[ROEM]]" target="_blank" rel="noopener">ROEM</a> AWS / Traefik stacken '
                  'hostolva. Az adatok az '
                  '<a href="[[INSSE]]" target="_blank" rel="noopener">INSSE</a> újrahasználati '
                  'feltételei alá tartoznak.</p>',
 'history_note': 'Dokumentáció verziója: [[VERSION]]. A meglévő hívásokat törő változások új '
                 'útvonalat kapnak (<code>/api/v2</code>); a <code>/api/v1</code> megmarad.',
 'copy': 'Másolás',
 'copied': 'Másolva',
 'open_answer': 'A válasz megnyitása ↗',
 'only_shown': 'Ez jelenik meg: [[NAMES]].',
 'key_invalid': 'A kulcs csak betűket, számokat, - és _ jeleket tartalmazhat',
 'title_no_key': 'Nyílt — nincs kulcs',
 'title_with_key': 'A kulccsal nyílik a címben',
 'freq': {}}
