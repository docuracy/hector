# HECTOR: Historical Economic Commodities: Terminologies, Ontologies, & Rates

## Test Persistent URLs using a Browser

- **Root**: [https://w3id.org/hector/](https://w3id.org/hector/) - User Interface (searchable index)
- **About**: [https://w3id.org/hector/about/](https://w3id.org/hector/about/)
- **Context**: [https://w3id.org/hector/context](https://w3id.org/hector/context)
- **Commodity Example**: [https://w3id.org/hector/commodity/saffron](https://w3id.org/hector/commodity/saffron) - pre-loaded in the User Interface
- **Unit Example**: [https://w3id.org/hector/unit/mass/pound](https://w3id.org/hector/unit/mass/pound) - pre-loaded in the User Interface

## Programmatic JSON Request Examples

### Commodity

To request JSON-LD for a commodity (e.g., saffron) using `curl`:

```bash
#!/bin/bash

COMMODITY="saffron"
curl -H "Accept: application/ld+json" \
     "https://w3id.org/hector/commodity/$COMMODITY"

```

### Unit

To request JSON-LD for a unit (e.g., pound) using curl:

```bash
#!/bin/bash
UNIT="mass/pound"
curl -H "Accept: application/ld+json" \
     "https://w3id.org/hector/unit/$UNIT"

```
