"""Evidence-labeled exposure diagrams and reviewable assessment presentation."""
import json
import re
from .core import require


def exposure_graph(graph):
    nodes=graph['nodes'];edges=graph['edges'];ids={n['id'] for n in nodes}
    require(len(ids)==len(nodes) and all(re.fullmatch(r'[A-Za-z][A-Za-z0-9_]*',i) for i in ids),'Graph node identity invalid')
    rows=['flowchart LR']
    for n in nodes:
        require(n.get('label') and n.get('kind') in ('actor','condition','service','asset','control'),'Graph node scope missing')
        rows.append('    '+n['id']+'['+json.dumps(n['label'])+']')
    for edge in edges:
        require(edge['from'] in ids and edge['to'] in ids,'Graph edge has no node')
        require(edge['state'] in ('observed','source_supported','proposed','unresolved'),'Graph evidence state missing')
        require(edge.get('evidence') or edge['state'] in ('proposed','unresolved'),'Confirmed edge has no evidence')
        arrow='-->' if edge['state'] in ('observed','source_supported') else '-.->'
        label=edge['state']+': '+edge['label']
        rows.append('    '+edge['from']+' '+arrow+'|'+json.dumps(label)+'| '+edge['to'])
    return {'mermaid':'\n'.join(rows)+'\n','edge_provenance':edges,'limits':'A source-supported arrow is not a runtime observation. Dotted edges remain proposed/unresolved.'}
