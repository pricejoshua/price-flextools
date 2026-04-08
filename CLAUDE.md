# price-flextools

Custom FlexTools modules for SIL FieldWorks Language Explorer (FLEx).

## What this is

FlexTools is a plugin framework for FLEx that lets you write Python modules to automate lexicography tasks. Each `.py` file in this repo is a standalone FlexTools module.

## Module structure

Every module follows this pattern:

```python
from flextoolslib import *
from SIL.LCModel import *

docs = {
    FTM_Name: "Tool Name",
    FTM_Version: 1,
    FTM_ModifiesDB: True/False,
    FTM_Synopsis: "One-line description",
    FTM_Help: None,
    FTM_Description: """..."""
}

def MainFunction(project, report, modifyAllowed=False):
    ...

FlexToolsModule = FlexToolsModuleClass(runFunction=MainFunction, docs=docs)
```

- `modifyAllowed=False` means FlexTools is running in read-only/preview mode — do not write to the DB.
- Use `report.Info(...)`, `report.Warning(...)`, `report.Error(...)` for output.
- Access the lexicon via `project.LexiconAllEntries()`, `project.LexiconGetLexemeForm(entry)`, etc.

## Current modules

| File | Purpose |
|------|---------|
| `Duplicate_Entry.py` | Duplicate a lexical entry with all its data (senses, glosses, examples, etc.) |
| `Export_Lexeme_Audio_TSV.py` | Export TSV of lexeme form, IPA transcription, and sound file name |
| `Fix_Duplicate_CFields.py` | Detect and merge duplicate custom fields (e.g. `TC`/`TC1`), then delete duplicates |
| `Merge_Analyses.py` | Merge duplicate wordform analyses by repointing occurrences to a chosen survivor |
| `FT_Custom_Dialogs.py` | Shared helper — reusable WinForms dialogs (not a FlexTools module itself) |

## Deployment

FlexTools loads modules from a `Modules/` directory next to `flextools.ini`. This repo should be placed as a named subdirectory (a "library") inside it:

```
Modules/
  PriceTools/        ← clone this repo here
    Duplicate_Entry.py
    Merge_Analyses.py
    FT_Custom_Dialogs.py
    ...
```

Modules will appear in the FlexTools UI as `PriceTools.Duplicate Entry`, etc.

Modules that import `FT_Custom_Dialogs` add their own directory to `sys.path` at the top of the file, so no extra setup is needed.

## Test data

`testdata/` contains a sample FLEx project (`Farsi_Justice.fwdata`) for local testing.

## Reference docs

`outside-docs/` contains PDF references copied from the upstream flextools repo:
- `FLExTools Programming.pdf`
- `Python for FlexTools and FLEx 9.1.pdf`

These are the primary API references — check them when working with unfamiliar LCModel APIs.

## Notes

- Writing systems: use `"en"` for default analysis WS, or `wsSelector="-1"` for the project default.
- Unicode normalization: FLEx stores strings in NFD internally — normalize inputs with `unicodedata.normalize('NFD', ...)` before comparing.
- The `SIL.LCModel` namespace is provided by FLEx's .NET runtime via IronPython; standard Python type hints don't apply to LCModel objects.
