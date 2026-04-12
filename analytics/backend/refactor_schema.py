import json
import re

with open('db_schema.json', 'r') as f:
    schema = json.load(f)

def clean_text(text):
    if not text:
        return text
    # Split by standard sentence terminators, keeping the terminator
    sentences = re.split(r'(?<=[.!?])\s+', text)
    cleaned = []
    for s in sentences:
        s_lower = s.lower()
        if any(kw in s_lower for kw in [
            'critical rule', 'critical join rule', 'default filter', 'always filter where',
            'critical warning', 'critical for historical queries', 'important:', 'always add where',
            'always join to franchises.sites_info', 'always join using both fbo_id and site_id'
        ]):
            continue
        cleaned.append(s)
    return " ".join(cleaned).strip()

for table in schema:
    table['purpose'] = clean_text(table.get('purpose', ''))
    
    for col in table.get('columns', []):
        col['description'] = clean_text(col.get('description', ''))
        
    for fk in table.get('foreign_keys', []):
        # Default all FKs to Many-to-One since they are defined on the Many side referencing the 1 side
        fk['cardinality'] = 'N:1'

with open('db_schema.json', 'w') as f:
    json.dump(schema, f, indent=2)

print("Schema refactored successfully.")
