"""Elasticsearch index definitions and mappings."""

ENTITY_INDEX = "entities"
SECURITY_INDEX = "securities"

ENTITY_MAPPING = {
    "settings": {
        "number_of_shards": 1,
        "number_of_replicas": 0,
        "analysis": {
            "analyzer": {
                "autocomplete": {
                    "type": "custom",
                    "tokenizer": "standard",
                    "filter": ["lowercase", "edge_ngram_filter"],
                },
            },
            "filter": {
                "edge_ngram_filter": {
                    "type": "edge_ngram",
                    "min_gram": 2,
                    "max_gram": 20,
                },
            },
        },
    },
    "mappings": {
        "properties": {
            "entity_id": {"type": "keyword"},
            "legal_name": {
                "type": "text",
                "analyzer": "standard",
                "fields": {
                    "autocomplete": {
                        "type": "text",
                        "analyzer": "autocomplete",
                        "search_analyzer": "standard",
                    },
                    "keyword": {"type": "keyword"},
                },
            },
            "short_name": {
                "type": "text",
                "fields": {"keyword": {"type": "keyword"}},
            },
            "aliases": {"type": "text"},
            "entity_type": {"type": "keyword"},
            "status": {"type": "keyword"},
            "country": {"type": "keyword"},
            "gics_sector": {"type": "keyword"},
            "gics_industry": {"type": "keyword"},
            "identifiers": {
                "type": "nested",
                "properties": {
                    "type": {"type": "keyword"},
                    "value": {"type": "keyword"},
                },
            },
        },
    },
}

SECURITY_MAPPING = {
    "settings": {
        "number_of_shards": 1,
        "number_of_replicas": 0,
        "analysis": {
            "analyzer": {
                "autocomplete": {
                    "type": "custom",
                    "tokenizer": "standard",
                    "filter": ["lowercase", "edge_ngram_filter"],
                },
            },
            "filter": {
                "edge_ngram_filter": {
                    "type": "edge_ngram",
                    "min_gram": 2,
                    "max_gram": 20,
                },
            },
        },
    },
    "mappings": {
        "properties": {
            "security_id": {"type": "keyword"},
            "name": {
                "type": "text",
                "analyzer": "standard",
                "fields": {
                    "autocomplete": {
                        "type": "text",
                        "analyzer": "autocomplete",
                        "search_analyzer": "standard",
                    },
                    "keyword": {"type": "keyword"},
                },
            },
            "short_name": {"type": "text"},
            "ticker": {
                "type": "keyword",
                "fields": {
                    "autocomplete": {
                        "type": "text",
                        "analyzer": "autocomplete",
                        "search_analyzer": "standard",
                    },
                },
            },
            "isin": {"type": "keyword"},
            "cusip": {"type": "keyword"},
            "figi": {"type": "keyword"},
            "issuer_name": {"type": "text"},
            "issuer_entity_id": {"type": "keyword"},
            "asset_class": {"type": "keyword"},
            "security_type": {"type": "keyword"},
            "exchange": {"type": "keyword"},
            "status": {"type": "keyword"},
        },
    },
}
