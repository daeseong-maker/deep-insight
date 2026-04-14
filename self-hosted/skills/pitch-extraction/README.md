# Pitch Extraction Skill

Automated metadata extraction from Korean pitch PDFs for the ShortFlow content registration system.

## Overview

This skill extracts 9 metadata fields from Korean pitch PDFs using a two-stage parsing strategy with LLM-based field extraction.

## Architecture

### Two-Stage PDF Parsing
1. **Stage 1**: opendataloader-pdf (free, local parsing)
2. **Stage 2**: Upstage Document Parse API (fallback for image-based PDFs)

### Field Extraction
- **Method**: LLM-based extraction using Claude Haiku via AWS Bedrock
- **Fields**: 9 metadata fields (title, logline, synopsis, characterDescription, episodes, runtime, genre, productionYear, productionStatus)

### Fallback Detection
Triggers Upstage API fallback when:
- Text length < 100 characters
- Korean character ratio < 10%
- Characters per page < 50

## File Structure

```
pitch-extraction/
├── scripts/
│   └── pitch_extractor.py    # Main implementation
├── SKILL.md                   # Skill definition
├── IMPLEMENTATION_STATUS.md   # Implementation status
└── README.md                  # This file
```

## Usage

```bash
# From self-hosted directory
uv run python main.py --user_query "기획안 PDF에서 메타데이터 추출해줘. 파일은 ./data/pitch/마피아킹_기획안_20260119.pdf"
```

The skill is automatically invoked when the user query mentions pitch extraction or PDF metadata extraction.

## Environment Variables

Required in `self-hosted/.env`:
- `UPSTAGE_API_KEY`: Upstage Document Parse API key
- `AWS_REGION`: AWS region for Bedrock (default: us-west-2)

## Output Format

```json
{
  "extractedAt": "2026-04-14T04:45:52.416839Z",
  "parsingMethod": "opendataloader" | "upstage_dp" | "error",
  "fields": {
    "title": "string | null",
    "logline": "string | null",
    "synopsis": "string | null",
    "characterDescription": "string | null",
    "episodes": "number | null",
    "runtime": "number | null",
    "genre": "string[] | null",
    "productionYear": "number | null",
    "productionStatus": "string | null"
  },
  "confidence": {
    "title": "high" | "medium" | "low" | "inferred",
    // ... for all 9 fields
  },
  "missingFields": ["field1", "field2", ...]
}
```

## Test Results

### Text-based PDF (마피아킹_기획안_20260119.pdf)
- **Parser**: opendataloader-pdf
- **Extracted**: 7/9 fields
- **Missing**: productionYear, productionStatus

### Image-based PDF (사랑의코딩법_소개서.pdf)
- **Parser**: Upstage Document Parse API (fallback)
- **Extracted**: 6/9 fields (5279 chars from 121 elements)
- **Missing**: episodes, runtime, productionYear

## Implementation Status

✅ Task 8.1: PitchExtractor class with extract() method
✅ Task 8.2: Error handling and graceful degradation

See [IMPLEMENTATION_STATUS.md](./IMPLEMENTATION_STATUS.md) for detailed status.
