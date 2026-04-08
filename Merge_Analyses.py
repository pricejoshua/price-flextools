# -*- coding: utf-8 -*-
#
# Merge Analyses FlexTool
#
# Scans all wordforms with multiple analyses, lets the user choose a
# survivor analysis to keep, then repoints all text occurrences of the
# other analyses to the survivor and deletes the duplicates.
#

import sys
import os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from flextoolslib import *

from SIL.LCModel import IWfiWordformRepository, ISegmentRepository
from SIL.LCModel.Core.KernelInterfaces import ITsString

from FT_Custom_Dialogs import FTChooseFromList

docs = {
    FTM_Name: "Merge Analyses",
    FTM_Version: 1,
    FTM_ModifiesDB: True,
    FTM_Synopsis: "Merge duplicate wordform analyses by repointing text occurrences to a chosen survivor",
    FTM_Help: None,
    FTM_Description: """
Scans all wordforms in the Wordform Inventory for entries that have more than
one analysis. For each such wordform:

1. Shows a list of wordforms with multiple analyses (with occurrence counts).
2. Lets you select a wordform to work on.
3. Shows all analyses for that wordform (glosses + morpheme breakdown).
4. Lets you choose which analysis to KEEP (the survivor).
5. Repoints every text occurrence that currently uses one of the other analyses
   to the survivor instead.
6. Deletes the now-unused analyses.

You can skip any wordform at any step. Run in read-only mode first to see a
dry-run report of what would change without modifying the database.
"""
}

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def get_best_vern_text(multistring):
    """Get the best vernacular text from a MultiString."""
    try:
        return ITsString(multistring.BestVernacularAlternative).Text or ""
    except Exception:
        return ""


def get_best_anal_text(multistring):
    """Get the best analysis text from a MultiString."""
    try:
        return ITsString(multistring.BestAnalysisAlternative).Text or ""
    except Exception:
        return ""


def describe_analysis(analysis):
    """
    Build a human-readable description of a WfiAnalysis.
    Format: 'Glosses: X, Y  |  Morphemes: a + b'
    """
    parts = []

    # --- Glosses ---
    try:
        gloss_strings = []
        for g in analysis.GlossesOS:
            form = get_best_anal_text(g.Form)
            if form:
                gloss_strings.append(form)
        parts.append("Glosses: " + (", ".join(gloss_strings) if gloss_strings else "(none)"))
    except Exception:
        parts.append("Glosses: (error)")

    # --- Morpheme bundles ---
    try:
        morph_strings = []
        for b in analysis.MorphBundlesOS:
            try:
                morph = b.MorphRA
                form = get_best_vern_text(morph.Form) if morph else ""
                morph_strings.append(form if form else "?")
            except Exception:
                morph_strings.append("?")
        parts.append("Morphemes: " + (" + ".join(morph_strings) if morph_strings else "(none)"))
    except Exception:
        parts.append("Morphemes: (error)")

    return "  |  ".join(parts)


def get_analysis_hvo(ann):
    """
    Return the IWfiAnalysis HVO for a text-annotation slot.
    Slots can hold IWfiGloss (.Analysis points to parent IWfiAnalysis)
    or IWfiAnalysis directly (no .Analysis attribute).
    """
    try:
        return ann.Analysis.Hvo   # IWfiGloss
    except AttributeError:
        return ann.Hvo            # IWfiAnalysis itself


def count_occurrences(project, target_hvo):
    """Count word-token slots across all texts that point to target_hvo."""
    count = 0
    for seg in project.ObjectsIn(ISegmentRepository):
        try:
            for ann in seg.AnalysesRS:
                try:
                    if get_analysis_hvo(ann) == target_hvo:
                        count += 1
                except Exception:
                    pass
        except Exception:
            pass
    return count


def repoint_occurrences(project, from_hvo, to_analysis):
    """
    Walk every segment.  Replace each word-token whose Analysis.Hvo == from_hvo
    with to_analysis.  Returns count of tokens repointed.
    """
    repointed = 0
    for seg in project.ObjectsIn(ISegmentRepository):
        try:
            rs = seg.AnalysesRS
            # Iterate in reverse so index shifts don't affect us
            for i in range(rs.Count - 1, -1, -1):
                try:
                    ann = rs[i]
                    if get_analysis_hvo(ann) == from_hvo:
                        rs.RemoveAt(i)
                        rs.Insert(i, to_analysis)
                        repointed += 1
                except Exception:
                    pass
        except Exception:
            pass
    return repointed


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def MergeAnalyses(project, report, modifyAllowed=False):

    # ------------------------------------------------------------------
    # Step 1: Collect all wordforms that have >1 analysis
    # ------------------------------------------------------------------
    report.Info("Scanning wordforms for multiple analyses...")

    multi_wf = []   # list of (form_str, wf_obj, analyses_list)

    for wf in project.ObjectsIn(IWfiWordformRepository):
        try:
            analyses = list(wf.AnalysesOC)
        except Exception:
            continue
        if len(analyses) < 2:
            continue
        form = get_best_vern_text(wf.Form) or "(no form)"
        multi_wf.append((form, wf, analyses))

    if not multi_wf:
        report.Info("No wordforms with multiple analyses found.")
        return

    multi_wf.sort(key=lambda x: x[0].lower())
    report.Info("Found {0} wordform(s) with multiple analyses.".format(len(multi_wf)))

    # ------------------------------------------------------------------
    # Step 2 -> loop: pick wordform, pick survivor, repoint + delete
    # ------------------------------------------------------------------
    while multi_wf:

        wf_choices = [
            "{0}  ({1} analyses)".format(form, len(analyses))
            for form, wf, analyses in multi_wf
        ]
        wf_choices.append("-- Done --")

        chosen_wf = FTChooseFromList(
            "Wordforms with multiple analyses  ({0} remaining).\n"
            "Select one to merge, or '-- Done --' to exit:".format(len(multi_wf)),
            wf_choices,
            width=500, height=350,
        )

        if not chosen_wf or chosen_wf == "-- Done --":
            report.Info("Finished.")
            return

        chosen_idx = next(
            (i for i, c in enumerate(wf_choices) if c == chosen_wf), None)
        if chosen_idx is None or chosen_idx >= len(multi_wf):
            report.Info("Nothing selected.")
            return

        form, wf, analyses = multi_wf[chosen_idx]

        # --------------------------------------------------------------
        # Step 3: Show analyses, let user pick survivor
        # --------------------------------------------------------------
        ana_choices = []
        for idx, ana in enumerate(analyses):
            desc = describe_analysis(ana)
            occ = count_occurrences(project, ana.Hvo)
            ana_choices.append("[{0}] {1}  ({2} occurrence{3})".format(
                idx + 1, desc, occ, "s" if occ != 1 else ""))
        ana_choices.append("-- Skip this wordform --")

        chosen_ana = FTChooseFromList(
            "Analyses for '{0}'.\n"
            "Select the analysis to KEEP "
            "(all others will be repointed to it, then deleted):".format(form),
            ana_choices,
            width=700, height=350, monospace=True,
        )

        if not chosen_ana or chosen_ana == "-- Skip this wordform --":
            report.Info("Skipped '{0}'.".format(form))
            continue

        survivor_idx = next(
            (i for i, c in enumerate(ana_choices) if c == chosen_ana), None)
        if survivor_idx is None or survivor_idx >= len(analyses):
            report.Info("Skipped '{0}'.".format(form))
            continue

        survivor = analyses[survivor_idx]
        losers = [a for i, a in enumerate(analyses) if i != survivor_idx]

        report.Info("'{0}': keeping analysis [{1}].".format(form, survivor_idx + 1))

        # --------------------------------------------------------------
        # Step 4: Repoint occurrences + delete loser analyses
        # --------------------------------------------------------------
        total_repointed = 0

        for loser in losers:
            display_idx = analyses.index(loser) + 1
            loser_hvo = loser.Hvo

            if modifyAllowed:
                n = repoint_occurrences(project, loser_hvo, survivor)
                total_repointed += n
                report.Info("  Analysis [{0}]: {1} occurrence{2} repointed.".format(
                    display_idx, n, "s" if n != 1 else ""))
                try:
                    wf.AnalysesOC.Remove(loser)
                    report.Info("  Analysis [{0}] deleted.".format(display_idx))
                except Exception as e:
                    report.Error("  Could not delete analysis [{0}]: {1}".format(
                        display_idx, str(e)))
            else:
                n = count_occurrences(project, loser_hvo)
                total_repointed += n
                report.Info("  [DRY RUN] Analysis [{0}]: {1} occurrence{2} would be repointed.".format(
                    display_idx, n, "s" if n != 1 else ""))

        if modifyAllowed:
            report.Info("Done with '{0}': {1} total occurrence{2} repointed.".format(
                form, total_repointed, "s" if total_repointed != 1 else ""))
            multi_wf.pop(chosen_idx)
        else:
            report.Warning(
                "[DRY RUN] '{0}': {1} occurrence{2} would be repointed. "
                "Run with Modify enabled to apply.".format(
                    form, total_repointed, "s" if total_repointed != 1 else ""))

    report.Info("All wordforms with multiple analyses have been resolved.")


FlexToolsModule = FlexToolsModuleClass(
    runFunction=MergeAnalyses,
    docs=docs
)
