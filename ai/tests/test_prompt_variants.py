import unittest
from types import SimpleNamespace
from unittest.mock import patch

from services.llm_postprocessor import postprocess_with_llm


class PromptVariantTests(unittest.TestCase):
    def test_fictional_examples_are_opt_in_and_real_input_is_unchanged(self):
        evidence = [{"id": "stt-001", "text": "실제 입력"}]
        with patch("services.llm_postprocessor.GEMINI_API_KEY", "test"), patch("services.llm_postprocessor.create_gemini_client") as create:
            model = create.return_value.models
            model.generate_content.return_value = SimpleNamespace(text="{}")
            for variant in ("baseline", "few_shot_v1"):
                postprocess_with_llm("실제 입력", [], [], evidence_units=evidence, prompt_variant=variant)
            baseline = model.generate_content.call_args_list[0].kwargs["contents"]
            fewshot = model.generate_content.call_args_list[1].kwargs["contents"]
        self.assertIn("실제 입력", baseline)
        self.assertIn("실제 입력", fewshot)
        self.assertNotIn("가상 제품 A", baseline)
        self.assertIn("가상 제품 A", fewshot)
        self.assertIn("Do not copy names or example IDs", fewshot)

    def test_list_videos_keep_all_evidence_units_up_to_the_larger_cap(self):
        evidence = [{"id": f"ocr-{i:03d}", "text": f"줄 {i}", "timeMs": i * 100} for i in range(1, 301)]
        with patch("services.llm_postprocessor.GEMINI_API_KEY", "test"), patch("services.llm_postprocessor.create_gemini_client") as create:
            model = create.return_value.models
            model.generate_content.return_value = SimpleNamespace(text="{}")
            postprocess_with_llm("", [], [], evidence_units=evidence, prompt_variant="structured_v2")
            prompt = model.generate_content.call_args.kwargs["contents"]
        for unit_id in ("ocr-001", "ocr-150", "ocr-201", "ocr-300"):
            self.assertIn(unit_id, prompt)  # the old 200-unit sampling dropped many of these

    def test_temporary_overload_is_retried_then_falls_back_to_another_model(self):
        import os
        from services import llm_postprocessor as lp
        client = SimpleNamespace(models=SimpleNamespace(generate_content=unittest.mock.Mock(side_effect=[
            RuntimeError("503 UNAVAILABLE"), RuntimeError("504 DEADLINE_EXCEEDED"), SimpleNamespace(text="ok")])))
        with patch.dict(os.environ, {"GEMINI_FALLBACK_MODEL": "backup-model"}), patch.object(lp.time, "sleep") as sleep:
            result = lp._generate_with_retry(client, model="main-model", contents="x")
        self.assertEqual(result.text, "ok")
        models = [call.kwargs["model"] for call in client.models.generate_content.call_args_list]
        self.assertEqual(models, ["main-model", "main-model", "backup-model"])
        self.assertEqual([call.args[0] for call in sleep.call_args_list], [4, 10])

    def test_quota_and_other_errors_are_not_retried(self):
        from services import llm_postprocessor as lp
        client = SimpleNamespace(models=SimpleNamespace(generate_content=unittest.mock.Mock(
            side_effect=RuntimeError("429 RESOURCE_EXHAUSTED"))))
        with patch.object(lp.time, "sleep") as sleep:
            with self.assertRaises(RuntimeError):
                lp._generate_with_retry(client, model="main-model", contents="x")
        self.assertEqual(client.models.generate_content.call_count, 1)
        sleep.assert_not_called()

    def test_default_variant_comes_from_environment_and_ignores_unknown_values(self):
        import os
        from services.llm_postprocessor import default_prompt_variant
        for value, expected in (("baseline", "baseline"), ("few_shot_v1", "few_shot_v1"),
                                ("nope", "structured_v2"), ("", "structured_v2")):
            with patch.dict(os.environ, {"DEFAULT_PROMPT_VARIANT": value}):
                self.assertEqual(default_prompt_variant(), expected)
        with patch.dict(os.environ, {}, clear=False):
            os.environ.pop("DEFAULT_PROMPT_VARIANT", None)
            self.assertEqual(default_prompt_variant(), "structured_v2")

    def test_structured_v2_rules_are_opt_in(self):
        evidence = [{"id": "stt-001", "text": "실제 입력"}]
        with patch("services.llm_postprocessor.GEMINI_API_KEY", "test"), patch("services.llm_postprocessor.create_gemini_client") as create:
            model = create.return_value.models
            model.generate_content.return_value = SimpleNamespace(text="{}")
            for variant in ("baseline", "few_shot_v1", "structured_v2"):
                postprocess_with_llm("실제 입력", [], [], evidence_units=evidence, prompt_variant=variant)
            prompts = [call.kwargs["contents"] for call in model.generate_content.call_args_list]
        self.assertNotIn("STRUCTURED V2 RULES", prompts[0])
        self.assertNotIn("STRUCTURED V2 RULES", prompts[1])
        self.assertIn("STRUCTURED V2 RULES", prompts[2])
        for rule in ("NAMES.", "COMPLETENESS.", "REQUIRED FIELDS.", "SECTIONS.", "CLAIMS.", "NO DUPLICATION.", "WORDING.", "CLAIM FORMAT.", "ITEM COUNT."):
            self.assertIn(rule, prompts[2])
        schemas = [call.kwargs["config"].response_schema for call in model.generate_content.call_args_list]
        self.assertNotIn("announcedItemCount", schemas[0]["properties"])
        self.assertEqual(schemas[2]["propertyOrdering"][0], "announcedItemCount")
        self.assertLess(schemas[2]["propertyOrdering"].index("announcedItemCount"), schemas[2]["propertyOrdering"].index("targets"))
        self.assertIn("실제 입력", prompts[2])
        self.assertNotIn("가상 제품 A", prompts[2])
