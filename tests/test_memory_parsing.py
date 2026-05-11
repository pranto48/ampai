from backend.agent import _extract_explicit_memory_request, _normalize_memory_fact, _determine_memory_action


def test_extract_explicit_memory_request_plain_text():
    assert _extract_explicit_memory_request('save to memory: I prefer dark mode') == 'I prefer dark mode'


def test_extract_explicit_memory_request_quoted():
    assert _extract_explicit_memory_request('save to memory "My favorite color is blue"') == 'My favorite color is blue'


def test_memory_action_saved():
    fact = _normalize_memory_fact('I prefer coffee')
    assert _determine_memory_action(fact, persist_memory=True, require_memory_approval=False, allowed_memory_categories=['preferences']) == 'saved'


def test_memory_action_pending_approval():
    fact = _normalize_memory_fact('Remember I live in NYC')
    assert _determine_memory_action(fact, persist_memory=True, require_memory_approval=True, allowed_memory_categories=None) == 'pending_approval'


def test_memory_action_blocked_by_policy():
    fact = _normalize_memory_fact('Remember this detail')
    assert _determine_memory_action(fact, persist_memory=False, require_memory_approval=False, allowed_memory_categories=None) == 'blocked_by_policy'
