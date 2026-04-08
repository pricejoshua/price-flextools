# -*- coding: utf-8 -*-
#
# Export Lexeme Audio TSV
#
# Exports a TSV file with lexeme form, IPA transcription, and sound file name
# for each lexical entry that has pronunciation data.
#

import os
import unicodedata

from flextoolslib import *

docs = {
    FTM_Name: "Export Lexeme Audio TSV",
    FTM_Version: 1,
    FTM_ModifiesDB: False,
    FTM_Synopsis: "Exports a TSV with lexeme form, IPA transcription, and sound file name",
    FTM_Help: None,
    FTM_Description: """
Exports a tab-separated file containing:
  - Lexeme Form (default vernacular writing system)
  - IPA Transcription (from the pronunciation field)
  - Sound File Name (from pronunciation media files)

Each pronunciation for each entry produces one row. Entries with multiple
pronunciations will have multiple rows. Entries without any pronunciation
data are skipped.

The output file is saved to the user's Desktop as 'lexeme_audio_export.tsv'.
"""
}


def ExportLexemeAudioTSV(project, report, modifyAllowed=False):
    """Main function for the Export Lexeme Audio TSV tool."""

    rows = []

    for entry in project.LexiconAllEntries():
        lexeme = project.LexiconGetLexemeForm(entry) or ""
        if not lexeme:
            continue

        # Get pronunciations for this entry
        try:
            pronunciations = list(entry.PronunciationsOS)
        except (AttributeError, Exception):
            continue

        if not pronunciations:
            continue

        for pron in pronunciations:
            # Get IPA form
            ipa = ""
            try:
                ipa = project.Pronunciation.GetForm(pron) or ""
            except (AttributeError, Exception):
                # Fallback: try reading Form MultiString directly
                try:
                    form = pron.Form
                    if form:
                        wss = form.AvailableWritingSystemIds
                        for ws in wss:
                            text = form.get_String(ws)
                            if text and text.Text:
                                ipa = text.Text
                                break
                except (AttributeError, Exception):
                    pass

            # Get sound file names
            sound_files = []
            try:
                media_list = project.Pronunciation.GetMediaFiles(pron)
                for media_obj in media_list:
                    try:
                        # media_obj is ICmMedia; get the referenced ICmFile
                        cm_file = media_obj.MediaFileRA
                        if cm_file:
                            path = project.Media.GetInternalPath(cm_file)
                            if path:
                                sound_files.append(os.path.basename(path))
                    except (AttributeError, Exception):
                        pass
            except (AttributeError, Exception):
                # Fallback: try raw LCModel access
                try:
                    for media in pron.MediaFilesOS:
                        if media.MediaFileRA:
                            path = str(media.MediaFileRA.InternalPath)
                            if path:
                                sound_files.append(os.path.basename(path))
                except (AttributeError, Exception):
                    pass

            sound_file_str = "; ".join(sound_files) if sound_files else ""

            # Only include rows that have at least IPA or a sound file
            if ipa or sound_file_str:
                rows.append((lexeme, ipa, sound_file_str))

    if not rows:
        report.Warning("No entries with pronunciation data found.")
        return

    # Sort by lexeme form
    rows.sort(key=lambda r: unicodedata.normalize('NFD', r[0].lower()))

    # Write TSV to Desktop
    desktop = os.path.join(os.path.expanduser("~"), "Desktop")
    output_path = os.path.join(desktop, "lexeme_audio_export.tsv")

    with open(output_path, "w", encoding="utf-8") as f:
        f.write("Lexeme Form\tIPA\tSound File\n")
        for lexeme, ipa, sound_file in rows:
            # Escape any tabs in the data
            lexeme = lexeme.replace("\t", " ")
            ipa = ipa.replace("\t", " ")
            sound_file = sound_file.replace("\t", " ")
            f.write(f"{lexeme}\t{ipa}\t{sound_file}\n")

    report.Info(f"Exported {len(rows)} rows to: {output_path}")


FlexToolsModule = FlexToolsModuleClass(
    runFunction=ExportLexemeAudioTSV,
    docs=docs
)
