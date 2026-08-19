"""
Tests for scripts/glossary.py.

Uses the real it.csv glossary (data/glossaries/it.csv, 562 rows fetched from
GlotPress) rather than a hand-built fixture, because every case here traces
back to an actual finding from running the engine's prototype against the
free plugin's real it_IT.po. See the plan's "Measured baseline" section.
"""
import os
import sys
import unittest

TESTS_DIR = os.path.dirname(os.path.abspath(__file__))
REPO_ROOT = os.path.dirname(TESTS_DIR)
DATA = os.path.join(REPO_ROOT, "data")
FIXTURE_OVERLAY = os.path.join(TESTS_DIR, "fixtures", "overlay-it_IT.csv")

sys.path.insert(0, os.path.join(REPO_ROOT, "scripts"))

from glossary import load_glossary, find_candidates, is_po_header_block  # noqa: E402


class TestFindCandidates(unittest.TestCase):
    def test_untranslated_entry_is_still_checked(self):
        """msgstr == msgid is a VIOLATION for a translatable term.
        Dashboard -> 'Bacheca' in the it glossary; leaving 'Dashboard' is
        wrong. Skipping msgstr == msgid entries silently hides this."""
        e = load_glossary("it", DATA)
        self.assertTrue(find_candidates(e, "Dashboard", "Dashboard"))

    def test_invariato_term_may_use_either_form(self):
        """'upload' has BOTH an invariato noun entry and a 'carica' verb
        entry. 'Upload File' -> 'Carica file' is correct and must not be
        flagged."""
        e = load_glossary("it", DATA)
        self.assertFalse(find_candidates(e, "Upload File", "Carica file"))

    def test_meta_valued_target_inverts_the_check(self):
        """The it glossary target for 'Please' is the instruction
        'NON SI TRADUCE'. Correct behaviour is to DROP it, so a msgstr that
        drops it passes. A generic accent/stem matcher can only verify the
        literal survival case (translator left 'Please' untranslated) —
        recognising a humanized rendering like 'si prega' needs
        locale-specific phrasing knowledge, which is polyglots_check.py's
        rule 6j (Phase 3), not this engine's job."""
        e = load_glossary("it", DATA)
        self.assertFalse(find_candidates(e, "Please enable it.", "Abilitala."))
        self.assertTrue(
            find_candidates(e, "Please enable it.", "Please, abilitala.")
        )

    def test_inflected_translation_passes_via_stem(self):
        """Glossary lemma 'eliminato' vs real msgstr 'eliminati'. Whole-word
        matching produces a false positive; stem matching must not."""
        e = load_glossary("it", DATA)
        self.assertFalse(
            find_candidates(e, "Item deleted", "Elemento eliminato definitivamente")
        )

    def test_real_violation_survives_stemming(self):
        """'required' -> 'necessario' (stem 'neces'); 'richiesta' shares no
        stem, so the 21 real hits must still be flagged."""
        e = load_glossary("it", DATA)
        self.assertTrue(
            find_candidates(e, "Password is required.", "La password è richiesta.")
        )

    def test_allcaps_literal_is_not_a_term_hit(self):
        """'Type RESET to confirm' -> 'Digita RESET per confermare'. RESET is
        a literal the user types, not the glossary verb 'reset'."""
        e = load_glossary("it", DATA)
        self.assertFalse(
            find_candidates(e, "Type RESET to confirm", "Digita RESET per confermare")
        )

    def test_overlay_outranks_locale_glossary(self):
        """Alessandro's PTE ruling: 'required plugin' -> 'plugin richiesto',
        which contradicts the bare locale entry 'required' -> 'necessario'.
        GlotPress ranks the project glossary first; so must we."""
        e = load_glossary("it", DATA, overlay_path=FIXTURE_OVERLAY)
        c = find_candidates(e, "Required plugin", "Plugin necessario")
        self.assertTrue(c)
        self.assertEqual(c[0].source, "overlay")
        self.assertEqual(c[0].expected, "plugin richiesto")


class TestPoHeaderDetection(unittest.TestCase):
    def test_real_po_header_is_detected(self):
        """po_manager.parse_po_blocks() mis-attributes the header's msgstr
        continuation lines to msgid instead of returning msgid=None for it
        (a bug in that existing, unmodified file) -- confirmed against the
        real free-plugin it_IT.po, whose header produced fake 'domain' and
        'last' glossary candidates (from its X-Domain:/Last-Translator:
        fields) before this guard existed."""
        block = (
            '# Italian translation\n'
            'msgid ""\n'
            'msgstr ""\n'
            '"Project-Id-Version: eleva-crm-for-photographers 1.3.8\\n"\n'
            '"Last-Translator: FULL NAME <EMAIL@ADDRESS>\\n"\n'
        )
        self.assertTrue(is_po_header_block(block))

    def test_real_entry_is_not_mistaken_for_header(self):
        block = 'msgid "Last Name"\nmsgstr "Cognome"\n'
        self.assertFalse(is_po_header_block(block))


if __name__ == "__main__":
    unittest.main()
