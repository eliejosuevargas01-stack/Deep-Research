"""stdlib-only isolated checks for the proposed Writer policy."""
import unittest
from proposal_writer_guardrail import render_gap_report, validate_lines


class ProposalTests(unittest.TestCase):
    def test_exact_classroom_example_passes(self):
        line = '**Proposta didática:** desenhe dois cartões, 0 e 1; use moeda parada para representar escolha entre ambos; depois pergunte: “Onde comparação deixa de funcionar?”'
        validate_lines(line, set())

    def test_bold_factual_claim_fails(self):
        with self.assertRaisesRegex(ValueError, "uncited"):
            validate_lines("**A população dobrou desde 2020.**", set())

    def test_unordered_numbered_and_table_facts_fail(self):
        for line in ("- O indicador aumentou no período observado", "1. O indicador aumentou no período observado", "| População | 42 milhões |"):
            with self.subTest(line=line), self.assertRaisesRegex(ValueError, "uncited"):
                validate_lines(line, set())

    def test_zero_evidence_emits_gaps_without_links(self):
        report = render_gap_report([("Panorama", False), ("Impacto", False)])
        self.assertIn("Lacuna:", report)
        self.assertEqual(report.count("https://"), 0)

    def test_fabricated_url_rejected(self):
        with self.assertRaisesRegex(ValueError, "uncollected"):
            validate_lines("Fato comprovado [fonte](https://inventado.invalid).", set())

    def test_mixed_keeps_cited_claim_and_gap_notice(self):
        trusted = "https://example.org/source"
        mixed = "Fato citado [fonte](https://example.org/source).\n\n## Ponto sem evidência\nLacuna: nenhuma evidência aproveitável após quatro tentativas. Conteúdo não disponível; sem fontes para citar."
        validate_lines(mixed, {trusted})
        report = render_gap_report([("Com evidência", True), ("Sem evidência", False)])
        self.assertIn("Evidência disponível", report)
        self.assertIn("Lacuna:", report)


if __name__ == "__main__":
    unittest.main()
