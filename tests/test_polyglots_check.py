"""
Tests for scripts/polyglots_check.py.

One hand-built .po block per rule (6a-6m from wp-polyglots-check/SKILL.md
Step 6, ported to code here), asserting both severity and rule id so a
regression that silently downgrades a rule doesn't slip through unnoticed.
Runs against small in-memory fixtures, not the real 562-row glossary --
that's what Phase 2's tests and the Phase 3 Step 6 regression run cover.
"""
import os
import sys
import tempfile
import unittest

TESTS_DIR = os.path.dirname(os.path.abspath(__file__))
REPO_ROOT = os.path.dirname(TESTS_DIR)
DATA = os.path.join(REPO_ROOT, "data")

sys.path.insert(0, os.path.join(REPO_ROOT, "scripts"))

from polyglots_check import (  # noqa: E402
    check_6a, check_6b, check_6c, check_6d, check_6e, check_6f, check_6g,
    check_6h, check_6i, check_6j, check_6k, check_6l, check_6m,
    check_entry, run_checks, build_invariato_terms,
)
from glossary import load_glossary  # noqa: E402


class TestIndividualRules(unittest.TestCase):
    def test_6a_plugin_name_translated_is_error(self):
        f = check_6a("Fotonic", "Eleva CRM", ["Plugin Name of the plugin"])
        self.assertIsNotNone(f)
        self.assertEqual((f.rule, f.severity), ("6a", "ERROR"))

    def test_6a_plugin_name_left_alone_passes(self):
        self.assertIsNone(check_6a("Fotonic", "Fotonic", ["Plugin Name of the plugin"]))

    def test_6a_translators_note_mentioning_plugin_name_is_not_flagged(self):
        """Real false positive found against fotonic-pro's it_IT.po: a
        developer's own translators note ('translators: 1: Plugin name
        "Eleva CRM Pro" 2: ...') is not one of WP.org's structural
        Plugin-Name/Author/changelog markers just because it contains that
        phrase mid-sentence."""
        comments = ['translators: 1: Plugin name "Eleva CRM Pro" 2: Plugin name "Eleva CRM"']
        self.assertIsNone(check_6a(
            "%1$s requires the free %2$s plugin to be active.",
            "%1$s richiede che il plugin gratuito %2$s sia attivo.",
            comments,
        ))

    def test_6b_fuzzy_with_content_is_warning(self):
        f = check_6b("Save", "Salva", {"fuzzy"})
        self.assertEqual((f.rule, f.severity), ("6b", "WARNING"))

    def test_6b_not_fuzzy_passes(self):
        self.assertIsNone(check_6b("Save", "Salva", set()))

    def test_6c_missing_placeholder_is_error(self):
        f = check_6c("Hello %s, you have %d messages", "Ciao, hai messaggi")
        self.assertEqual((f.rule, f.severity), ("6c", "ERROR"))

    def test_6c_placeholders_intact_passes(self):
        self.assertIsNone(check_6c("Hello %s", "Ciao %s"))

    def test_6c_reordered_numbered_placeholders_is_error(self):
        f = check_6c("From %1$s to %2$s", "A %2$s da %1$s")
        self.assertEqual((f.rule, f.severity), ("6c", "ERROR"))

    def test_6d_missing_html_tag_is_error(self):
        f = check_6d('Click <a href="%s">here</a>', "Clicca qui")
        self.assertEqual((f.rule, f.severity), ("6d", "ERROR"))

    def test_6d_tags_intact_passes(self):
        self.assertIsNone(check_6d('Click <a href="%s">here</a>', '<a href="%s">Clicca qui</a>'))

    def test_6e_apostrophe_for_accent_is_error(self):
        f = check_6e("Done", "e' completato")
        self.assertEqual((f.rule, f.severity), ("6e", "ERROR"))

    def test_6e_correct_accent_passes(self):
        self.assertIsNone(check_6e("Done", "è completato"))

    def test_6f_title_case_is_warning(self):
        f = check_6f("Save Changes Now", "Salva Le Modifiche Adesso")
        self.assertEqual((f.rule, f.severity), ("6f", "WARNING"))

    def test_6f_normal_sentence_case_passes(self):
        self.assertIsNone(check_6f("Save changes", "Salva le modifiche"))

    def test_6f_acronyms_and_proper_nouns_not_flagged(self):
        """Real false positives from the free-plugin .po. Counting 3
        consecutive capitalised words flagged all of these; none is Title
        Case."""
        for s in [
            "Fotonic richiede l'estensione PHP OpenSSL. Abilitala sul tuo server.",
            "Immagini, PDF, DOC, DOCX max 10 MB ciascuno",
            "Apri la tua app di autenticazione (Google Authenticator, Authy, ecc.)",
            "Questo sito è eseguito su Local by Flywheel ed esiste solo su questo computer",
        ]:
            self.assertIsNone(check_6f("x", s), f"false positive on: {s}")

    def test_6f_sentence_initial_function_word_not_flagged(self):
        """A function word opening a new sentence after '.' or '?' is
        correctly capitalised. Ignoring sentence boundaries flagged 17
        correct strings in the real .po."""
        for s in [
            "Genera un nuovo codice di recupero. Il codice precedente verrà invalidato.",
            "Vuoi eliminare questa scheda? Questa azione è irreversibile.",
        ]:
            self.assertIsNone(check_6f("x", s), f"false positive on: {s}")

    def test_6g_space_before_punctuation_is_warning(self):
        f = check_6g("Done.", "Fatto .")
        self.assertEqual((f.rule, f.severity), ("6g", "WARNING"))

    def test_6g_clean_punctuation_passes(self):
        self.assertIsNone(check_6g("Done.", "Fatto."))

    def test_6g_oxford_comma_in_a_real_list_is_flagged(self):
        f = check_6g("one, two, and three", "uno, due, e tre")
        self.assertEqual((f.rule, f.severity), ("6g", "WARNING"))

    def test_6g_comma_joining_two_clauses_is_not_an_oxford_comma(self):
        """Real false positive from both Fotonic .po files. The it_IT
        handbook scopes this rule to the comma before the conjunction
        ENDING A LIST; a comma joining independent clauses is correct."""
        self.assertIsNone(check_6g(
            "Encrypted backups need the PHP Sodium and Zip extensions, and this server lacks them.",
            "I backup cifrati richiedono le estensioni PHP Sodium e Zip, e questo server non le ha.",
        ))

    def test_6h_ampersand_conjunction_is_warning(self):
        f = check_6h("Name & Address", "Nome & Indirizzo")
        self.assertEqual((f.rule, f.severity), ("6h", "WARNING"))

    def test_6h_html_entity_ampersand_passes(self):
        self.assertIsNone(check_6h("Terms &amp; Conditions", "Termini &amp; Condizioni"))

    def test_6i_generalised_loanword_plural_is_warning(self):
        entries = load_glossary("it", DATA)
        invariato = build_invariato_terms(entries)
        self.assertIn("plugin", invariato)  # sanity: real glossary has it invariato
        f = check_6i("Manage plugins", "Gestisci i plugins", invariato)
        self.assertEqual((f.rule, f.severity), ("6i", "WARNING"))

    def test_6i_correct_invariant_plural_passes(self):
        entries = load_glossary("it", DATA)
        invariato = build_invariato_terms(entries)
        self.assertIsNone(check_6i("Manage plugins", "Gestisci i plugin", invariato))

    def test_6j_humanized_please_is_warning(self):
        f = check_6j("Please try again later", "Si prega di riprovare più tardi")
        self.assertEqual((f.rule, f.severity), ("6j", "WARNING"))

    def test_6j_dropped_please_passes(self):
        self.assertIsNone(check_6j("Please try again later", "Riprova più tardi"))

    def test_6k_gerund_without_in_corso_is_info(self):
        f = check_6k("Loading settings", "Caricamento impostazioni")
        self.assertEqual((f.rule, f.severity), ("6k", "INFO"))

    def test_6k_gerund_with_in_corso_passes(self):
        self.assertIsNone(check_6k("Loading settings", "Caricamento impostazioni in corso"))

    def test_6l_12_hour_format_kept_is_warning(self):
        f = check_6l("M j, Y g:i A", "M j, Y g:i A")
        self.assertEqual((f.rule, f.severity), ("6l", "WARNING"))

    def test_6l_24_hour_format_passes(self):
        self.assertIsNone(check_6l("M j, Y g:i A", "j M Y H:i"))

    def test_6m_bare_wordpress_org_url_is_info(self):
        f = check_6m("See docs", "Vedi https://wordpress.org/support/")
        self.assertEqual((f.rule, f.severity), ("6m", "INFO"))

    def test_6m_localized_url_passes(self):
        self.assertIsNone(check_6m("See docs", "Vedi https://it.wordpress.org/support/"))


class TestCheckEntryAndGlossaryMerge(unittest.TestCase):
    def test_empty_msgstr_is_skipped_entirely(self):
        """Untranslated strings are wp-i18n-doctor's concern (NOT_IN_PO /
        EMPTY_MSGSTR), not this skill's -- running compliance rules on
        nothing to check would just be noise."""
        findings, glossary_findings = run_checks_on_blocks(
            [("Dashboard", 'msgid "Dashboard"\nmsgstr ""')],
            slug="it",
        )
        self.assertEqual(findings, [])
        self.assertEqual(glossary_findings, [])

    def test_msgstr_equal_to_msgid_is_still_glossary_checked(self):
        """Mirrors glossary.py's own fix: leaving 'Dashboard' untranslated
        (msgstr == msgid) must still surface as a GLOSSARY finding, matching
        Phase 2's test_untranslated_entry_is_still_checked."""
        findings, glossary_findings = run_checks_on_blocks(
            [("Dashboard", 'msgid "Dashboard"\nmsgstr "Dashboard"')],
            slug="it",
        )
        self.assertTrue(any(g.term == "dashboard" for g in glossary_findings))

    def test_overlay_flows_through_to_glossary_findings(self):
        overlay = os.path.join(TESTS_DIR, "fixtures", "overlay-it_IT.csv")
        findings, glossary_findings = run_checks_on_blocks(
            [("Required plugin", 'msgid "Required plugin"\nmsgstr "Plugin necessario"')],
            slug="it",
            overlay_path=overlay,
        )
        self.assertTrue(any(g.source == "overlay" for g in glossary_findings))


def run_checks_on_blocks(msgid_msgstr_pairs, slug, overlay_path=None):
    """Write pairs to a throwaway .po file and run the real run_checks()
    pipeline end-to-end -- proves the file-loading glue works, not just the
    per-rule functions tested above."""
    header = (
        'msgid ""\nmsgstr ""\n"Content-Type: text/plain; charset=UTF-8\\n"\n\n'
    )
    body = "\n\n".join(block for _, block in msgid_msgstr_pairs)
    with tempfile.NamedTemporaryFile("w", suffix=".po", delete=False, encoding="utf-8") as f:
        f.write(header + body + "\n")
        path = f.name
    try:
        return run_checks(path, slug, DATA, overlay_path=overlay_path)
    finally:
        os.unlink(path)


if __name__ == "__main__":
    unittest.main()
