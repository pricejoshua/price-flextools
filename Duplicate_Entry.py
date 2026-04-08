# -*- coding: utf-8 -*-
#
# Duplicate Entry FlexTool
#
# Duplicates an existing lexical entry with all its data (senses, glosses,
# examples, etc.) with the option to modify the lexeme form.
#

import unicodedata

from flextoolslib import *
from SIL.LCModel import *
from SIL.LCModel.Core.KernelInterfaces import ITsString
from SIL.LCModel.Core.Text import TsStringUtils

# Maximum entries to show in dropdown (to prevent UI freezing)
MAX_DISPLAY_ENTRIES = 200

docs = {
    FTM_Name: "Duplicate Entry",
    FTM_Version: 2,
    FTM_ModifiesDB: True,
    FTM_Synopsis: "Duplicates a lexical entry with all its data",
    FTM_Help: None,
    FTM_Description: """
This tool duplicates an existing lexical entry:

1. Prompts for a search term (beginning of lexeme form)
   - Leave empty to see all entries (first 200)
   - Type text to filter entries starting with that text
2. Shows matching entries with headword, gloss, and part of speech
3. Optionally allows you to edit the lexeme form for the duplicate
4. Creates an exact duplicate with all senses, glosses, definitions,
   examples, translations, semantic domains, etc.

Use this when you need to create a new entry that is similar to an
existing one, such as for dialectal variants or related forms.
"""
}


def get_entry_display_string(project, entry):
    """Create a user-friendly display string for an entry: 'lexeme (gloss) [POS]'"""
    # Get lexeme/headword
    try:
        headword = str(entry.HeadWord) if entry.HeadWord else ""
    except (AttributeError, Exception):
        headword = ""
    if not headword:
        headword = project.LexiconGetLexemeForm(entry) or "(no form)"

    # Get first gloss
    gloss = ""
    pos = ""
    try:
        if entry.SensesOS and entry.SensesOS.Count > 0:
            first_sense = entry.SensesOS[0]
            gloss = project.LexiconGetSenseGloss(first_sense) or ""
            pos = project.LexiconGetSensePOS(first_sense) or ""
    except (AttributeError, Exception):
        pass  # No senses available

    # Build display string
    display = headword
    if gloss:
        display += f" ({gloss})"
    if pos:
        display += f" [{pos}]"

    return display


def find_entries_by_prefix(project, prefix):
    """Find all entries whose lexeme form starts with the given prefix."""
    matches = []
    # Normalize prefix to NFD to match FLEx's internal normalization
    prefix_lower = unicodedata.normalize('NFD', prefix.lower()) if prefix else ""

    for entry in project.LexiconAllEntries():
        lexeme = project.LexiconGetLexemeForm(entry)
        # If no prefix given, include all entries
        # If prefix given, only include entries starting with prefix
        if not prefix_lower or (lexeme and
                unicodedata.normalize('NFD', lexeme.lower()).startswith(prefix_lower)):
            display = get_entry_display_string(project, entry)
            matches.append((lexeme or "", display, entry))

    # Sort by lexeme form
    matches.sort(key=lambda x: unicodedata.normalize('NFD', x[0].lower()) if x[0] else "")

    return matches


def copy_multistring(source_ms, dest_ms):
    """Copy all writing system alternatives from source to destination MultiString/MultiUnicode."""
    if source_ms is None:
        return

    try:
        wss = source_ms.AvailableWritingSystemIds
        for ws in wss:
            text = source_ms.get_String(ws)
            if text and text.Text:
                dest_ms.set_String(ws, text)
    except (AttributeError, Exception):
        pass  # Property not available


def safe_copy_reference_collection(source_obj, dest_obj, attr_name):
    """Safely copy items from a reference collection that may not exist."""
    try:
        source_coll = getattr(source_obj, attr_name, None)
        if source_coll is None:
            return
        dest_coll = getattr(dest_obj, attr_name, None)
        if dest_coll is None:
            return
        for item in source_coll:
            dest_coll.Add(item)
    except (AttributeError, Exception):
        pass  # Collection not available in this project


def safe_copy_reference_atom(source_obj, dest_obj, attr_name):
    """Safely copy a reference atom property that may not exist."""
    try:
        source_val = getattr(source_obj, attr_name, None)
        if source_val:
            setattr(dest_obj, attr_name, source_val)
    except (AttributeError, Exception):
        pass  # Property not available


def duplicate_example_sentence(project, source_example, dest_sense):
    """Duplicate a LexExampleSentence with its translations."""
    sl = project.project.ServiceLocator

    # Create new example
    new_example = sl.GetService(ILexExampleSentenceFactory).Create()
    dest_sense.ExamplesOS.Add(new_example)

    # Copy Example field (MultiString)
    copy_multistring(source_example.Example, new_example.Example)

    # Copy Reference
    try:
        if source_example.Reference and source_example.Reference.Text:
            new_example.Reference = source_example.Reference
    except (AttributeError, Exception):
        pass

    # Copy Translations
    try:
        for trans in source_example.TranslationsOC:
            try:
                if trans.TypeRA:
                    new_trans = sl.GetService(ICmTranslationFactory).Create(new_example, trans.TypeRA)
                    copy_multistring(trans.Translation, new_trans.Translation)
            except (AttributeError, Exception):
                pass  # Translation type not available
    except (AttributeError, Exception):
        pass  # Translations not available


def duplicate_sense(project, source_sense, dest_entry, msa_map):
    """Duplicate a LexSense with all its data."""
    sl = project.project.ServiceLocator

    # Create new sense
    new_sense = sl.GetService(ILexSenseFactory).Create()
    dest_entry.SensesOS.Add(new_sense)

    # Copy Gloss (MultiUnicode)
    copy_multistring(source_sense.Gloss, new_sense.Gloss)

    # Copy Definition (MultiString)
    copy_multistring(source_sense.Definition, new_sense.Definition)

    # Copy MorphoSyntaxAnalysis reference
    try:
        if source_sense.MorphoSyntaxAnalysisRA:
            source_msa = source_sense.MorphoSyntaxAnalysisRA
            if source_msa.Hvo in msa_map:
                new_sense.MorphoSyntaxAnalysisRA = msa_map[source_msa.Hvo]
    except (AttributeError, Exception):
        pass  # MSA not available

    # Copy Semantic Domains
    safe_copy_reference_collection(source_sense, new_sense, 'SemanticDomainsRC')

    # Copy Reversal Entries (may not exist if no reversal indexes configured)
    safe_copy_reference_collection(source_sense, new_sense, 'ReversalEntriesRC')

    # Copy Anthropology Note
    copy_multistring(source_sense.AnthroNote, new_sense.AnthroNote)

    # Copy Bibliography
    copy_multistring(source_sense.Bibliography, new_sense.Bibliography)

    # Copy Discourse Note
    copy_multistring(source_sense.DiscourseNote, new_sense.DiscourseNote)

    # Copy Encyclopedia
    copy_multistring(source_sense.EncyclopedicInfo, new_sense.EncyclopedicInfo)

    # Copy General Note
    copy_multistring(source_sense.GeneralNote, new_sense.GeneralNote)

    # Copy Grammar Note
    copy_multistring(source_sense.GrammarNote, new_sense.GrammarNote)

    # Copy Phonology Note
    copy_multistring(source_sense.PhonologyNote, new_sense.PhonologyNote)

    # Copy Restrictions
    copy_multistring(source_sense.Restrictions, new_sense.Restrictions)

    # Copy Scientific Name
    try:
        if source_sense.ScientificName and source_sense.ScientificName.Text:
            new_sense.ScientificName = source_sense.ScientificName
    except (AttributeError, Exception):
        pass

    # Copy Semantic Domain strings
    copy_multistring(source_sense.SemanticsNote, new_sense.SemanticsNote)

    # Copy Sociolinguistics Note
    copy_multistring(source_sense.SocioLinguisticsNote, new_sense.SocioLinguisticsNote)

    # Copy Source
    try:
        if source_sense.Source and source_sense.Source.Text:
            new_sense.Source = source_sense.Source
    except (AttributeError, Exception):
        pass

    # Copy Usage Types
    safe_copy_reference_collection(source_sense, new_sense, 'UsageTypesRC')

    # Copy Domain Types
    safe_copy_reference_collection(source_sense, new_sense, 'DomainTypesRC')

    # Copy Sense Type
    safe_copy_reference_atom(source_sense, new_sense, 'SenseTypeRA')

    # Copy Status
    safe_copy_reference_atom(source_sense, new_sense, 'StatusRA')

    # Copy Example Sentences
    try:
        for example in source_sense.ExamplesOS:
            duplicate_example_sentence(project, example, new_sense)
    except (AttributeError, Exception):
        pass  # Examples not available

    # Copy Pictures
    try:
        for pic in source_sense.PicturesOS:
            new_pic = sl.GetService(ICmPictureFactory).Create()
            new_sense.PicturesOS.Add(new_pic)
            safe_copy_reference_atom(pic, new_pic, 'PictureFileRA')
            copy_multistring(pic.Caption, new_pic.Caption)
            copy_multistring(pic.Description, new_pic.Description)
    except (AttributeError, Exception):
        pass  # Pictures not available

    # Recursively copy subsenses
    try:
        for subsense in source_sense.SensesOS:
            duplicate_sense(project, subsense, new_sense, msa_map)
    except (AttributeError, Exception):
        pass  # Subsenses not available

    return new_sense


def duplicate_msa(project, source_msa, dest_entry):
    """Duplicate a MorphoSyntaxAnalysis object."""
    sl = project.project.ServiceLocator

    try:
        class_name = source_msa.ClassName
    except (AttributeError, Exception):
        class_name = ""

    if class_name == "MoStemMsa":
        source_msa = IMoStemMsa(source_msa)
        new_msa = sl.GetService(IMoStemMsaFactory).Create()
        dest_entry.MorphoSyntaxAnalysesOC.Add(new_msa)
        safe_copy_reference_atom(source_msa, new_msa, 'PartOfSpeechRA')
        # Copy inflection class if present
        safe_copy_reference_atom(source_msa, new_msa, 'InflectionClassRA')
        # Copy Stratum
        safe_copy_reference_atom(source_msa, new_msa, 'StratumRA')
        # Copy prodRestrict
        safe_copy_reference_collection(source_msa, new_msa, 'ProdRestrictRC')

    elif class_name == "MoUnclassifiedAffixMsa":
        source_msa = IMoUnclassifiedAffixMsa(source_msa)
        new_msa = sl.GetService(IMoUnclassifiedAffixMsaFactory).Create()
        dest_entry.MorphoSyntaxAnalysesOC.Add(new_msa)
        safe_copy_reference_atom(source_msa, new_msa, 'PartOfSpeechRA')

    elif class_name == "MoDerivAffMsa":
        source_msa = IMoDerivAffMsa(source_msa)
        new_msa = sl.GetService(IMoDerivAffMsaFactory).Create()
        dest_entry.MorphoSyntaxAnalysesOC.Add(new_msa)
        safe_copy_reference_atom(source_msa, new_msa, 'FromPartOfSpeechRA')
        safe_copy_reference_atom(source_msa, new_msa, 'ToPartOfSpeechRA')

    elif class_name == "MoInflAffMsa":
        source_msa = IMoInflAffMsa(source_msa)
        new_msa = sl.GetService(IMoInflAffMsaFactory).Create()
        dest_entry.MorphoSyntaxAnalysesOC.Add(new_msa)
        safe_copy_reference_atom(source_msa, new_msa, 'PartOfSpeechRA')

    else:
        # Generic fallback - create stem MSA
        new_msa = sl.GetService(IMoStemMsaFactory).Create()
        dest_entry.MorphoSyntaxAnalysesOC.Add(new_msa)

    return new_msa


def duplicate_allomorph(project, source_allo, dest_entry, is_lexeme_form=False, new_form=None):
    """Duplicate an allomorph (MoForm)."""
    sl = project.project.ServiceLocator

    try:
        class_name = source_allo.ClassName
    except (AttributeError, Exception):
        class_name = ""

    if class_name == "MoStemAllomorph":
        source_allo = IMoStemAllomorph(source_allo)
        new_allo = sl.GetService(IMoStemAllomorphFactory).Create()
    elif class_name == "MoAffixAllomorph":
        source_allo = IMoAffixAllomorph(source_allo)
        new_allo = sl.GetService(IMoAffixAllomorphFactory).Create()
    elif class_name == "MoAffixProcess":
        source_allo = IMoAffixProcess(source_allo)
        new_allo = sl.GetService(IMoAffixProcessFactory).Create()
    else:
        # Default to stem allomorph
        new_allo = sl.GetService(IMoStemAllomorphFactory).Create()

    # Add to entry first
    if is_lexeme_form:
        dest_entry.LexemeFormOA = new_allo
    else:
        dest_entry.AlternateFormsOS.Add(new_allo)

    # Copy Form - use new_form if provided (for lexeme form), otherwise copy original
    if new_form is not None and is_lexeme_form:
        # Get the default vernacular writing system
        wsv = project.project.DefaultVernWs
        new_allo.Form.set_String(wsv, new_form)
        # Also copy other writing system alternatives from source
        try:
            wss = source_allo.Form.AvailableWritingSystemIds
            for ws in wss:
                if ws != wsv:  # Skip the default one we already set
                    text = source_allo.Form.get_String(ws)
                    if text and text.Text:
                        new_allo.Form.set_String(ws, text)
        except (AttributeError, Exception):
            pass  # Could not copy other writing systems
    else:
        copy_multistring(source_allo.Form, new_allo.Form)

    # Copy MorphType
    safe_copy_reference_atom(source_allo, new_allo, 'MorphTypeRA')

    # Copy IsAbstract
    try:
        new_allo.IsAbstract = source_allo.IsAbstract
    except (AttributeError, Exception):
        pass

    return new_allo


def duplicate_entry(project, source_entry, new_lexeme_form=None):
    """Create a complete duplicate of a lexical entry."""
    sl = project.project.ServiceLocator

    # Create new entry
    new_entry = sl.GetService(ILexEntryFactory).Create()

    # Copy LexemeForm
    try:
        if source_entry.LexemeFormOA:
            duplicate_allomorph(project, source_entry.LexemeFormOA, new_entry,
                              is_lexeme_form=True, new_form=new_lexeme_form)
    except (AttributeError, Exception):
        pass  # LexemeForm not available

    # Copy CitationForm (MultiUnicode)
    copy_multistring(source_entry.CitationForm, new_entry.CitationForm)

    # Copy Alternate Forms
    try:
        for allo in source_entry.AlternateFormsOS:
            duplicate_allomorph(project, allo, new_entry, is_lexeme_form=False)
    except (AttributeError, Exception):
        pass  # Alternate forms not available

    # Copy MorphoSyntaxAnalyses and build mapping
    msa_map = {}  # source HVO -> new MSA object
    try:
        for msa in source_entry.MorphoSyntaxAnalysesOC:
            new_msa = duplicate_msa(project, msa, new_entry)
            msa_map[msa.Hvo] = new_msa
    except (AttributeError, Exception):
        pass  # MSAs not available

    # Copy Senses (with MSA mapping)
    try:
        for sense in source_entry.SensesOS:
            duplicate_sense(project, sense, new_entry, msa_map)
    except (AttributeError, Exception):
        pass  # Senses not available

    # Copy Etymology
    try:
        for etym in source_entry.EtymologyOS:
            new_etym = sl.GetService(ILexEtymologyFactory).Create()
            new_entry.EtymologyOS.Add(new_etym)
            copy_multistring(etym.Form, new_etym.Form)
            copy_multistring(etym.Gloss, new_etym.Gloss)
            copy_multistring(etym.Comment, new_etym.Comment)
            copy_multistring(etym.Bibliography, new_etym.Bibliography)
            try:
                if etym.Source and etym.Source.Text:
                    new_etym.Source = etym.Source
            except (AttributeError, Exception):
                pass
            safe_copy_reference_collection(etym, new_etym, 'LanguageRS')
    except (AttributeError, Exception):
        pass  # Etymology not available

    # Copy Pronunciations
    try:
        for pron in source_entry.PronunciationsOS:
            new_pron = sl.GetService(ILexPronunciationFactory).Create()
            new_entry.PronunciationsOS.Add(new_pron)
            copy_multistring(pron.Form, new_pron.Form)
            copy_multistring(pron.CVPattern, new_pron.CVPattern)
            copy_multistring(pron.Tone, new_pron.Tone)
            safe_copy_reference_collection(pron, new_pron, 'LocationRS')
            # Copy media files references
            try:
                for media in pron.MediaFilesOS:
                    new_media = sl.GetService(ICmMediaFactory).Create()
                    new_pron.MediaFilesOS.Add(new_media)
                    safe_copy_reference_atom(media, new_media, 'MediaFileRA')
                    copy_multistring(media.Label, new_media.Label)
            except (AttributeError, Exception):
                pass  # Media files not available
    except (AttributeError, Exception):
        pass  # Pronunciations not available

    # Copy Comment
    copy_multistring(source_entry.Comment, new_entry.Comment)

    # Copy LiteralMeaning
    copy_multistring(source_entry.LiteralMeaning, new_entry.LiteralMeaning)

    # Copy Bibliography
    copy_multistring(source_entry.Bibliography, new_entry.Bibliography)

    # Copy Restrictions
    copy_multistring(source_entry.Restrictions, new_entry.Restrictions)

    # Copy SummaryDefinition
    copy_multistring(source_entry.SummaryDefinition, new_entry.SummaryDefinition)

    # Copy DoNotUseForParsing flag
    try:
        new_entry.DoNotUseForParsing = source_entry.DoNotUseForParsing
    except (AttributeError, Exception):
        pass

    # Copy Dialect Labels
    safe_copy_reference_collection(source_entry, new_entry, 'DialectLabelsRS')

    # Copy DoNotPublishIn
    safe_copy_reference_collection(source_entry, new_entry, 'DoNotPublishInRC')

    # Copy PublishIn
    safe_copy_reference_collection(source_entry, new_entry, 'PublishInRC')

    return new_entry


def DuplicateEntry(project, report, modifyAllowed=False):
    """Main function for the Duplicate Entry tool."""

    # Step 1: Get search prefix from user
    search_prefix = FTDialogText(
        "Enter the beginning of the lexeme to find (leave empty to see all entries):",
        ""
    )

    if search_prefix is None:
        report.Info("Operation cancelled.")
        return

    # Step 2: Find matching entries
    matches = find_entries_by_prefix(project, search_prefix)

    if not matches:
        if search_prefix:
            report.Warning(f"No entries found starting with '{search_prefix}'")
        else:
            report.Warning("No entries found in the lexicon.")
        return

    # Limit display if too many matches
    total_matches = len(matches)
    if total_matches > MAX_DISPLAY_ENTRIES:
        matches = matches[:MAX_DISPLAY_ENTRIES]
        report.Info(f"Showing first {MAX_DISPLAY_ENTRIES} of {total_matches} entries. "
                   "Enter more specific text to narrow results.")

    # Step 3: Let user select an entry
    # Use the user-friendly display strings for selection
    display_names = [display for lexeme, display, entry in matches]

    if len(matches) == 1:
        selected_display = display_names[0]
        report.Info(f"Found one match: {selected_display}")
    else:
        selected_display = FTDialogChoose(
            f"Select an entry to duplicate ({len(matches)} shown):",
            display_names
        )

    if not selected_display:
        report.Info("No entry selected. Operation cancelled.")
        return

    # Find the selected entry by matching the display string
    selected_entry = None
    original_lexeme = None
    for lexeme, display, entry in matches:
        if display == selected_display:
            selected_entry = entry
            original_lexeme = lexeme
            report.Info(f"Selected entry: {selected_entry}")
            break

    if not selected_entry:
        report.Error("Could not find the selected entry.")
        return

    # Step 4: Ask for new lexeme form
    # Use the lexeme from the match, or get it fresh if not set
    if not original_lexeme:
        original_lexeme = project.LexiconGetLexemeForm(selected_entry)
        report.Info(f"Retrieved lexeme form: {original_lexeme}")
    new_lexeme = FTDialogText(
        "Enter the lexeme form for the duplicate (or keep the same):",
        original_lexeme if original_lexeme else ""
    )

    if new_lexeme is None:
        report.Info("Operation cancelled.")
        return

    # Use original if user cleared the field
    if not new_lexeme:
        new_lexeme = original_lexeme

    # Step 5: Check if we can modify
    if not modifyAllowed:
        report.Warning(f"Would duplicate entry '{original_lexeme}' as '{new_lexeme}'")
        report.Info("Run with 'Modify' enabled to create the duplicate.")
        return

    # Step 6: Create the duplicate
    try:
        new_entry = duplicate_entry(project, selected_entry, new_lexeme)

        try:
            new_headword = str(new_entry.HeadWord) if new_entry.HeadWord else new_lexeme
        except (AttributeError, Exception):
            new_headword = new_lexeme

        report.Info(f"Successfully duplicated '{original_lexeme}' as '{new_headword}'",
                   project.BuildGotoURL(new_entry))

        # Report what was copied
        try:
            sense_count = len(list(selected_entry.SensesOS))
            report.Info(f"  - Copied {sense_count} sense(s)")
        except (AttributeError, Exception):
            pass  # Could not count senses

    except Exception as e:
        report.Error(f"Error creating duplicate: {str(e)}")


FlexToolsModule = FlexToolsModuleClass(
    runFunction=DuplicateEntry,
    docs=docs
)
