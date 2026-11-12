# Contributing

Found a word that won't look up? There are three ways to help.

## 1. Report a missing word

Open an [issue](../../issues) with:

- the word **exactly as spelled in the book** (including any accents or hyphens)
- which book it's from
- what it seems to mean in context

## 2. Add it yourself

Edit [`wh40k_custom_entries.txt`](wh40k_custom_entries.txt) and open a pull request. The format is:

```
Headword | other spellings, comma-separated | Definition.
```

Guidelines:

- **Write definitions in your own words.** Please don't paste text from books, rulebooks, the Lexicanum or other sites. Short and factual is best: one or two sentences.
- Start with a context tag where it helps, such as `(Fenrisian)`, `(Space Wolves)` or `(Aeldari)`.
- Put entries in the matching section, in alphabetical order.
- Avoid headwords that are ordinary English words (*for*, *under*, *verse*, *accounting*). While this dictionary is selected, they would replace the normal definition.
- No spoilers in definitions if you can avoid it.

By contributing, you agree that your additions are released under [CC BY-SA 3.0](LICENSE-CONTENT.md).

## 3. Fix the builder

Bug reports and pull requests for `wh40k_dict_builder.py` are welcome. Please test with `--limit 200` and keep the default request delay at 1 second or more.
