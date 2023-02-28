from app.models import db

from app.utils.db.util import messaged_timer


@messaged_timer("Creating index for full Technique search")
def add_technique_search_index():
    # remove and remake ts_vec and index it
    # 1. imm_unaccent(technique.tech_description)
    #    unaccent - useful for 'doppelganging'
    # 2. regexp_replace(__1__, '<\/?(sup|a|code)[^>]*>', '', 'gi')
    #    remove the only 3 tags we expect in descriptions
    # 3. regexp_replace(__2__, '\[[0-9]{1,2}\]', '', 'gi')
    #    remove citation marks [N-NN]
    # 4. regexp_replace(__3__, '\[([^\]]+)\]\([^\)]+\)', '\1', 'gi')
    #    replace MD links [Text](URL) -> Text
    # 5. regexp_replace(__4__, '[^a-z0-9 ]+', ' ', 'gi')
    #    all non A-z0-9/space -> ' '
    db.session.execute(
        r"""
    DROP INDEX IF EXISTS tech_ts_index;
    ALTER TABLE technique DROP COLUMN IF EXISTS tech_ts;

    ALTER TABLE technique ADD COLUMN tech_ts tsvector
        GENERATED ALWAYS AS
            (setweight(to_tsvector('english_nostop',
            imm_unaccent(technique.full_tech_name)), 'B') ||
            setweight(to_tsvector('english_nostop',
            regexp_replace(technique.tech_id ||
            ' ' || substr(technique.tech_id, 2), '[^a-z0-9 ]+', ' ', 'gi')), 'A') ||
            setweight(to_tsvector('english_nostop',
            regexp_replace(regexp_replace(regexp_replace(regexp_replace(imm_unaccent(technique.tech_description),
            '<\/?(sup|a|code)[^>]*>', '', 'gi'), '\[[0-9]{1,2}\]', '', 'gi'),
            '\[([^\]]+)\]\([^\)]+\)', '\1', 'gi'), '[^a-z0-9 ]', ' ', 'gi')), 'D')) STORED;
    CREATE INDEX tech_ts_index ON technique USING gist(tech_ts);
    """.strip()
    )
    db.session.commit()


@messaged_timer("Add Facilities for Answer Card Search")
def add_technique_answer_search_facilities():
    # adds and indexes the column "tech_ans_ts" which is a generated searchable TSvec for Technique answers
    # 1. coalesce(technique.tech_answer, '')
    #    replace nulls with empty strings
    # 2. imm_unaccent(__1__)
    #    remove accenting - useful for 'doppelganging'
    # 3. regexp_replace(__2__, '[^a-z0-9 ]+', ' ', 'gi')
    #    keep only alphanumerics
    # 4. to_tsvector('english_nostop', __3__)
    #    make the text-search vector itself

    # add function "tsvector_agg" that allows aggregating an array TSvecs
    #    given a Technique: this makes a single vector from:
    #    - its answer card content
    #    - its description
    #    - the answer cards of its sub-techs
    #    - the descriptions of its sub-techs
    db.session.execute(
        r"""
    DROP INDEX IF EXISTS tech_ans_ts_index;
    ALTER TABLE technique DROP COLUMN IF EXISTS tech_ans_ts;
    ALTER TABLE technique ADD COLUMN tech_ans_ts tsvector
        GENERATED ALWAYS AS
            (
        to_tsvector('english_nostop',
            regexp_replace(
                imm_unaccent(coalesce(technique.tech_answer, '')),
            '[^a-z0-9 ]+', ' ', 'gi'))
            ) STORED;
    CREATE INDEX tech_ans_ts_index ON technique USING gist(tech_ans_ts);

    DROP FUNCTION IF EXISTS tsvector_agg;
    CREATE FUNCTION tsvector_agg(tsvector[]) RETURNS tsvector AS $$
    DECLARE
        tsvector_item tsvector;
        tsvec_accumulator tsvector := '';
    BEGIN
        FOREACH tsvector_item IN ARRAY $1
        LOOP
            tsvec_accumulator := tsvec_accumulator || tsvector_item;
        END LOOP;
        RETURN tsvec_accumulator;
    END;
    $$ LANGUAGE plpgsql IMMUTABLE;
    """.strip()
    )
    db.session.commit()
