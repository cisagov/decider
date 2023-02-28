import re


def transform_description_citations(item):
    description = item["description"]
    counter = 1
    for markdown_citation in re.findall(r"\(Citation: [^()]+\)", description):
        citation = re.search(r"\(Citation: (.+)\)", markdown_citation).group(1)
        external_ref = next(
            filter(
                lambda e: e["source_name"] == citation,
                item["external_references"],
            ),
            None,
        )
        if external_ref:

            # ----------------------------------------------------------
            # only used in blurb formation compatibility
            # url always present for Techniques
            if "url" not in external_ref:
                description = description.replace(markdown_citation, "")
                continue
            # ----------------------------------------------------------

            url = external_ref["url"]
            try:
                html_citation = f'<sup><a href="{url}">[{counter}]</a></sup>'
                description = description.replace(markdown_citation, html_citation)
            except AttributeError:
                print(markdown_citation)
                print(external_ref)
            counter += 1
    return description
