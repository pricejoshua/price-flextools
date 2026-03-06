# -*- coding: utf-8 -*-
#
#   Fix Duplicate Custom Fields
#    - A FlexTools Module -
#
#   Automatically detects duplicate LexEntry custom field pairs where one
#   field's internal name is another field's name with a trailing digit
#   (e.g. "TC" / "TC1", "Top Ten" / "Top Ten1").
#
#   For every entry the module:
#     1. Reads the value from the duplicate field.
#     2. If the duplicate has data and the primary is empty  ->  copies the
#        value into the primary field.
#     3. If both fields have data and the values differ      ->  logs a
#        WARNING and leaves both untouched (manual review needed).
#     4. If the values match, or the duplicate is empty      ->  no action.
#     5. Clears the duplicate field on the entry.
#
#   After all entries have been processed the duplicate field definitions
#   are deleted from the project schema.
#
#   Run without write permission in FlexTools to preview changes safely.
#   Grant write permission to apply changes.
#

from flextoolslib import *
import re

# -----------------------------------------------------------------------
# Configuration

# Writing system used by these fields (wsSelector="-1" -> default analysis WS)
WS = "en"

# -----------------------------------------------------------------------

docs = {
    FTM_Name       : "Fix Duplicate Custom Fields",
    FTM_Version    : 4,
    FTM_ModifiesDB : True,
    FTM_Synopsis   : "Auto-detect and merge duplicate LexEntry custom fields (e.g. TC/TC1), then delete the duplicates",
    FTM_Description:
"""
Automatically detects duplicate LexEntry custom field pairs where one
field's internal name is another field's name with a trailing digit appended
(e.g. "TC" / "TC1", "Top Ten" / "Top Ten1", "Wordlist Number" / "Wordlist Number1").

For each detected pair the duplicate field's data is merged into the primary
field (if the primary is empty), the duplicate field value is cleared on every
entry, and finally the duplicate field definition is removed from the schema.

Run without write permission (the default in FlexTools) to preview all changes.
Grant write permission to apply changes.
""",
}

# -----------------------------------------------------------------------

def _build_field_map(project):
    """
    Return a dict mapping internal field name -> flid for all LexEntry
    custom fields, using the MetaDataCache to get true internal names
    (not display labels, which can be duplicated across fields).
    """
    mdc = project.lp.Cache.MetaDataCacheAccessor
    field_map = {}
    for flid, label in project.LexiconGetEntryCustomFields():
        internal_name = mdc.GetFieldName(flid)
        field_map[internal_name] = flid
    return field_map


def _detect_duplicate_pairs(field_map):
    """
    Find (primary, duplicate) pairs where the duplicate's internal name is
    the primary's name with one or more trailing digits appended.
    Returns a sorted list of (primary_name, duplicate_name) tuples.
    """
    pairs = []
    for name in field_map:
        m = re.match(r'^(.+?)(\d+)$', name)
        if m and m.group(1) in field_map:
            pairs.append((m.group(1), name))
    pairs.sort()
    return pairs


def _get_text(project, entry, flid):
    """Return the string value of a custom field, or '' if missing/blank."""
    try:
        val = project.LexiconGetFieldText(entry, flid, WS)
        return val.strip() if val else ""
    except Exception:
        return ""


def Main(project, report, modifyAllowed):
    if not modifyAllowed:
        report.Warning("Running without write permission - no changes will be made (preview mode).")

    # ------------------------------------------------------------------
    # Build internal-name -> flid map using MetaDataCache
    # ------------------------------------------------------------------
    field_map = _build_field_map(project)

    report.Info("Custom LexEntry fields found in schema (internal name: flid):")
    for name, flid in sorted(field_map.items()):
        report.Info(f"  '{name}': {flid}")

    # ------------------------------------------------------------------
    # Auto-detect duplicate pairs
    # ------------------------------------------------------------------
    duplicate_pairs = _detect_duplicate_pairs(field_map)

    if not duplicate_pairs:
        report.Info("No duplicate field pairs detected. Nothing to do.")
        return

    report.Info(f"Detected {len(duplicate_pairs)} duplicate pair(s):")
    for primary, duplicate in duplicate_pairs:
        report.Info(f"  '{primary}'  <-  '{duplicate}'")

    # ------------------------------------------------------------------
    # Count entries with data in each field
    # ------------------------------------------------------------------
    counted_names = {name for pair in duplicate_pairs for name in pair}
    field_counts = {name: 0 for name in counted_names}

    for entry in project.LexiconAllEntries():
        for name in counted_names:
            if _get_text(project, entry, field_map[name]):
                field_counts[name] += 1

    report.Info("Entries with data per field:")
    for primary, duplicate in duplicate_pairs:
        report.Info(f"  '{primary}': {field_counts[primary]}   '{duplicate}': {field_counts[duplicate]}")

    # ------------------------------------------------------------------
    # Per-entry processing
    # ------------------------------------------------------------------
    conflict_count   = 0
    moved_count      = 0
    already_ok_count = 0
    cleared_count    = 0

    for entry in project.LexiconAllEntries():
        headword = project.LexiconGetHeadword(entry)

        for primary, duplicate in duplicate_pairs:
            primary_flid   = field_map[primary]
            duplicate_flid = field_map[duplicate]

            primary_val   = _get_text(project, entry, primary_flid)
            duplicate_val = _get_text(project, entry, duplicate_flid)

            if duplicate_val:
                if not primary_val:
                    report.Info(
                        f"  MOVE  '{headword}': '{duplicate}' value '{duplicate_val}' "
                        f"-> '{primary}'"
                    )
                    if modifyAllowed:
                        project.LexiconSetFieldText(entry, primary_flid, duplicate_val, WS)
                    moved_count += 1

                elif primary_val == duplicate_val:
                    report.Info(
                        f"  SAME  '{headword}': '{primary}' and '{duplicate}' "
                        f"both = '{primary_val}' (will clear duplicate)"
                    )
                    already_ok_count += 1

                else:
                    report.Warning(
                        f"  CONFLICT  '{headword}': "
                        f"'{primary}'='{primary_val}'  vs  '{duplicate}'='{duplicate_val}'"
                        f" - leaving untouched"
                    )
                    conflict_count += 1
                    continue   # Do NOT clear - preserve both values for manual review

            # Always clear the duplicate field on every entry (even if already
            # empty) so no orphaned <Custom> XML elements remain after the field
            # definition is deleted.
            if modifyAllowed:
                project.LexiconClearField(entry, duplicate_flid)
            cleared_count += 1

    # ------------------------------------------------------------------
    # Summary
    # ------------------------------------------------------------------
    report.Info("-" * 60)
    report.Info(f"Entries where duplicate data was moved : {moved_count}")
    report.Info(f"Entries where values already matched   : {already_ok_count}")
    report.Info(f"Entries with conflicts (not touched)   : {conflict_count}")
    report.Info(f"Duplicate field values cleared         : {cleared_count}")

    if conflict_count:
        report.Warning(
            f"{conflict_count} conflict(s) found - resolve these manually before "
            "re-running to delete the duplicate field definitions."
        )

    # ------------------------------------------------------------------
    # Delete duplicate field definitions (only if no conflicts remain)
    # Uses IFwMetaDataCacheManaged.DeleteCustomField() via the LCM cache.
    # ------------------------------------------------------------------
    if conflict_count == 0:
        from SIL.LCModel.Infrastructure import IFwMetaDataCacheManaged
        mdc_managed = IFwMetaDataCacheManaged(project.lp.Cache.MetaDataCacheAccessor)

        for primary, duplicate in duplicate_pairs:
            dup_flid = field_map[duplicate]
            action = "DELETE" if modifyAllowed else "DELETE (preview)"
            report.Info(f"  {action} field definition '{duplicate}' (flid={dup_flid})")
            if modifyAllowed:
                mdc_managed.DeleteCustomField(dup_flid)
    else:
        report.Warning(
            "Skipping field definition deletion because conflicts were found. "
            "Fix conflicts first, then re-run."
        )

    report.Info("Done.")


# -----------------------------------------------------------------------

FlexToolsModule = FlexToolsModuleClass(Main, docs)

# -----------------------------------------------------------------------
if __name__ == "__main__":
    print(FlexToolsModule.Help())
