"""Functional checks for the context-bound two-stage protocol."""
from pathlib import Path
from variant_check import check_functional, implementation, write_rows
if __name__ == '__main__':
    results = check_functional('two-stage-context-bound', implementation('protocol'))
    write_rows(Path(__file__).with_name('two_stage_functional.csv'), results)
    print(len(results), 'cases;', sum(r['reconstruction_subsets'] for r in results), 'subset reconstructions')
