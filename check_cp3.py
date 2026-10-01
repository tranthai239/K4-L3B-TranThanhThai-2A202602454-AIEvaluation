"""Extra CP3 contract checks: python check_cp3.py (no API calls)."""

from template import BenchmarkRunner, EvalResult, FailureAnalyzer, QAPair, RAGASEvaluator


def result(f: float, r: float, c: float, kind: str | None = None) -> EvalResult:
    return EvalResult(QAPair("question", "expected"), "actual", f, r, c,
                      min(f, r, c) >= 0.5, kind)


def check_runner() -> None:
    runner = BenchmarkRunner()
    pair = QAPair("alpha", "alpha", "alpha", {"id": "E01"}, ["alpha"])
    outputs = runner.run([pair], lambda question: question, RAGASEvaluator())
    assert outputs[0].qa_pair is pair
    assert outputs[0].context_recall == 1.0
    assert outputs[0].actual_answer == "alpha"
    assert runner.run([], lambda question: question, RAGASEvaluator()) == []

    empty = runner.generate_report([])
    assert empty == {
        "total": 0, "passed": 0, "pass_rate": 0.0,
        "avg_faithfulness": 0.0, "avg_relevance": 0.0, "avg_completeness": 0.0,
        "avg_context_recall": None, "avg_context_precision": None, "failure_types": {},
    }
    good, bad = result(0.8, 0.8, 0.8), result(0.2, 0.2, 0.2, "hallucination")
    good.context_recall = 0.0
    bad.context_precision = 0.5
    report = runner.generate_report([good, bad])
    assert report["total"] == 2 and report["pass_rate"] == 0.5
    assert report["avg_faithfulness"] == 0.5
    assert report["avg_context_recall"] == 0.0
    assert report["avg_context_precision"] == 0.5
    assert report["failure_types"] == {"hallucination": 1}
    boundary = result(0.5, 0.5, 0.5)
    boundary.context_recall = 0.0
    assert runner.identify_failures([boundary]) == []
    assert runner.identify_failures([good], 0.9) == [good]

    baseline = [result(0.9, 0.9, 0.9)]
    assert runner.run_regression([result(0.85, 0.85, 0.85)], baseline)["passed"]
    regression = runner.run_regression([result(0.84, 0.9, 0.8)], baseline)
    assert regression["regressions"] == ["faithfulness", "completeness"]
    assert not regression["passed"]
    assert regression["baseline_avg_relevance"] == 0.9
    for new, old in [([], baseline), (baseline, []), ([], [])]:
        try:
            runner.run_regression(new, old)
        except ValueError:
            pass
        else:
            raise AssertionError("Empty regression input must not pass a quality gate")


def check_analyzer() -> None:
    analyzer = FailureAnalyzer()
    failures = [result(0.1, 0.8, 0.8, "hallucination"),
                result(0.8, 0.1, 0.8, "irrelevant"),
                result(0.8, 0.8, 0.1, "incomplete")]
    expected = [
        "Context is missing or irrelevant — improve retrieval",
        "Answer does not address the question — improve prompt clarity",
        "Answer is missing key information — increase context window or improve generation",
    ]
    assert [analyzer.find_root_cause(item) for item in failures] == expected
    assert analyzer.find_root_cause(result(0.1, 0.1, 0.8)) == "Multiple issues detected — review full pipeline"
    assert analyzer.categorize_failures(failures) == {"hallucination": 1, "irrelevant": 1, "incomplete": 1}
    assert analyzer.generate_improvement_suggestions([]) == []
    assert len(analyzer.generate_improvement_suggestions(failures[:1])) >= 3
    suggestions = analyzer.generate_improvement_suggestions([failures[2], failures[2], failures[0]])
    assert "expected answer" in suggestions[0].lower()
    log = analyzer.generate_improvement_log(failures, ["Check evidence | conditions\nThen rerun"])
    assert "F001" in log and "F003" in log and log.count("Open") == 3
    assert "\\|" in log and len(log.splitlines()) == 5
    assert "review" in log.lower()
    assert len(analyzer.generate_improvement_log([], []).splitlines()) == 2


if __name__ == "__main__":
    check_runner()
    check_analyzer()
    print("CP3 contract checks passed")
