"""Génération seule dans un processus borné, sans outil ni confirmation."""
import json
import sys

from .app import Ollama


def main():
    try:
        data = json.load(sys.stdin)
        client = Ollama(data['address'], data['timeout'])
        chunks, size = [], 0
        for chunk in client.chat(data['model'], data['messages'], structured=True):
            size += len(chunk)
            if size > 15000:
                raise ValueError('Proposition limitée à 15 000 caractères.')
            chunks.append(chunk)
        proposal = json.loads(''.join(chunks))
        print(json.dumps(proposal, ensure_ascii=False))
        return 0
    except Exception as error:
        print(str(error), file=sys.stderr)
        return 1


if __name__ == '__main__':
    raise SystemExit(main())
