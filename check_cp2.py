"""Extra CP2 contract checks: python check_cp2.py (no API calls)."""

import math

from template import LLMJudge, RAGASEvaluator


def check_metrics() -> None:
    evaluator = RAGASEvaluator()
    assert evaluator.evaluate_faithfulness("the", "") == 1.0
    assert evaluator.evaluate_relevance("", "the") == 1.0
    assert evaluator.evaluate_completeness("", "the") == 1.0
    assert evaluator.evaluate_context_recall([], "the") == 1.0
    assert evaluator.evaluate_context_precision([], "the") == 1.0
    assert evaluator.evaluate_context_recall([], "alpha") == 0.0
    assert evaluator.evaluate_context_precision(["noise"], "alpha") == 0.0
    assert evaluator.evaluate_faithfulness("alpha beta", "alpha") == 0.5
    assert evaluator.evaluate_relevance("alpha", "alpha beta") == 0.5
    assert evaluator.evaluate_completeness("alpha", "alpha beta") == 0.5
    chunks = ["alpha", "noise", "beta"]
    assert evaluator.evaluate_context_recall(chunks, "alpha beta") == 1.0
    assert evaluator.evaluate_context_recall(chunks[::-1], "alpha beta") == 1.0
    assert math.isclose(evaluator.evaluate_context_precision(chunks, "alpha beta"), 5 / 6)

    for question, context, expected, failure_type in [
        ("noise", "noise", "noise", "hallucination"),
        ("noise", "alpha", "noise", "irrelevant"),
        ("alpha", "alpha", "noise", "incomplete"),
        ("alpha beta gamma", "alpha", "alpha", "off_topic"),
        ("alpha beta", "alpha", "alpha beta", None),
    ]:
        result = evaluator.run_full_eval("alpha", question, context, expected)
        assert result.failure_type == failure_type
        assert result.passed == (failure_type is None)
        assert result.context_recall is None and result.context_precision is None

    result = evaluator.run_full_eval("alpha", "alpha", "alpha", "alpha", [])
    assert result.context_recall == 0.0 and result.context_precision == 0.0
    assert result.passed and result.overall_score() == 1.0
    assert result.qa_pair.expected_answer == "alpha"
    assert result.actual_answer == "alpha"


def check_judge() -> None:
    rubric = {"accuracy": "Correct policy", "clarity": "Clear answer"}
    prompts = []

    def judge_response(prompt: str) -> str:
        prompts.append(prompt)
        return '{"accuracy": 0.8, "clarity": 0.7}'

    result = LLMJudge(judge_response).score_response("Warranty?", "24 months", rubric)
    assert result["scores"] == {"accuracy": 0.8, "clarity": 0.7}
    assert result["reasoning"] == '{"accuracy": 0.8, "clarity": 0.7}'
    assert all(text in prompts[0] for text in ["Warranty?", "24 months", "Correct policy", "Clear answer"])
    for response in ["not JSON", "[]", "null", '{}', '{"accuracy": true, "clarity": 0.7}',
                     '{"accuracy": 5, "clarity": 0.7}', '{"accuracy": NaN, "clarity": 0.7}']:
        result = LLMJudge(lambda _: response).score_response("Q", "A", rubric)
        assert result["scores"] == {"accuracy": 0.5, "clarity": 0.5}
        assert result["reasoning"] == response

    judge = LLMJudge(judge_response)
    assert not any(judge.detect_bias([]).values())
    assert not any(judge.detect_bias([{"scores": {}}]).values())
    for score, lenient, severe in [(0.8, False, False), (0.3, False, False),
                                   (0.9, True, False), (0.2, False, True)]:
        flags = judge.detect_bias([{"scores": {"accuracy": score}}])
        assert flags == {"positional_bias": False, "leniency_bias": lenient, "severity_bias": severe}
    # Adjacent entries represent first/second responses for each matched trial.
    batch = [{"scores": {"accuracy": score}} for score in [0.7, 0.4, 0.8, 0.5]]
    assert judge.detect_bias(batch)["positional_bias"]
    batch[-1]["scores"]["accuracy"] = 0.9
    assert not judge.detect_bias(batch)["positional_bias"]


if __name__ == "__main__":
    check_metrics()
    check_judge()
    print("CP2 contract checks passed")
