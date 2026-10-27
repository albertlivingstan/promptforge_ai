from app.core import STRATEGIES, analyze, optimize, evaluate, classify

def test_analysis():
    a = analyze('Explain AI')
    assert a['clarity'] < 100
    assert a['missing']

def test_all_strategies():
    for s in STRATEGIES:
        p = optimize('Explain transformers', s)
        assert 'Explain transformers' in p
        assert len(p) > 50

def test_classifier():
    assert classify('Write a Python function') == 'coding'

def test_evaluation():
    m = evaluate('## Python sorting\n- Sort a list', 'Explain Python sorting', 'Python sorting')
    assert 0 <= m['heuristic_score'] <= 100
    assert 'reference_keyword_recall' in m
