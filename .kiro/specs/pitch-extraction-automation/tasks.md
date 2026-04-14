# Implementation Plan: Pitch Extraction Automation

## Overview

This implementation plan creates a two-stage PDF parsing system that extracts 9 metadata fields from Korean pitch PDFs. The system uses opendataloader-pdf as the primary parser with Upstage Document Parse API as a fallback, implements pattern-based field extraction with Korean language support, assigns confidence levels to extracted fields, and integrates with the Deep Insight skill system and Spring Boot backend.

**Implementation Language**: Python

**Key Components**:
- PDF_Parser: Two-stage parsing orchestration
- Fallback_Detector: Quality threshold validation
- Field_Extractor: 9-field extraction with regex patterns
- Metadata_Validator: Confidence level assignment
- Pitch_Extractor: Pipeline coordination and JSON output

## Tasks

- [x] 1. Set up project structure and dependencies
  - Create `self-hosted/skills/pitch-extraction/` directory structure
  - Create `pitch_extractor.py` as main module
  - Create `requirements.txt` with dependencies: opendataloader, requests, hypothesis (for testing)
  - Update `self-hosted/Dockerfile` to install opendataloader and dependencies
  - Add UPSTAGE_API_KEY to `self-hosted/.env.example`
  - _Requirements: 1.1, 10.1_

- [x] 2. Implement PDF_Parser component with two-stage parsing
  - [x] 2.1 Create PDFParser class with parse() method
    - Implement ParseResult dataclass (success, text, method, error, page_count)
    - Implement Stage 1: opendataloader-pdf parsing using load_pdf()
    - Implement Stage 2: Upstage Document Parse API fallback with base64 encoding
    - Handle exceptions and trigger fallback on opendataloader-pdf failure
    - Return parsing method ("opendataloader" or "upstage_dp") in result
    - _Requirements: 1.1, 1.6, 1.7, 6.1_

  - [ ]* 2.2 Write property test for PDF_Parser
    - **Property 1: Fallback Detection Thresholds**
    - **Validates: Requirements 1.3, 1.4, 1.5, 7.2**
    - Generate random texts with varying lengths (0-200 chars), Korean/non-Korean mixes (0-100%), and page counts (1-20)
    - Verify fallback triggers correctly for each threshold condition

  - [ ]* 2.3 Write unit tests for PDF_Parser
    - Test opendataloader-pdf with standard text-based PDF
    - Test Upstage API with image-heavy PDF
    - Test error handling for corrupted PDF
    - Test parsing method tracking
    - _Requirements: 1.1, 1.6, 1.7_

- [x] 3. Implement Fallback_Detector component
  - [x] 3.1 Create FallbackDetector class with should_fallback() method
    - Implement text length threshold check (< 100 characters)
    - Implement Korean character ratio check (< 10% using Unicode U+AC00 to U+D7A3)
    - Implement characters per page threshold check (< 50)
    - Return True if any threshold is not met
    - _Requirements: 1.3, 1.4, 1.5, 5.4, 7.2_

  - [ ]* 3.2 Write property test for Fallback_Detector
    - **Property 10: Korean Character Ratio Calculation**
    - **Validates: Requirements 5.4**
    - Generate random texts with known Korean character counts
    - Verify ratio calculation is correct (Korean chars / total chars)

  - [ ]* 3.3 Write unit tests for Fallback_Detector
    - Test threshold detection for text length < 100
    - Test threshold detection for Korean ratio < 10%
    - Test threshold detection for chars/page < 50
    - Test Korean character counting (U+AC00 to U+D7A3)
    - _Requirements: 1.3, 1.4, 1.5, 5.4_

- [x] 4. Checkpoint - Ensure parsing components work correctly
  - Ensure all tests pass, ask the user if questions arise.

- [x] 5. Implement Field_Extractor component for metadata extraction
  - [x] 5.1 Create FieldExtractor class with extract_fields() method
    - Implement FieldSet dataclass with all 9 fields (title, logline, synopsis, characterDescription, episodes, runtime, genre, productionYear, productionStatus)
    - Implement title extraction using regex pattern for "제목:"/"작품명:"/"Title:" labels
    - Implement logline extraction using regex pattern for "로그라인:"/"한줄 소개:" labels
    - Implement synopsis extraction using regex pattern for "시놉시스:"/"줄거리:"/"스토리:" sections
    - Implement characterDescription extraction using regex pattern for "등장인물:"/"캐릭터:"/"인물 소개:" sections
    - _Requirements: 2.1, 2.2, 2.4, 2.5, 5.2_

  - [x] 5.2 Implement numeric field extraction
    - Implement episodes extraction using regex pattern "총 N화"/"N부작"/"N회" and convert to integer
    - Implement runtime extraction using regex pattern "회당 N분"/"편당 N분" and convert to integer
    - _Requirements: 2.6, 2.7_

  - [x] 5.3 Implement genre and year extraction
    - Implement genre extraction using regex pattern for "장르:"/"Genre:" labels
    - Implement genre splitting for "/" and "," delimiters into array
    - Implement productionYear extraction using 4-digit year pattern (2020-2030 range)
    - _Requirements: 2.8, 2.9_

  - [x] 5.4 Implement productionStatus extraction and normalization
    - Implement productionStatus extraction using keyword matching ("기획중"/"제작중"/"완성"/"완료"/"방영완료")
    - Implement normalization: "완료"/"방영완료" → "완성"
    - _Requirements: 2.10, 2.11_

  - [x] 5.5 Implement logline inference and null handling
    - Implement logline inference from synopsis first sentence (max 40 characters) when logline is not found
    - Mark inferred logline with extraction_metadata flag
    - Return null for fields that cannot be extracted
    - _Requirements: 2.3, 2.12, 6.3_

  - [ ]* 5.6 Write property tests for Field_Extractor
    - **Property 2: Field Extraction from Labeled Sections**
    - **Validates: Requirements 2.1, 2.2, 2.4, 2.5, 2.8, 2.10, 5.2**
    - Generate random texts with field labels at various positions
    - Verify extraction works regardless of surrounding text

  - [ ]* 5.7 Write property test for numeric field extraction
    - **Property 3: Numeric Field Extraction and Type Conversion**
    - **Validates: Requirements 2.6, 2.7**
    - Generate random texts with numeric patterns ("총 N화", "회당 N분")
    - Verify integer conversion is correct

  - [ ]* 5.8 Write property test for logline inference
    - **Property 4: Logline Inference from Synopsis**
    - **Validates: Requirements 2.3**
    - Generate random synopsis texts without explicit logline
    - Verify logline is generated from first sentence (max 40 chars)
    - Verify "inferred" flag is set

  - [ ]* 5.9 Write property test for productionStatus normalization
    - **Property 5: ProductionStatus Normalization**
    - **Validates: Requirements 2.11**
    - Generate random status keywords including "완료" and "방영완료"
    - Verify normalization to "완성"

  - [ ]* 5.10 Write property test for null handling
    - **Property 6: Null Handling for Missing Fields**
    - **Validates: Requirements 2.12, 6.3**
    - Generate random texts missing various fields
    - Verify null is returned and field continues processing

  - [ ]* 5.11 Write property test for genre splitting
    - **Property 11: Genre Splitting**
    - **Validates: Requirements 2.8**
    - Generate random genre strings with "/" and "," delimiters
    - Verify splitting produces correct array

  - [ ]* 5.12 Write property test for year range validation
    - **Property 12: Year Range Validation**
    - **Validates: Requirements 2.9**
    - Generate random texts with years inside and outside 2020-2030
    - Verify only valid years are extracted

  - [ ]* 5.13 Write unit tests for Field_Extractor
    - Test title extraction with "제목:" label
    - Test logline extraction with "로그라인:" label
    - Test logline inference from synopsis
    - Test synopsis extraction with multi-paragraph text
    - Test characterDescription extraction
    - Test episodes extraction with "총 30화" pattern
    - Test runtime extraction with "회당 3분" pattern
    - Test genre splitting for "로맨스/코미디"
    - Test productionYear extraction with 4-digit year
    - Test productionStatus normalization ("완료" → "완성")
    - Test null handling for missing fields
    - _Requirements: 2.1-2.12_

- [x] 6. Checkpoint - Ensure field extraction works correctly
  - Ensure all tests pass, ask the user if questions arise.

- [x] 7. Implement Metadata_Validator component
  - [x] 7.1 Create MetadataValidator class with validate() method
    - Implement confidence level assignment logic
    - Assign "high" confidence for explicit label matching
    - Assign "medium" confidence for pattern matching without labels
    - Assign "low" confidence for uncertain matching
    - Assign "inferred" confidence for generated fields
    - Return confidence dictionary for all 9 fields
    - _Requirements: 3.1, 3.2, 3.3, 3.4, 3.5_

  - [ ]* 7.2 Write property test for Metadata_Validator
    - **Property 7: Confidence Level Assignment**
    - **Validates: Requirements 3.1, 3.2, 3.3, 3.4, 3.5**
    - Generate random extraction results with different methods
    - Verify confidence levels match extraction method

  - [ ]* 7.3 Write unit tests for Metadata_Validator
    - Test "high" confidence for label-matched fields
    - Test "medium" confidence for pattern-matched fields
    - Test "low" confidence for uncertain extractions
    - Test "inferred" confidence for generated fields
    - _Requirements: 3.1, 3.2, 3.3, 3.4, 3.5_

- [-] 8. Implement Pitch_Extractor pipeline coordinator
  - [x] 8.1 Create PitchExtractor class with extract() method
    - Implement ExtractionResult dataclass (extractedAt, parsingMethod, fields, confidence, missingFields)
    - Orchestrate pipeline: parse PDF → detect fallback → extract fields → validate → format output
    - Generate ISO 8601 timestamp for extractedAt
    - Populate missingFields array with null field names
    - Preserve Korean text (UTF-8 encoding, Unicode U+AC00 to U+D7A3) without translation
    - _Requirements: 4.1, 4.2, 4.3, 4.4, 4.5, 4.6, 5.1, 5.3_

  - [x] 8.2 Implement error handling and graceful degradation
    - Handle parsing failures and return partial results
    - Continue processing when individual fields fail
    - Log all errors to CloudWatch (parsing attempts, fallback triggers, extraction failures)
    - Return error response when both parsers fail
    - _Requirements: 6.1, 6.2, 6.3, 6.4, 6.5_

  - [ ]* 8.3 Write property test for JSON output completeness
    - **Property 8: JSON Output Completeness**
    - **Validates: Requirements 4.1, 4.2, 4.3, 4.4, 4.5**
    - Generate random extraction results
    - Verify all required JSON fields are present (extractedAt, parsingMethod, fields, confidence, missingFields)
    - Verify ISO 8601 timestamp format

  - [ ]* 8.4 Write property test for Korean text preservation
    - **Property 9: Korean Text Preservation**
    - **Validates: Requirements 4.6, 5.1, 5.3**
    - Generate random Korean texts (Unicode U+AC00 to U+D7A3)
    - Extract and verify text matches original (round-trip property)
    - Verify UTF-8 encoding is preserved

  - [ ]* 8.5 Write unit tests for Pitch_Extractor
    - Test full pipeline with sample PDF
    - Test JSON output format
    - Test missing_fields array population
    - Test timestamp generation (ISO 8601)
    - _Requirements: 4.1, 4.2, 4.3, 4.4, 4.5_

- [x] 9. Checkpoint - Ensure pipeline coordination works correctly
  - Ensure all tests pass, ask the user if questions arise.

- [ ] 10. Implement CloudWatch observability
  - [ ] 10.1 Add CloudWatch logging to all components
    - Log parsing attempts with method and latency
    - Log fallback triggers with reason and thresholds
    - Log extraction results with field counts and confidence levels
    - Log errors with context (field name, error message)
    - Log Upstage API usage for credit tracking
    - _Requirements: 6.5, 7.3, 9.1, 9.2, 9.3, 9.4_

  - [ ] 10.2 Implement CloudWatch metrics emission
    - Emit PitchExtraction.ParseLatency metric (histogram)
    - Emit PitchExtraction.ExtractionSuccess metric (count)
    - Emit PitchExtraction.FallbackRate metric (percentage)
    - Emit PitchExtraction.UpstageCredits metric (count)
    - _Requirements: 9.5_

- [ ] 11. Update SKILL.md with implementation details
  - [ ] 11.1 Update SKILL.md with Python implementation examples
    - Add import statements and module structure
    - Add usage examples with sample code
    - Add error handling examples
    - Document expected input/output formats
    - _Requirements: 10.1, 10.2, 10.3, 10.4, 10.5_

- [ ] 12. Create integration with Spring Boot backend
  - [ ] 12.1 Implement JSON serialization for Spring Boot consumption
    - Create to_json() method in ExtractionResult
    - Ensure field names match Spring Boot expectations (camelCase)
    - Ensure genre field is serialized as JSON array
    - Ensure confidence and missingFields are serialized correctly
    - _Requirements: 8.1, 8.2, 8.3, 8.4_

  - [ ]* 12.2 Write integration tests for Spring Boot endpoint
    - Test POST /internal/drafts endpoint with sample extraction result
    - Test RDS save operation (mock or test database)
    - Test JSON field mapping
    - Test error response handling
    - _Requirements: 8.1, 8.2, 8.3, 8.4_

- [ ] 13. Create test data and sample PDFs
  - [ ] 13.1 Create sample PDFs for testing
    - Create `self-hosted/tests/fixtures/standard-pitch.pdf` (text-based, all 9 fields)
    - Create `self-hosted/tests/fixtures/image-heavy-pitch.pdf` (scanned, requires OCR)
    - Create `self-hosted/tests/fixtures/partial-pitch.pdf` (missing some fields)
    - Create `self-hosted/tests/fixtures/corrupted-pitch.pdf` (invalid PDF)
    - _Requirements: 1.1, 1.6, 6.1, 6.4_

  - [ ] 13.2 Create expected output JSON files
    - Create `self-hosted/tests/fixtures/standard-pitch-expected.json`
    - Create `self-hosted/tests/fixtures/image-heavy-pitch-expected.json`
    - Create `self-hosted/tests/fixtures/partial-pitch-expected.json`
    - _Requirements: 4.1, 4.2, 4.3, 4.4, 4.5_

  - [ ]* 13.3 Write end-to-end integration tests
    - Test full pipeline with standard-pitch.pdf
    - Test fallback with image-heavy-pitch.pdf
    - Test partial extraction with partial-pitch.pdf
    - Test error handling with corrupted-pitch.pdf
    - Verify extraction completes within 10 seconds
    - _Requirements: 1.1, 1.6, 6.1, 6.2, 6.3, 6.4_

- [ ] 14. Update Docker configuration for local development
  - [ ] 14.1 Update self-hosted/Dockerfile
    - Add opendataloader installation
    - Add requests library installation
    - Add hypothesis library installation (for testing)
    - Copy skills directory to /app/skills
    - _Requirements: 10.1_

  - [ ] 14.2 Update self-hosted/.env
    - Add UPSTAGE_API_KEY environment variable
    - Add SKILL_DIRS=/app/skills environment variable
    - Add LOG_LEVEL=INFO environment variable
    - _Requirements: 1.6, 6.5_

  - [ ] 14.3 Create docker-compose.yml for local testing
    - Configure agentcore service with environment variables
    - Mount skills directory as volume
    - Expose port 8000
    - _Requirements: 10.1_

- [ ] 15. Checkpoint - Ensure local development environment works
  - Ensure all tests pass, ask the user if questions arise.

- [ ] 16. Prepare AWS deployment configuration
  - [ ] 16.1 Update managed-agentcore/Dockerfile
    - Add opendataloader installation
    - Add requests library installation
    - Bundle skills directory in Docker image
    - _Requirements: 10.1_

  - [ ] 16.2 Create ECS task definition updates
    - Add UPSTAGE_API_KEY from AWS Secrets Manager
    - Add CloudWatch log configuration
    - Add environment variables (SKILL_DIRS, LOG_LEVEL)
    - _Requirements: 1.6, 6.5, 9.1_

  - [ ] 16.3 Document AWS Secrets Manager setup
    - Document how to store Upstage API key in Secrets Manager
    - Document IAM role permissions for ECS task
    - Document key rotation policy (90 days)
    - _Requirements: 1.6_

- [ ] 17. Create monitoring and alerting configuration
  - [ ] 17.1 Create CloudWatch dashboard
    - Add widget for extraction requests per hour
    - Add widget for success rate by parsing method
    - Add widget for average confidence levels by field
    - Add widget for missing fields frequency distribution
    - _Requirements: 9.1, 9.2, 9.3, 9.4, 9.5_

  - [ ] 17.2 Create CloudWatch alarms
    - Create alarm for extraction success rate < 90%
    - Create alarm for Upstage fallback rate > 50%
    - Create alarm for average latency > 15 seconds
    - Create alarm for error rate > 5%
    - _Requirements: 9.1, 9.2, 9.3, 9.4, 9.5_

- [ ] 18. Final checkpoint - Ensure all components are integrated
  - Ensure all tests pass, ask the user if questions arise.

## Notes

- Tasks marked with `*` are optional and can be skipped for faster MVP
- Each task references specific requirements for traceability
- Checkpoints ensure incremental validation at key milestones
- Property tests validate universal correctness properties (12 properties total)
- Unit tests validate specific examples and edge cases
- Integration tests validate end-to-end workflows
- Implementation uses Python as specified in the design document
- Local development in self-hosted/ directory, AWS deployment in managed-agentcore/ directory
- Skills location: self-hosted/skills/pitch-extraction/
- Test location: self-hosted/tests/
