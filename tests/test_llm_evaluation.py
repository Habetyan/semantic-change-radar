from evaluation.compare_llm import validate_response


def response(content: str, reason: str = "stop") -> dict:
    return {"done": True, "done_reason": reason, "message": {"content": content}}


def test_generated_decisions_require_literal_evidence_and_complete_json():
    record = {"old_text": "Only guests may read.", "new_text": "Only members may read."}
    valid = (
        '{"status":"modified","reason":"Actor changes.","old_quote":"guests","new_quote":"members"}'
    )
    prediction, error = validate_response(response(valid), record)
    assert prediction["status"] == "modified" and error is None
    assert validate_response(response(valid.replace('"guests"', '"admins"')), record)[0] is None
    assert validate_response(response(valid, "length"), record)[0] is None
    assert validate_response(response("[]"), record)[0] is None
    assert validate_response(response('{"status": "modified"'), record)[0] is None
