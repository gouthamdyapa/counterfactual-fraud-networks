#!/usr/bin/env python3
"""One frozen proof-illustration check, separate from the main validation suite."""
import argparse
import hashlib
import importlib.util
import itertools
import json
from pathlib import Path
import sys


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def literal_counts(events, root):
    pairs = 0
    triples = 0
    for a, b in itertools.permutations(events, 2):
        if a['target'] == b['source'] and a['time'] < b['time'] and b['target'] == root:
            pairs += 1
    for a, b, c in itertools.permutations(events, 3):
        if (a['target'] == b['source'] and b['target'] == c['source']
                and a['time'] < b['time'] < c['time'] and c['target'] == root):
            triples += 1
    return pairs, triples


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--solver-path', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    here = Path(__file__).resolve().parent
    protocol = json.loads((here / 'protocol.json').read_text())
    for name, expected in protocol['frozen_sha256'].items():
        assert sha(here / name) == expected, ('Frozen file changed', name)
    assert sha(args.solver_path) == protocol['solver_sha256']
    instance = json.loads((here / 'instance.json').read_text())
    expected = json.loads((here / 'expected.json').read_text())
    events = instance['events']
    optional = [e['id'] for e in events if e['status'] == 'optional']
    assert len(optional) == 6 and len(events) == 10
    baseline = literal_counts(events, instance['root'])
    assert list(baseline) == expected['baseline']
    table = {}
    contexts = {key: {} for key in expected['contexts']}
    examined = 0
    for bits in itertools.product((False, True), repeat=len(optional)):
        deleted = {eid for eid, choice in zip(optional, bits) if choice}
        kept = [e for e in events if e['id'] not in deleted]
        w2, w3 = literal_counts(kept, instance['root'])
        cost = sum(e['cost'] for e in events if e['id'] in deleted)
        examined += 1
        if w2 >= instance['min_w2']:
            key = (baseline[0] - w2, w3)
            table[key] = min(table.get(key, cost), cost)
        final = sorted(eid for eid in deleted if eid.startswith('C'))
        for name, spec in expected['contexts'].items():
            if final == spec['deleted_c']:
                assert w2 == 5
                contexts[name][str(w3)] = min(contexts[name].get(str(w3), cost), cost)
    assert examined == 64
    for name in contexts:
        assert contexts[name] == expected['contexts'][name]['minimum_cost_by_w3']
    loss5 = {str(w): cost for (loss, w), cost in table.items() if loss == 5}
    assert loss5 == expected['global_loss_5']

    spec = importlib.util.spec_from_file_location('illustration_candidate', args.solver_path)
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    candidate = module.solve_profiles(instance)
    got = {(row['loss'], row['w3']): row['total_cost'] for row in candidate['profiles']}
    assert got == table
    for row in candidate['profiles']:
        deleted = set(row['deleted_ids'])
        assert deleted <= set(optional)
        counts = literal_counts([e for e in events if e['id'] not in deleted], instance['root'])
        assert counts == (row['w2'], row['w3'])
        assert sum(e['cost'] for e in events if e['id'] in deleted) == row['total_cost']
    result = {
        'status': 'passed',
        'scope': 'One separately frozen ten-event explanatory instance; not added to the 375-history suite.',
        'legal_subsets_enumerated': examined,
        'baseline': list(baseline),
        'contexts': contexts,
        'global_loss_5': loss5,
        'all_admissible_profile_entries_checked': len(table),
        'all_returned_witnesses_checked': len(candidate['profiles']),
        'solver_sha256': sha(args.solver_path),
        'protocol_sha256': sha(here / 'protocol.json'),
        'candidate_result': candidate,
    }
    args.output.write_text(json.dumps(result, indent=2, sort_keys=True) + '\n')
    print(json.dumps({key: result[key] for key in ('status', 'legal_subsets_enumerated',
          'contexts', 'global_loss_5', 'all_admissible_profile_entries_checked')}, indent=2))


if __name__ == '__main__':
    main()
