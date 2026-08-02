#!/usr/bin/env python3
"""Generate the English site under en/ from the French pages at the root.

Why this exists
---------------
Both languages used to live on one URL, swapped by JavaScript. Google indexes
URLs, not toggle states, so the English content was effectively invisible in
search. Now French lives at /page.html and English at /en/page.html, and the
two are declared to each other with hreflang.

The French files stay the single source of truth. English text already lives
inside them (in the JS dictionaries, or in the hidden [data-lang-block="en"]
sections), so this script does not translate anything — it re-points URLs,
forces the page language, and turns the FR/EN buttons into real links.

Run after editing any French page:

    python3 build-en.py
"""
import os
import re
import shutil

SITE = 'https://piecesautochateauguay.ca'

# french file  ->  english file (English slugs rank better for English queries)
PAGES = {
    'index.html':                'index.html',
    'infolettre.html':           'newsletter.html',
    'conditions.html':           'terms.html',
    'confidentialite.html':      'privacy.html',
    'politique-de-temoins.html': 'cookie-policy.html',
}

# english <title> and meta description for each generated page
META = {
    'index.html': (
        "Auto Parts in Châteauguay, Sainte-Martine and Saint-Rémi",
        "Auto parts, tools and equipment for repair shops and drivers. "
        "Three locations in the Montérégie: Châteauguay, Sainte-Martine and Saint-Rémi."),
    'newsletter.html': (
        "Newsletter — Pièces Auto Châteauguay",
        "Sign up for our newsletter: supplier promotions, new catalogues and new arrivals."),
    'terms.html': (
        "Terms — Pièces Auto Châteauguay",
        "Terms of use, sale and returns for Pièces d'autos Châteauguay inc."),
    'privacy.html': (
        "Privacy Policy — Pièces Auto Châteauguay",
        "Personal information we collect, how it is used and retained, and your rights under Law 25."),
    'cookie-policy.html': (
        "Cookie Policy — Pièces Auto Châteauguay",
        "Cookies used on this site, what they are for, and how to manage your preferences."),
}

OUT = 'en'


def fr_url(fr):
    return f'{SITE}/' if fr == 'index.html' else f'{SITE}/{fr}'


def en_url(en):
    return f'{SITE}/en/' if en == 'index.html' else f'{SITE}/en/{en}'


def hreflang_block(fr, en):
    """Each page declares itself, its counterpart, and the default."""
    return (
        f'<link rel="alternate" hreflang="fr-CA" href="{fr_url(fr)}">\n'
        f'<link rel="alternate" hreflang="en-CA" href="{en_url(en)}">\n'
        f'<link rel="alternate" hreflang="x-default" href="{fr_url(fr)}">'
    )


def switcher_script(target_href, other_lang):
    """Replace the in-place toggle with navigation to the other language's URL.

    Cloning each button drops the listener the page already attached, so the
    original swap-in-place behaviour cannot fire alongside this one.
    """
    return f'''
<script>
/* Language is a URL, not a toggle. The button for the other language
   navigates; the button for this page's language does nothing. */
(function(){{
  document.querySelectorAll('.lang button').forEach(function(btn){{
    var fresh = btn.cloneNode(true);
    btn.parentNode.replaceChild(fresh, btn);
    if (fresh.dataset.lang === '{other_lang}') {{
      fresh.addEventListener('click', function(){{
        try {{ localStorage.setItem('pac-lang', '{other_lang}'); }} catch(e){{}}
        location.href = '{target_href}';
      }});
    }}
  }});
}})();
</script>
'''


def build_english(fr, en):
    s = open(fr, encoding='utf-8').read()

    # 1. page language
    s = s.replace('<html lang="fr">', '<html lang="en">', 1)

    # 2. assets sit one level up from en/. This covers markup attributes and the
    #    single-quoted paths inside the BRANCHES / DOCS data in index.html.
    #    og:image and the JSON-LD images are already absolute URLs, so they are
    #    untouched and stay correct from any directory depth.
    s = s.replace('href="assets/', 'href="../assets/')
    s = s.replace('src="assets/', 'src="../assets/')
    s = s.replace("'assets/", "'../assets/")

    # 3. internal links point at the English siblings
    for f_from, f_to in PAGES.items():
        s = s.replace(f'href="{f_from}"', f'href="{f_to}"')

    # 4. canonical + hreflang
    s = re.sub(r'<link rel="canonical"[^>]*>',
               f'<link rel="canonical" href="{en_url(en)}">', s, count=1)
    s = re.sub(r'(<link rel="alternate" hreflang="[^"]*"[^>]*>\s*)+',
               hreflang_block(fr, en) + '\n', s, count=1)

    # 5. social tags describe the English page
    title, desc = META[en]
    s = re.sub(r'<meta property="og:url" content="[^"]*">',
               f'<meta property="og:url" content="{en_url(en)}">', s)
    s = re.sub(r'<meta property="og:title" content="[^"]*">',
               f'<meta property="og:title" content="{title}">', s)
    s = re.sub(r'<meta property="og:description" content="[^"]*">',
               f'<meta property="og:description" content="{desc}">', s)
    s = s.replace('<meta property="og:locale" content="fr_CA">',
                  '<meta property="og:locale" content="en_CA">')
    s = s.replace('<meta property="og:locale:alternate" content="en_CA">',
                  '<meta property="og:locale:alternate" content="fr_CA">')
    s = re.sub(r'<meta name="twitter:title" content="[^"]*">',
               f'<meta name="twitter:title" content="{title}">', s)
    s = re.sub(r'<meta name="twitter:description" content="[^"]*">',
               f'<meta name="twitter:description" content="{desc}">', s)

    # 6. title + description
    s = re.sub(r'<title>[^<]*</title>', f'<title>{title}</title>', s, count=1)
    s = re.sub(r'<meta name="description" content="[^"]*">',
               f'<meta name="description" content="{desc}">', s, count=1)

    # 7. the URL decides the language, not localStorage — otherwise an English
    #    URL could render French for a returning visitor, which contradicts
    #    the canonical and hreflang we just declared.
    #
    #    Both source forms are handled so the build is idempotent: the first
    #    run rewrites the original ternary, later runs rewrite the already
    #    patched applyLang('fr') that patch_french leaves behind. Without this,
    #    running the script twice silently produced English pages that
    #    rendered in French.
    s = re.sub(r"applyLang\((?:saved === 'en' \? 'en' : 'fr'|'fr')\);",
               "applyLang('en');", s)
    # The <title> inside applyLang is a lang ternary — it already resolves to
    # the English branch once lang is 'en', so it must not be touched here.

    # 8. FR button navigates back to the French page
    back = '../' if en == 'index.html' else '../' + fr
    s = s.replace('</body>', switcher_script(back, 'fr') + '</body>', 1)

    open(os.path.join(OUT, en), 'w', encoding='utf-8').write(s)
    return en


def patch_french(fr, en):
    """The French page keeps its content; only its language wiring changes."""
    s = open(fr, encoding='utf-8').read()

    s = re.sub(r'(<link rel="alternate" hreflang="[^"]*"[^>]*>\s*)+',
               hreflang_block(fr, en) + '\n', s, count=1)
    s = s.replace("applyLang(saved === 'en' ? 'en' : 'fr');", "applyLang('fr');")

    if 'Language is a URL, not a toggle' not in s:
        forward = 'en/' if en == 'index.html' else 'en/' + en
        s = s.replace('</body>', switcher_script(forward, 'en') + '</body>', 1)

    open(fr, 'w', encoding='utf-8').write(s)


if __name__ == '__main__':
    shutil.rmtree(OUT, ignore_errors=True)
    os.makedirs(OUT, exist_ok=True)
    for fr, en in PAGES.items():
        build_english(fr, en)
        patch_french(fr, en)
        print(f'  {fr:28s} ->  en/{en}')
    print(f'\n{len(PAGES)} English pages generated in {OUT}/')
