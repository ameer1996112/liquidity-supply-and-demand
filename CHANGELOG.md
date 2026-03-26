# Changelog
## [1.0.1.0] - 2026-03-26

### Added
- **Visual Annotator Shadow Mode**: New `test_visual_annotator.py` script to run historical 5m/1H screenshots through Claude 3.5 Sonnet's Vision model against the 4-dimension grading rubric.
- **Multimodal LLM Payloads**: Extended `AnthropicClient` to natively support multimodal lists (images + text).
- **Tool Use Extraction**: Enforced strict JSON output using Anthropic's Tool Use API.
- **Auto Image Compression**: Added a Pillow-based utility to resize images > 5MB to comply with Anthropic limits.
