// Namespaced global vars
// prettier-ignore
window.question = {
    answer_data: [],
    answer_view: [],
    search_str: "",
    index: "",
    version: "",
    markjs_opts: {
        accuracy: {
            value: "exactly",
            limiters: [
                ",", ".", "(", ")", "-", "_", "/", "\\", "?", "!", "'", '"', "|", "+", "@", "[", "]", "{", "}", "<",
                ">", "#", "$", "%", "^", "`", "&", "*", ":", ";", "~"
            ],
        },
    },
};

// On ready
$(document).ready(function () {
    $(window).on("resize", debounced_platformMatchHeight); // matches platform panel even after content reflow

    let version_v_strip = Math.floor(parseFloat($("#versionSelect").val().replace("v", "")));
    if (version_v_strip >= 10) {
        $("#dataSourceSelect").show();
    } else {
        $("#dataSourceSelect").hide();
    }

    initAnswerCards();
});

// ---------------------------------------------------------------------------------------------------------------------

var debounced_platformMatchHeight = _.debounce(platformMatchHeight, 150);

function platformMatchHeight() {
    // aligns platform filter column to height of answer cards

    var navBar = $(".navbarSection");
    var navTop = navBar.position().top;
    var navHeight = navBar.outerHeight(true);

    var ansHeader = $("#answerListHeader");
    var ansHeaderBottom = ansHeader.position().top + ansHeader.outerHeight(true);

    $("#filterSpacing").height(ansHeaderBottom - (navTop + navHeight));
}

function initAnswerCards() {
    // Lock input until data is ready
    $("#platform-selection input").prop("disabled", true);
    $("#questionSearch").prop("disabled", true);

    // Update page filters to match stored filter state
    syncFilters("platform");
    syncFilters("data_source");

    // GET the answer card data via API for the question specified by the <div>
    var ans_list = $("#answer-list");
    question.index = ans_list.data("index");
    question.version = ans_list.data("version");
    $.ajax({
        url: "/api/answers/",
        type: "GET",
        data: {
            index: question.index,
            tactic: ans_list.data("tactic"),
            version: question.version,
        },
        dataType: "json",
        success: function (answers) {
            // Add default score to entries so they maintain original display order unless scored by MiniSearch; save
            for (let i = 0; i < answers.length; i++) {
                answers[i].score = -i;
                answers[i].label = `${answers[i].name} (${answers[i].id})`;
                answers[i].highlights = {};
                answers[i].content_text = $(answers[i].content).text();
            }
            question.answer_data = answers;
            question.answer_view = answers;

            // Clear search string
            question.search_str = "";

            // Filter, sort, paginate, and display the content
            questionRender();

            // Data is loaded -> free inputs
            $("#platform-selection input").prop("disabled", false);
            $("#questionSearch").prop("disabled", false);

            platformMatchHeight();
        },
    });
}

function templateAndHighlightAnswer(ans_data) {
    // Render card with template
    var ans_card = $(answerTemplate(ans_data));

    // Highlight label and content sections for matched terms
    if ("label" in ans_data.highlights)
        ans_card.find(".ans-label").mark(ans_data.highlights.label, question.markjs_opts);
    if ("content_text" in ans_data.highlights)
        ans_card.find(".ans-content").mark(ans_data.highlights.content_text, question.markjs_opts);

    return ans_card;
}

function gotoAnswerPage(page_num) {
    var PER_PAGE = 5; // Configurable
    var answers_view = question.answer_view;

    // Start page has content changed in-place: gotoAnswerPage(1) is called on page load
    if (question.index === "start") {
        // Holds all answer cards
        var grid = $("<div></div>");

        // For all answer cards we have
        for (var i = 0; i < answers_view.length; i++) {
            // Create a new row for each 3 cards, add to master holder
            if (i % 3 === 0) {
                var row = $('<div class="columns"></div>');
                grid.append(row);
            }

            // Wrap answer card with column div
            var piece = $('<div class="column is-one-third tactic-column"></div>');
            piece.append(templateAndHighlightAnswer(answers_view[i]));

            // Add chunk to current row
            grid.children().last().append(piece);
        }

        $("#answer-list").empty();
        $("#answer-list").append(grid);

        return;
    }

    // [Answer Cards] Get answer data, trim to current view, clear cards, repopulate
    var current_answers = _.slice(answers_view, PER_PAGE * (page_num - 1), PER_PAGE * page_num);
    var answer_list = $("#answer-list");
    answer_list.empty();
    _.forEach(current_answers, function (ans_data) {
        answer_list.append(templateAndHighlightAnswer(ans_data));
    });

    // [Page Nav Bar] Calc total # of pages, fill list with page buttons, clear current, repopulate
    var total_pages = Math.ceil(answers_view.length / PER_PAGE);
    var page_list = $("<ul>", { class: "pagination-list" });
    for (var cur_page = 1; cur_page <= total_pages; cur_page++) {
        page_list.append($(pageButtonTemplate(cur_page, cur_page === page_num)));
    }
    var answer_nav = $("#answer-nav");
    answer_nav.empty();
    answer_nav.append(page_list);
}

function questionRenderFrontendSearch(answer_data) {
    // Terms are space-seperated chunks of text
    var terms = _.filter(question.search_str.toLowerCase().split(" "), function (t) {
        return t !== "";
    });

    // Excludes are terms that start with -, get base exclusion terms, keep non-empty
    var excludes = _.remove(terms, function (t) {
        return _.startsWith(t, "-");
    });
    excludes = _.map(excludes, function (t) {
        return t.slice(1);
    });
    excludes = _.filter(excludes, function (t) {
        return t !== "";
    });

    var new_search = _.join(terms, " "); // Make new search string from positive associations

    // Conduct fuzzy (+prefix) search against the "label"/"content_text" fields of the answer cards
    var miniSearch = new MiniSearch({ fields: ["label", "content_text"], storeFields: ["label", "content_text"] });
    miniSearch.addAll(answer_data);
    var results = miniSearch.search(new_search, {
        prefix: (term) => term.length > 2,
        fuzzy: (term) => (term.length > 2 ? 0.15 : null),

        // Remove any results containing the excluded terms
        filter: function (result) {
            for (const exclusion of excludes) {
                if (
                    result.label.toLowerCase().includes(exclusion) ||
                    result.content_text.toLowerCase().includes(exclusion)
                )
                    return false;
            }
            return true;
        },
    });

    // For all search results
    _.forEach(results, function (entry) {
        // Restructure match data that MiniSearch returns
        // Instead of specifying terms and where they exist ...
        //     We specify places and what terms exist in them
        var field_to_terms = {};
        for (const [term, fields] of Object.entries(entry.match)) {
            _.forEach(fields, function (field) {
                if (field in field_to_terms) field_to_terms[field].push(term);
                else field_to_terms[field] = [term];
            });
        }

        // Overwrite default score with the actual search score
        var matched_answer = _.filter(answer_data, function (a) {
            return a.id === entry.id;
        })[0];

        matched_answer.score = entry.score;
        matched_answer.highlights = field_to_terms;
    });

    answer_data = _.sortBy(answer_data, [
        function (c) {
            return -c.score;
        },
    ]); // Highest scores first

    return answer_data;
}

function questionRenderBackendSearchRequest(answer_data) {
    // form URL params for request
    let ansList = $("#answer-list");
    let params = [
        ["version", ansList.data("version")],
        ["index", ansList.data("index")],
        ["tactic_context", ansList.data("tactic")],
        ["search", question.search_str],
    ];
    _.forEach(getChkSelections("platform"), function (platform) {
        params.push(["platforms", platform]);
    });
    _.forEach(getChkSelections("data_source"), function (data_source) {
        params.push(["data_sources", data_source]);
    });
    let paramStr = new URLSearchParams(params).toString();

    // request the user's search
    $.ajax({
        type: "GET",
        url: `/search/answer_cards?${paramStr}`,
        dataType: "json",
        success: function (searchResponse) {
            // transform cards using response from server
            questionRenderBackendSearchResponse(answer_data, searchResponse);
        },
    });
}

function questionRenderBackendSearchResponse(answer_data, searchResponse) {
    // search successful
    if ("results" in searchResponse) {
        // there were results -> set status and re-order / highlight cards
        if (Object.keys(searchResponse.results).length > 0) {
            $("#ans-search-status").html(`<b>Search Used:</b> ${searchResponse.status}`);

            // update answer cards with search result scores
            _.forEach(answer_data, function (answerEntry) {
                if (answerEntry.id in searchResponse.results) {
                    let result = searchResponse.results[answerEntry.id];

                    answerEntry.score = result.score;
                    answerEntry.highlights.label = result.display_matches;
                    answerEntry.highlights.content_text = result.display_matches;
                    answerEntry.highlights.additional = result.additional_matches;
                }
            });

            // score answer cards score descending
            answer_data = _.sortBy(answer_data, [
                function (c) {
                    return -c.score;
                },
            ]);
        }

        // no matches found -> just set status
        else {
            $("#ans-search-status").html(`
                <b>Search Used:</b> ${searchResponse.status}<br>
                <span style="color: red;"><i>No matches - cards will stay in their default order</i></span>
            `);
        }

        question.answer_view = answer_data;
        gotoAnswerPage(1);
    }

    // bad search query
    else {
        // display error status in red
        $("#ans-search-status").html(`<span style="color: red;">${searchResponse.status}</span>`);

        // don't re-order / highlight answers
        question.answer_view = answer_data;
        gotoAnswerPage(1);
    }
}

function questionRender() {
    // clone data for transform, get filters of cards to remove
    var answer_data = JSON.parse(JSON.stringify(question.answer_data));
    var platform_selections = getChkSelections("platform");
    var data_source_selections = getChkSelections("data_source");

    // front-end handles removing filtered-out cards
    if (platform_selections.length > 0) {
        // Remove all answers that share no platforms with selected
        _.remove(answer_data, function (answer) {
            var answer_platforms = _.split(answer.platforms, ",");
            if (_.intersection(platform_selections, answer_platforms).length === 0) {
                return true;
            }
        });
    }
    if (data_source_selections.length > 0) {
        // Remove all answers that share no platforms with selected
        _.remove(answer_data, function (answer) {
            var data_source_platforms = _.split(answer.data_sources, ",");
            if (_.intersection(data_source_selections, data_source_platforms).length === 0) {
                return true;
            }
        });
    }

    // no search -> set view, goto 1
    if (question.search_str.length === 0) {
        question.answer_view = answer_data;
        gotoAnswerPage(1);
        return;
    }

    // Tactic->Techs, Tech->Subs use backend as to search more content
    if ($("#answer-list").data("index") === "start") {
        question.answer_view = questionRenderFrontendSearch(answer_data);
        gotoAnswerPage(1);
    } else {
        questionRenderBackendSearchRequest(answer_data);
    }
}

function answerTemplate(answer) {
    // form additional matches section if present and 1+ matches exist
    let additionalMatches = "";
    if ("additional" in answer.highlights && answer.highlights.additional.length !== 0) {
        let matchLocations;

        // card is SubTechnique itself or has no subs - don't mention subs
        if (answer.id.includes(".") || answer.num === 0) {
            matchLocations = "Description";
        }
        // Technique with subs - mention away
        else {
            matchLocations = "Description / SubTechniques";
        }

        additionalMatches = `<p class="ans-additional-matches"><i>
        <u>Matches in ${matchLocations}:</u> ${_.join(answer.highlights.additional, ", ")}
        </i><p>`;
    }

    return `<div class="card answer box is-flex-grow-1" data-tech-id="${answer.id}">
        <div class="columns">
            <div class="column">
                <a target="_blank" rel="noreferrer noopener" class="ans-url" href="${answer.url}">
                    <span class="ans-label">${answer.name} (${answer.id})</span>
                    <span class="icon is-small">
                        <i class="mdi mdi-link"></i>
                    </span>
                </a>
            </div>
            <div class="column is-narrow count-column">
                <a>
                    <p class="ans-num">
                        <span class="icon is-small equal-height">
                            <i class="mdi mdi-file-tree-outline"></i>
                        </span>
                        ${answer.num}
                    </p>
                </a>
            </div>
        </div>

        <div class="card-content">
            <a class="ans-path" href="${answer.path}">
                <!-- <p class="is-size-5 ans-text">answer.text</p> -->
                <div class="md-content ans-content is-size-5">
                    ${answer.content}
                </div>
                ${additionalMatches}
            </a>
        </div>
    </div>`;
}

function pageButtonTemplate(page_num, is_current) {
    if (is_current) {
        return `<button class="pagination-link is-current">${page_num}</button>`;
    } else {
        return `<button class="pagination-link" onclick="gotoAnswerPage(${page_num})">${page_num}</button>`;
    }
}

// ---------------------------------------------------------------------------------------------------------------------
// Page interaction callbacks: filtering & search

var questionUpdateSearchString = _.debounce(function (search_str) {
    // clear status (for backend, not present for front-end)
    if ($("#ans-search-status").length) {
        $("#ans-search-status").html("");
    }

    // run search
    question.search_str = search_str;
    questionRender();
}, 200);

var questionClearPlatforms = _.debounce(function () {
    clearFilters("platform");
    questionRender();
}, 50);

var questionUpdatePlatforms = _.debounce(function (checkbox) {
    updateFilters("platform", checkbox);
    questionRender();
}, 50);

var questionClearDataSources = _.debounce(function () {
    clearFilters("data_source");
    questionRender();
}, 50);

var questionUpdateDataSources = _.debounce(function (checkbox) {
    updateFilters("data_source", checkbox);
    questionRender();
}, 50);
