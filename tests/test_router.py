import pytest
from app.router import choose_route, hybrid_generate

def test_auto_prefers_local_for_short_tasks():
    order, reason = choose_route('Explain sorting')
    assert order == ['local', 'cloud']
    assert 'fallback' in reason

def test_explicit_route_does_not_fallback():
    assert choose_route('Explain sorting', 'cloud')[0] == ['cloud']

def test_complex_code_cloud_first():
    order, _ = choose_route('Write Python code ' + 'implement robust tests ' * 40)
    assert order[0] == 'cloud'

def test_invalid_route():
    with pytest.raises(ValueError):
        choose_route('hi', 'unknown')

@pytest.mark.asyncio
async def test_mock_is_explicit():
    result = await hybrid_generate('Explain caching', 'mock')
    assert result['route'] == 'mock'
    assert result['provider'] == 'mock'
