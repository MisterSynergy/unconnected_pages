# Unconnected pages by category
Wikidata bot that collects unconnected pages from Wikipedias within a certain category. The category needs to by identified by a Wikidata Q-ID so that all sitelinks to that category items are petscanned. Wikipedia pages without a connected Wikidata item are being reported to a page on Wikidata.

Currently, the only report produced can be found at [User:MisterSynergy/rowing/unconnected_pages](https://www.wikidata.org/wiki/User:MisterSynergy/rowing/unconnected_pages).

## Technical requirements
The bot is currently scheduled to run weekly on [Toolforge](https://wikitech.wikimedia.org/wiki/Portal:Toolforge) from within the `msynbot` tool account. It depends on the [shared pywikibot files](https://wikitech.wikimedia.org/wiki/Help:Toolforge/Pywikibot#Using_the_shared_Pywikibot_files_(recommended_setup)) and is running in a Kubernetes environment using Python 3.11.2.

In the background, the bot makes requests to the [Petscan](https://petscan.wmflabs.org/) tool by @MagnusManske.