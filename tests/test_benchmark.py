import json

import pytest

from lexflow.benchmark import DEFAULT_DATASET, evaluate, load_dataset


def test_versioned_synthetic_benchmark_reports_known_limits():
    report = evaluate()
    assert report['synthetic'] is True and report['cases'] == 28
    assert report['precision'] == 1.0 and report['recall'] < 1.0
    assert report['f1'] >= .95
    assert report['conflict_fields_recalled'] == {'numerator': 5, 'denominator': 5}
    misses = [row['id'] for row in report['results'] if not row['exact_match']]
    assert misses == ['property-ocr-label-loss']
    assert set(report['by_matter_type']) == {'property_purchase','inheritance','company_formation','general'}
    assert 'OCR' in report['scope']


def test_evaluator_counts_missing_and_unexpected_values_and_omits_private_text(tmp_path):
    source = tmp_path/'dataset.json'
    source.write_text(json.dumps({'format':'lexflow-extraction-evaluation-v1','version':'private-test','synthetic':False,
        'cases':[{'id':'case-1','matter_type':'general','text':'private source text','expected':{'client_name':['Private Example']}}]}))
    def wrong(*args):
        return [{'field_key':'client_name','value':'Incorrect Person','evidence':'private evidence'}]
    report = evaluate(source, extractor=wrong)
    assert report['true_positive'] == 0 and report['false_positive'] == 1 and report['false_negative'] == 1
    assert report['f1'] == 0 and report['synthetic'] is False
    assert 'Private Example' not in json.dumps(report) and 'private source text' not in json.dumps(report)
    assert report['results'][0]['missed_fields'] == ['client_name']


@pytest.mark.parametrize('change', ['duplicate', 'schema', 'value', 'synthetic'])
def test_evaluation_rejects_ambiguous_ground_truth(tmp_path, change):
    data = json.loads(DEFAULT_DATASET.read_text())
    if change == 'duplicate': data['cases'].append(data['cases'][0])
    if change == 'schema': data['cases'][0]['matter_type'] = 'unknown'
    if change == 'value': data['cases'][0]['expected']['buyer_name'] = 'a string instead of list'
    if change == 'synthetic': data.pop('synthetic')
    path = tmp_path/'invalid.json'
    path.write_text(json.dumps(data))
    with pytest.raises(ValueError):
        load_dataset(path)
