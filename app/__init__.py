"""ZoneWise: a location-aware assistant for Delhi planning law.

A user clicks a point on a map of Delhi and asks a question. ZoneWise works out which
planning zones contain that point, retrieves only the clauses that apply there, and
answers with a citation on every sentence, or declines when no clause supports an
answer.

The modules, in the order the data moves through them:

  config      paths and settings, read once from .env
  extract     source PDFs  ->  one text record per page            (scripts/02)
  cleaning    raw page text ->  clean lines that remember their page
  chunking    clean lines   ->  clause-sized chunks with citations (scripts/03)
  tagging     chunks        ->  which planning-zone topics each is about (scripts/04)
  indexing    chunks        ->  a Chroma vector index and a BM25 index (scripts/05)
  spatial     a point       ->  which zones contain it
  retrieval   a question    ->  the best chunks, dense + keyword, fused
  location    a point       ->  changes what retrieval returns: exclude, expand, boost
  llm         the one door to the Anthropic API, plus a fake client for tests
  answer      a question and a point -> a cited answer, or an honest refusal
  geocode     a place name  ->  coordinates, via Nominatim
  agent       a question with a place in it -> tools, then a cited answer
  api         all of the above over HTTP, and the built frontend at /

See docs/ARCHITECTURE.md for the same thing with diagrams, and DECISIONS.md for why
each piece works the way it does.
"""
