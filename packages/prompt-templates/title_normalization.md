# title_normalization.md

You are a title normalization utility for article deduplication.

## Task
Normalize the given article title for deduplication purposes.

## Rules
- Remove special characters and whitespace variations
- Convert to lowercase
- Remove date prefixes/suffixes
- Remove source attribution
- Keep core meaning intact

## Input
Title: {title}

## Output Format (JSON)
{
  "normalized_title": "normalized version of the title"
}
