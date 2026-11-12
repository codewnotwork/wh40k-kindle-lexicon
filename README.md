# Unofficial Warhammer 40k Kindle Lexicon

A pop-up dictionary for Kindle e-readers that covers the Warhammer 40,000 universe. Long-press a word like *Inquisitor*, *Runejarl*, *Astartes* or *wyrdstorm* while reading, and get a short definition in place of the English dictionary entry.

> **Unofficial fan project.** Not affiliated with or endorsed by Games Workshop. Warhammer 40,000 and all associated names and marks are trademarks of Games Workshop Limited.

## What's in it

- **About 7,300 entries** from the [Warhammer 40k Wiki](https://warhammer40k.fandom.com), each shortened to the opening of its article and linked to the full page.
- **Alternate names and spellings** from the wiki's redirects. Distinctive parts of character names work too, so *Calgar* finds *Marneus Calgar*.
- **Plurals and possessives**, such as *Runejarls* and *Calgar's*.
- **Numbered meanings** where several articles share a name, for example *Angron* the primarch and *Angron* the novel.
- **Custom entries** for terms the wiki doesn't cover, starting with about 165 Fenrisian (Space Wolves) words.

## Install the ready-made dictionary

1. Download the latest `WH40K_Lexicon_vX.X.mobi` from the [Releases](../../releases) page.
2. Plug your Kindle into your computer. Open its drive, then `documents`, then `dictionaries` (create the `dictionaries` folder if it isn't there).
3. Copy the `.mobi` file in, then eject the Kindle.
4. In any book, long-press a word. In the pop-up, tap the dictionary name and choose **Warhammer 40k Lexicon (unofficial)**. Switch back to your regular dictionary the same way.

Tested on a recent Kindle e-reader. Kindle e-readers only; the Kindle phone and tablet apps don't support sideloaded dictionaries.

## Build it yourself

You only need this to change entries or pull fresh text from the wiki.

**You need:**
- Python 3.8 or newer ([python.org](https://www.python.org)). No extra packages.
- **kindlegen 2.9**, Amazon's retired tool that builds Kindle dictionary files. It's bundled inside older **Kindle Previewer 3** installs at `lib\fc\bin\kindlegen.exe`, and copies of the standalone kindlegen 2.9 are on archive.org. *Kindle Previewer 4 does not include it.*

**Run:**

```
python wh40k_dict_builder.py --kindlegen "C:\path\to\kindlegen.exe"
```

The first run downloads the wiki at a polite pace (one request per second), which takes about 15–30 minutes. It saves its progress, so you can stop and resume. The finished file appears in `wh40k_dictionary_output/`.

| Option | What it does |
|---|---|
| `--build-only` | Rebuild from what's already downloaded, with no network access. Use this after editing custom entries. |
| `--limit 200` | Quick test with 200 articles. |
| `--kindlegen PATH` | Where kindlegen is, if it isn't found automatically. |
| `--custom PATH` | Use a different custom entries file. |
| `--delay 1.0` | Seconds between wiki requests. Please keep it at 1 or more. |

Please use the ready-made release unless you actually need a fresh build. Every full build downloads the whole wiki again.

## Adding words

Missing terms go in [`wh40k_custom_entries.txt`](wh40k_custom_entries.txt), one per line:

```
Headword | other spellings, comma-separated | Definition.
Runejarl | runejarls, Rune Jarl | (Fenrisian) A Rune Priest: a Space Wolves Librarian (psyker).
Hja | | (Fenrisian) Yes.
```

- If a headword matches a wiki article, your text is added as an extra meaning under it.
- Plural and possessive forms are added automatically.
- Avoid headwords that are ordinary English words (*for*, *under*, *verse*). They would replace the normal definition while this dictionary is selected.

See [CONTRIBUTING.md](CONTRIBUTING.md) to suggest words for the shared list.

## Licences

- **Builder script:** [MIT](LICENSE).
- **Dictionary content** (the built `.mobi` and `wh40k_custom_entries.txt`): [CC BY-SA 3.0](LICENSE-CONTENT.md). Wiki text is © Warhammer 40k Wiki (Fandom) contributors. Custom entries are © the project contributors.
- Games Workshop's trademarks are not covered by either licence.

## Credits

- The [Warhammer 40k Wiki](https://warhammer40k.fandom.com) contributors, for the bulk of the entries.
- The [Lexicanum](https://wh40k.lexicanum.com/wiki/Fenris_Vulgaris) *Fenris Vulgaris* page, for help compiling the Fenrisian word list (which draws on the lexicon appendix of the novel *The Wolftime*).
