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
