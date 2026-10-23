"""Offline extraction evaluation against explicit, versioned ground truth."""
import argparse
import hashlib
import json
from pathlib import Path

from .extraction import SCHEMAS, comparison_value, rule_extract

DEFAULT_DATASET = Path(__file__).resolve().parent.parent / 'evaluations' / 'synthetic-v1.json'


def load_dataset(path):
    raw = Path(path).read_bytes()
    if len(raw) > 16 * 1024 * 1024:
        raise ValueError('Evaluation dataset exceeds 16 MiB')
    data = json.loads(raw)
    if (data.get('format') != 'lexflow-extraction-evaluation-v1' or not data.get('version')
            or type(data.get('synthetic')) is not bool or not data.get('cases')):
        raise ValueError('Provide a versioned dataset with an explicit synthetic flag and cases')
    identifiers = set()
    for case in data['cases']:
        schema = SCHEMAS.get(case.get('matter_type'))
        identifier = case.get('id')
        if (not isinstance(identifier, str) or not identifier or identifier in identifiers or not schema
                or not isinstance(case.get('text'), str) or len(case['text']) > 200_000
                or not isinstance(case.get('expected'), dict)):
            raise ValueError('Each case needs a unique ID, supported matter type, text and expected field map')
        identifiers.add(identifier)
        allowed = set(schema['required'] + schema['optional'])
        for field, values in case['expected'].items():
            if field not in allowed or not isinstance(values, list) or not values or any(not isinstance(v, str) or not v.strip() for v in values):
                raise ValueError('Expected fields must use supported keys and non-empty lists of literal values')
    return data, hashlib.sha256(raw).hexdigest()


def metrics(tp, fp, fn):
    precision = tp / (tp + fp) if tp + fp else None
    recall = tp / (tp + fn) if tp + fn else None
    return {'true_positive': tp, 'false_positive': fp, 'false_negative': fn,
            'precision': round(precision, 6) if precision is not None else None,
            'recall': round(recall, 6) if recall is not None else None,
            'f1': round(2 * tp / (2 * tp + fp + fn), 6) if 2 * tp + fp + fn else None}


def evaluate(path=DEFAULT_DATASET, extractor=rule_extract):
    dataset, digest = load_dataset(path)
    totals, by_type, results = [0, 0, 0], {}, []
    exact, expected_conflicts, found_conflicts, evidence, candidates = 0, 0, 0, 0, 0
    for case in dataset['cases']:
        actual = extractor(case['text'], case['matter_type'])
        candidates += len(actual)
        evidence += sum(bool(item.get('evidence', '').strip()) for item in actual)
        predicted = {(item['field_key'], comparison_value(item['field_key'], item['value'])) for item in actual}
        expected = {(field, comparison_value(field, value)) for field, values in case['expected'].items() for value in values}
        counts = [len(expected & predicted), len(predicted - expected), len(expected - predicted)]
        totals = [a + b for a, b in zip(totals, counts)]
        category = by_type.setdefault(case['matter_type'], [0, 0, 0])
        by_type[case['matter_type']] = [a + b for a, b in zip(category, counts)]
        exact += expected == predicted
        for field, values in case['expected'].items():
            normalized = {comparison_value(field, value) for value in values}
            if len(normalized) > 1:
                expected_conflicts += 1
                found_conflicts += normalized <= {value for key, value in predicted if key == field}
        results.append({'id': case['id'], 'matter_type': case['matter_type'], **metrics(*counts),
                        'exact_match': expected == predicted,
                        'missed_fields': sorted({field for field, _ in expected - predicted}),
                        'unexpected_fields': sorted({field for field, _ in predicted - expected})})
    return {'format': 'lexflow-extraction-report-v1', 'dataset_version': dataset['version'], 'dataset_sha256': digest,
            'synthetic': dataset['synthetic'], 'engine': 'offline explicit-label rules',
            'scope': 'Text-to-candidate extraction only. Does not evaluate OCR, external AI, legal correctness, reviewer decisions or office time savings.',
            'limitations': dataset.get('limitations', ''), 'cases': len(results), **metrics(*totals),
            'exact_documents': {'numerator': exact, 'denominator': len(results)},
            'conflict_fields_recalled': {'numerator': found_conflicts, 'denominator': expected_conflicts},
            'evidence_present': {'numerator': evidence, 'denominator': candidates},
            'by_matter_type': {key: metrics(*value) for key, value in sorted(by_type.items())}, 'results': results}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--dataset', type=Path, default=DEFAULT_DATASET)
    parser.add_argument('--output', type=Path)
    parser.add_argument('--min-f1', type=float, default=0.0, help='Fail if micro F1 is below this 0–1 threshold')
    args = parser.parse_args()
    if not 0 <= args.min_f1 <= 1:
        parser.error('--min-f1 must be between 0 and 1')
    report = evaluate(args.dataset)
    encoded = json.dumps(report, ensure_ascii=False, indent=2) + '\n'
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(encoded)
        print(json.dumps({key: report[key] for key in ('dataset_version', 'synthetic', 'cases', 'precision', 'recall', 'f1')}))
    else:
        print(encoded, end='')
    if report['f1'] is None or report['f1'] < args.min_f1:
        raise SystemExit(1)


if __name__ == '__main__':
    main()
