import hashlib
import json
import tempfile
import unittest
from pathlib import Path

from runbook_trustlayer import RunbookQAPipeline, validate_output_folder


class RunbookTrustLayerTests(unittest.TestCase):
    def test_valid_bundle_passes_with_nonblocking_warnings(self):
        with tempfile.TemporaryDirectory() as tmp:
            output = self._write_valid_bundle(Path(tmp))

            report = validate_output_folder(output)

            self.assertEqual(report.status, "pass")
            self.assertTrue(any(claim["risk"] == "high" for claim in report.enriched_claims))
            self.assertTrue(
                any(result.check_type == "schema_validation" and result.status == "warning" for result in report.checks)
            )

    def test_missing_core_artifact_blocks_release(self):
        with tempfile.TemporaryDirectory() as tmp:
            output = self._write_valid_bundle(Path(tmp))
            (output / "final_artifact.md").unlink()

            report = validate_output_folder(output)

            self.assertEqual(report.status, "block_release")
            self.assertTrue(any("Missing required final artifact" in result.message for result in report.checks))

    def test_missing_required_data_points_regenerates_when_product_spec_declares_them(self):
        with tempfile.TemporaryDirectory() as tmp:
            output = self._write_valid_bundle(Path(tmp))
            (output / "product_spec.json").write_text(
                json.dumps(
                    {
                        "briefing_type": "default",
                        "required_sections": [],
                        "required_data_points": [
                            {
                                "name": "current_state_budget_total",
                                "required": True,
                                "claim_type": "budget_number",
                                "allowed_source_types": ["official_budget"],
                                "citation_required": True,
                            }
                        ],
                    }
                ),
                encoding="utf-8",
            )

            report = validate_output_folder(output)

            self.assertEqual(report.status, "regenerate")
            self.assertTrue(any("Missing required_data_points.json" in result.message for result in report.checks))

    def test_hash_mismatch_blocks_release(self):
        with tempfile.TemporaryDirectory() as tmp:
            output = self._write_valid_bundle(Path(tmp))
            sources = json.loads((output / "sources.json").read_text(encoding="utf-8"))
            sources[0]["content_hash"] = "sha256:deadbeef"
            (output / "sources.json").write_text(json.dumps(sources), encoding="utf-8")

            report = validate_output_folder(output)

            self.assertEqual(report.status, "block_release")
            self.assertTrue(any("content_hash does not match" in result.message for result in report.checks))

    def test_exact_copy_mismatch_blocks_high_weight_claim(self):
        with tempfile.TemporaryDirectory() as tmp:
            output = self._write_valid_bundle(Path(tmp), claim_amount="$33.1 billion")

            report = validate_output_folder(output)

            self.assertEqual(report.status, "block_release")
            self.assertTrue(any(result.check_type == "copy_check" and result.status == "fail" for result in report.checks))

    def test_cli_writer_emits_qa_results_and_repair_plan(self):
        with tempfile.TemporaryDirectory() as tmp:
            output = self._write_valid_bundle(Path(tmp), claim_amount="$33.1 billion")
            pipeline = RunbookQAPipeline()
            report = pipeline.validate(output)
            pipeline.write_outputs(report)

            self.assertTrue((output / "qa_results.json").exists())
            self.assertTrue((output / "repair_plan.json").exists())
            payload = json.loads((output / "qa_results.json").read_text(encoding="utf-8"))
            self.assertEqual(payload["status"], "block_release")

    def _write_valid_bundle(self, output: Path, claim_amount: str = "$32.1 billion") -> Path:
        output.mkdir(parents=True, exist_ok=True)
        snapshots = output / "source_snapshots"
        snapshots.mkdir()
        snapshot_text = "The enacted FY2026 state budget totals $32.1 billion."
        snapshot_path = snapshots / "source_001.txt"
        snapshot_path.write_text(snapshot_text, encoding="utf-8")
        digest = hashlib.sha256(snapshot_path.read_bytes()).hexdigest()

        (output / "final_artifact.md").write_text(
            f"# Executive Summary\n\nThe enacted FY2026 state budget totals {claim_amount} [source_001].\n",
            encoding="utf-8",
        )
        (output / "audit_bundle.json").write_text(
            json.dumps(
                {
                    "runbook_version": "test@1",
                    "briefing_type": "default",
                    "product_id": "test-briefing",
                    "jurisdiction": "North Carolina",
                    "official_role": "Governor",
                    "run_timestamp": "2026-05-02T20:30:00Z",
                    "generator_prompt_version": "generator_v1",
                    "qa_prompt_version": "qa_v1",
                    "final_artifact_path": "final_artifact.md",
                    "final_status": "pass",
                    "human_review_notes": [],
                }
            ),
            encoding="utf-8",
        )
        (output / "sources.json").write_text(
            json.dumps(
                [
                    {
                        "source_id": "source_001",
                        "source_type": "official_budget",
                        "title": "FY2026 Enacted State Budget",
                        "publisher": "State Budget Office",
                        "url": "https://example.gov/budget.pdf",
                        "retrieved_at": "2026-05-02T20:10:00Z",
                        "retrieval_method": "web_fetch",
                        "snapshot_path": "source_snapshots/source_001.txt",
                        "content_hash": f"sha256:{digest}",
                    }
                ]
            ),
            encoding="utf-8",
        )
        (output / "claims.json").write_text(
            json.dumps(
                [
                    {
                        "claim_id": "claim_001",
                        "section_id": "executive_summary",
                        "claim_text": f"The enacted FY2026 state budget totals {claim_amount}.",
                        "claim_type": "budget_number",
                        "citation_ids": ["source_001"],
                        "source_extracts": [
                            {
                                "source_id": "source_001",
                                "extract_id": "extract_001",
                                "text": snapshot_text,
                                "snapshot_path": "source_snapshots/source_001.txt",
                            }
                        ],
                        "required_source_type": "official_budget",
                        "route_if_unsupported": "block_release",
                    }
                ]
            ),
            encoding="utf-8",
        )
        (output / "qa_results.json").write_text("{}", encoding="utf-8")
        return output


if __name__ == "__main__":
    unittest.main()

