---
name: translate
description: Extract new translatable strings, translate them to es/de, and compile catalogs
user_invocable: true
---

# Translate EMR strings

Perform the full translation workflow for the EMR app:

1. Run `yarn extract` to extract new/updated translatable strings into `.po` files.

2. Read the `.po` files to see which strings have empty `msgstr`:
   - `src/locale/es/messages.po`
   - `src/locale/de/messages.po`

3. For each untranslated string (empty `msgstr ""`), fill in the correct translation:
   - **es**: Spanish (Latin American)
   - **de**: German

   Use the existing translations in the same file and in `contrib/fhir-emr/src/locale/{es,de}/messages.ts` as style reference to keep terminology consistent.

4. Run `yarn compile` to compile the updated catalogs into `messages.ts`.

5. Report what strings were added/translated.

**Important**: Do NOT modify `src/locale/en/messages.po` — English strings are the source and don't need `msgstr` values (Lingui uses the `msgid` as the English text).
