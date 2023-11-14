import re


def transform_description_citations(item):
    desc = item["description"]

    for markdown_citation, source_name in re.findall(r"(\(Citation: *(.+?) *\))", desc):

        cite_num, ext_reference = next(
            (
                (index, ref)
                for index, ref in enumerate(item["external_references"])
                if ref["source_name"].strip() == source_name
            ),
            (None, None)
        )

        # not found -> clear it
        if cite_num is None:
            desc = desc.replace(markdown_citation, "")

        # found
        else:
            url = ext_reference.get("url")

            # url-less -> clear it
            if url is None:
                desc = desc.replace(markdown_citation, "")

            # has url -> link it
            else:
                safe_source_name = source_name.replace('"', '\\"')
                html_citation = f'<sup><a href="{url}" title="{safe_source_name}">[{cite_num}]</a></sup>'
                desc = desc.replace(markdown_citation, html_citation)

    return desc
