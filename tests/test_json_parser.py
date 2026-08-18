import pytest
import json
from config.json_parser import parse_json_response


def test_parse_clean_json():
    data = {"status": "VALID", "score": 95, "items": ["a", "b"]}
    raw_str = json.dumps(data)
    result = parse_json_response(raw_str)
    assert result == data


def test_parse_markdown_codeblock_json():
    raw_str = """Here is the extracted invoice:
```json
{
  "vendor_name": "PT Maju Terus",
  "total": 500000.0
}
```
Thank you."""
    result = parse_json_response(raw_str)
    assert result["vendor_name"] == "PT Maju Terus"
    assert result["total"] == 500000.0


def test_parse_generic_codeblock_json():
    raw_str = """
```
{
  "has_stamp": true,
  "has_signature": false
}
```
"""
    result = parse_json_response(raw_str)
    assert result["has_stamp"] is True
    assert result["has_signature"] is False


def test_parse_json_with_thinking_preamble():
    raw_str = """Thinking Process:
1. Vendor found: ABC
2. Total matches.

{"result": "SUCCESS", "tax_valid": true}
"""
    result = parse_json_response(raw_str)
    assert result["result"] == "SUCCESS"
    assert result["tax_valid"] is True


def test_parse_empty_content_raises_error():
    with pytest.raises(ValueError, match="empty content"):
        parse_json_response("")


def test_parse_invalid_json_raises_decode_error():
    with pytest.raises(json.JSONDecodeError):
        parse_json_response("This is not valid JSON { broken: 123 ")
