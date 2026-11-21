from pathlib import Path
import re

skill = Path(__file__).resolve().parents[1] / 'SKILL.md'
s = skill.read_text(encoding='utf-8')
assert s.startswith('---\n')
header = s.split('---', 2)[1]
for key in ('name:', 'description:', 'version:'):
    assert key in header, key
for phrase in ('ingen merge', 'ingen produktionsdeploy', 'Henrik', 'Perplexity Computer',
               'PASS', 'FAIL', 'BLOCKED', '0 SEK', 'rollback', 'Godkännandegräns'):
    assert phrase.lower() in s.lower(), phrase
assert len(re.findall(r'^### ', s, flags=re.MULTILINE)) >= 5
assert (skill.parent / 'references/ACCEPTANCE.md').exists()
print('PASS: skill format och skyddsregler kontrollerade')
