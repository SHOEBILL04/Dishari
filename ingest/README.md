# Ingest Module

## Purpose
The ingest module handles data ingestion from past BCS preliminary question sources (PDFs, scans, text files).

## Responsibilities
- **Parsing & Extraction**: Extract question stems, 4 answer options, correct indices, and metadata.
- **Normalization**: Enforce Unicode Bangla NFC normalization (clean non-standard characters, remove legacy Bijoy artifacts).
- **Deduplication**: Detect repeated or duplicate questions across past papers using normalized text and vector embeddings.
- **Verification Staging**: Load ingested questions into the database with `status = 'draft'` or `status = 'verified'` pending validation.
