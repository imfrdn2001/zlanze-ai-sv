from app.scope import requests_all_pending_options


QUESTION = (
    "Are you looking for a basic informational website, an online store, "
    "or a custom portal with client accounts?"
)


def test_request_for_developers_and_cost_for_these_means_all_options() -> None:
    assert requests_all_pending_options(
        "Can you suggest developers and cost to build these?", QUESTION
    )


def test_single_option_answer_does_not_trigger_comparison() -> None:
    assert not requests_all_pending_options("I want the online store", QUESTION)


def test_comparison_requires_pending_clarification() -> None:
    assert not requests_all_pending_options("Compare all three", None)
