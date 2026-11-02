# task

Quotes the cold-chain backbone for every project in a quote book.

    PYTHONPATH=src python3 -m task --book DIR --out DIR

The book files, the quote and the documents written to the output directory
are described in /app/ci/api_contract.md. The unit tests run with

    PYTHONPATH=src python3 -m unittest discover -s tests -v
