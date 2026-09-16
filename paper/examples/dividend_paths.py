"""Run hand-constructed illustrative candidates; no LLM or benchmark claims.
Run from repository root: .venv/bin/python paper/examples/dividend_paths.py
"""
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
from src.kg.online_kg import OnlineKG
from src.kg.schema import Triple, Provenance
from src.execution.sandbox import SandboxExecutor
from src.evaluation.evaluator import PathEvaluator
from src.planning.planner import ReasoningPath, PathStep


def main():
    kg = OnlineKG()
    edges = [
        ('e1', 'March 31', '2002_dividend', '0.450', 'table', 'T1'),
        ('e2', 'Acme', 'declared_dividend', '0.455', 'text', 'P1'),
        ('e3', 'March 31', '2002_high', '26.50', 'table', 'T1'),
    ]
    for _, h, r, t, kind, source in edges:
        kg.add_triple(Triple(h, r, t, Provenance(kind, source)))
    candidates = []
    specifications = [
        ('A', '2002_dividend', '(float(b)-float(a))/float(a)*100',
         ['Read earlier dividend', 'Read new dividend', 'Compute percentage increase']),
        ('B', '2002_dividend', '(float(a)-float(b))/float(a)*100',
         ['Read earlier dividend', 'Read new dividend', 'Reverse subtraction']),
        ('C', '2002_high', '(float(b)-float(a))/float(a)*100',
         ['Read high price as old value', 'Read new dividend', 'Compute percentage change']),
    ]
    for pid, relation, formula, goals in specifications:
        code = f'a = kg.get_neighbors(\n    "March 31", "{relation}")[0]\nb = kg.get_neighbors(\n    "Acme", "declared_dividend")[0]\nresult = {formula}\n'
        path = ReasoningPath(pid, [PathStep(i+1,g) for i,g in enumerate(goals)])
        candidates.append((path, code, SandboxExecutor().run(code, kg)))
    scored = PathEvaluator().evaluate_all(candidates)
    payload = {'kind': 'constructed illustration; not an LLM prediction',
               'question': 'What is the percentage increase from the March dividend to the newly declared dividend?',
               'edges': edges, 'candidates': []}
    for item in scored:
        assert item.exec_result.success
        assert len(item.exec_result.evidence) == 2
        payload['candidates'].append({'path': item.path.path_id,
            'steps': [s.goal for s in item.path.steps], 'code': item.code,
            'output': item.exec_result.value, 'score': item.score,
            'evidence': [e.__dict__ for e in item.exec_result.evidence]})
    assert abs(scored[0].exec_result.value - 1.1111111111111112) < 1e-10
    assert len({round(s.score, 8) for s in scored}) == 1
    output = Path(__file__).with_name('dividend_paths.json')
    output.write_text(json.dumps(payload, indent=2) + '\n')
    for c in payload['candidates']:
        print(c['path'], 'output=', c['output'], 'score=', c['score'])


if __name__ == '__main__':
    main()
