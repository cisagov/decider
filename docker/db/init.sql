-- Used for top-right Technique search - WORD_SIMILARITY()
CREATE EXTENSION IF NOT EXISTS pg_trgm WITH SCHEMA public;

-- Fake mutable unaccent function for full search
CREATE EXTENSION IF NOT EXISTS unaccent WITH SCHEMA public;
DROP FUNCTION IF EXISTS imm_unaccent;
CREATE FUNCTION imm_unaccent(text) RETURNS text AS $$
BEGIN
    RETURN unaccent($1);
END;
$$ LANGUAGE plpgsql IMMUTABLE;

-- Dictionary for Full Search, doesn't remove stop words "a", "the", ..
DROP TEXT SEARCH CONFIGURATION IF EXISTS english_nostop;
DROP TEXT SEARCH DICTIONARY IF EXISTS english_stem_nostop;
CREATE TEXT SEARCH DICTIONARY english_stem_nostop (template = snowball, language = english);
CREATE TEXT SEARCH CONFIGURATION english_nostop (copy = english);
ALTER TEXT SEARCH CONFIGURATION english_nostop ALTER MAPPING REPLACE english_stem WITH english_stem_nostop;
