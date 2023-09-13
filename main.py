from time import time, sleep, strftime
from urllib.parse import quote, quote_plus
from typing import TypedDict

import requests
import pywikibot as pwb


PETSCAN_ENDPOINT = 'https://petscan.wmflabs.org/'
WDQS_ENDPOINT = 'https://query.wikidata.org/sparql'
HEADERS = {
    'User-Agent': f'{requests.utils.default_headers()["User-Agent"]} (Wikidata ' \
                   ' bot by User:MisterSynergy; mailto:mister.synergy@yahoo.com)'
}
LANGUAGE_MAPPINGS:dict[str, str] = {
    'en-simple' : 'simple',
    'nb' : 'no',
    'yue' : 'zh-yue',
}
NAMESPACES:dict[int, str] = {
    0 : '',
    4 : 'Wikipedia',
    10 : 'Template',
    12 : 'Help',
    14 : 'Category'
}


class PetscanEntryDict(TypedDict):
    id : int
    len : int
    n : str
    namespace : int
    nstext : str
    title : str
    touched : str


def petscan_unconnected_pages(language:str, category:str) -> list[PetscanEntryDict]:
    response = requests.get(
        url=PETSCAN_ENDPOINT,
        headers=HEADERS,
        params={
            'language' : language,
            'project' : 'wikipedia',
            'categories' : category,
            'depth' : '12',
            'wikidata_item' : 'without',
            'show_redirects' : 'no',
            'format' : 'json',
            'doit' : '1'
        }
    )

    if response.status_code != 200:
        raise RuntimeWarning()

    payload = response.json()
    if '*' not in payload:
        raise RuntimeError()
    
    return payload.get('*', [])[0].get('a', {}).get('*', [])


def sparql_interwikilinks_for_entity(qid:str) -> list[dict[str, dict[str, str]]]:
    query = f"""SELECT ?sitelink WHERE {{
  BIND(wd:{qid} AS ?item) .
  ?item wdt:P31/wdt:P279* wd:Q4167836 .
  ?item ^schema:about [ schema:isPartOf/wikibase:wikiGroup 'wikipedia'; schema:name ?sitelink ] .
}}"""

    response = requests.post(
        url=WDQS_ENDPOINT,
        headers=HEADERS,
        data={
            'format' : 'json',
            'query' : query
        }
    )

    payload = response.json()

    return payload.get('results', {}).get('bindings', [])


def write_to_wikipage(report_page_title:str, wikitext:str) -> None:
    wikidata_site = pwb.Site(code='wikidata', fam='wikidata')
    wikidata_site.login()

    page = pwb.Page(wikidata_site, report_page_title)
    page.text = wikitext
    page.save(
        summary='update page (weekly job via Toolforge) #msynbot #unapproved',
        watch='nochange',
        minor=True,
        quiet=True
    )


def get_title_and_lang(interwikilink:dict[str, dict[str, str]]) -> tuple[str, str]:
    # remove namespace prefixes
    page_title = ''.join(interwikilink.get('sitelink', {}).get('value', '').partition(':')[2:])

    language_raw = interwikilink.get('sitelink', {}).get('xml:lang', '')
    language = LANGUAGE_MAPPINGS.get(language_raw, language_raw)

    return language, page_title


def process_local_category(interwikilink:dict[str, dict[str, str]], dump_file:str) -> None:
    language, category = get_title_and_lang(interwikilink)

    try:
        petscan_result = petscan_unconnected_pages(language, category)
    except RuntimeWarning: # petscan not successful
        return
    except RuntimeError: # no results returned
        return
    if len(petscan_result) == 0: # empty result
        return

    with open(dump_file, mode='a', encoding='utf8') as file_handle:
        for row in petscan_result:
            if 'q' in row: # has Wikidata item
                continue
            if row.get('namespace') not in NAMESPACES: # irrelevant namespace
                continue

            if row.get('namespace') != 0:
                formatted_namespace = f'{NAMESPACES.get(row.get("namespace", 0), "")}:'
            else:
                formatted_namespace = ''

            file_handle.write(f'{language}\t{NAMESPACES.get(row.get("namespace", 0), "")}' \
                              f'\t{formatted_namespace}{row.get("title", "")}\n')


def renew_task(category_qid:str, dump_file:str) -> None:
    with open(dump_file, mode='w', encoding='utf8') as file_handle:
        file_handle.write(f'# file generated: {int(time()):d}\n')

    interwikilinks = sparql_interwikilinks_for_entity(category_qid)

    for interwikilink in interwikilinks:
        process_local_category(interwikilink, dump_file)
        sleep(1) # between petscan requests


def load_dump_file(dump_file:str) -> list[str]:
    lines = []

    with open(dump_file, mode='r', encoding='utf8') as file_handle:
        for line in file_handle:
            if line.strip().startswith('#'):
                continue
            lines.append(line.strip())

    return lines


def print_task(category_qid:str, dump_file:str, report_page_title:str) -> None:
    intro = f"""{{{{User:MisterSynergy/header}}}}
List of all pages categorized (including subcategories) in any of the (Wikipedia) sitelinks of {{{{Q|{category_qid}}}}} that are not linked to a Wikidata item. Latest update: {strftime("%-d %B %Y, ~%-H:%M (UTC)")}.
"""

    table_header = """{| class="wikitable sortable"
|-
! cnt !! project !! namespace !! pagetitle !! duplicity !! find in Wikidata !! new item
"""

    table_row = """|-
| {cnt}
| {language}
| {ns}
| [[:{language}:{full_page_title}]]
| [//wikidata-todo.toolforge.org/duplicity.php?wiki={language}wiki&norand=1&page={full_page_title_escaped} duplicity]
| [//www.wikidata.org/w/index.php?&search={full_page_title_quote_plus} find in Wikidata]
| [//www.wikidata.org/wiki/Special:NewItem?site={language}wiki&page={full_page_title_escaped}&label={full_page_title_escaped}&lang={language} create]
"""

    table_footer = """|}"""

    wikitext = intro + table_header

    for cnt, line in enumerate(load_dump_file(dump_file), start=1):
        lang, namespace, page_title = line.split('\t')
        page_title = page_title.replace('_', ' ')

        wikitext = wikitext + table_row.format(
            cnt=cnt,
            language=lang,
            ns=namespace,
            full_page_title=page_title,
            full_page_title_escaped=quote(page_title),
            full_page_title_quote_plus=quote_plus(page_title)
        )

    wikitext = wikitext + table_footer

    ## write output to wiki page ##
    write_to_wikipage(report_page_title, wikitext)


def main() -> None:
    task = 'unconnected_pages'

    # rowing Q8683464
    # triathlon Q7390897
    # tennis Q5325416
    # rowing templates Q8683771
    # wikiproject rowing Q8918930
    # portal rowing Q9086734
    # rowing files Q8929960
    category_qid = 'Q8683464'
    dump_file = f'logs/{task}_{category_qid}.txt'
    report_page_title = 'User:MisterSynergy/rowing/unconnected_pages'

    renew_task(category_qid, dump_file)
    print_task(category_qid, dump_file, report_page_title)


if __name__ == '__main__':
    main()
