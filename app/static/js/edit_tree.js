window.jump_to_id = {
    tech_to_tact: {},
};

/*
    There are multiple levels referenced in this file. Tabs: There is the
    upper level of tabs and lower level of tabs. These tabs are for the
    tactics. By clicking on the tactic, the user is able to see all the
    associated technique answer for that tactic. The lower level tabs
    contain techniques that have subtechniques. By clicking on these, the
    user will see that technique's question and the subtechnique answers. If
    the techniques does not have subtechniques, then it will not appear in
    the tabs.

    The tactic_level referenced means that the item in the sidebar was clicked
    and is accessed when selecting a tactic from the first list of tabs. This
    level also only shows the question for the tactic and the answer for the
    technique. The technique_level field means that the item clicked is accessed
    within a technique. This means that the question for the selected technique
    and the answers for that technique's subtechniques will display.

    There are multiple levels for the tabs. Tab 1 refers to the first set of tabs
    (tactics) and tabs 2 refers to the second set (techniques that have subtechniques).

    There are 3 levelsl of content. The first content contains the tactic
    question at the top of the page. The second content contains the technique
    answers of the tactic. If the user clicks on a technique in the sidebar,
    the second content container will

*/
// function to open tab when clicking on the actual tab
function openTab(liObj, tab, level) {
    // ajax request ensures that each tab open gets fresh content
    $.ajax({
        type: "GET",
        url: `/edit/tree/api`,
        contentType: "application/json",
        dataType: "json",
        data: {
            index: tab,
            version: $("#versionSelect").val(),
            selected_content: "tree", // selects answer and questions for tactics and techniques
        },
        success: function (res) {
            $(`#content${level}`).empty();

            $(`#tabs${level}`).find(" > ul > .is-active").removeClass("is-active");
            $(`.menu-list > li > a`).removeClass("is-active");
            $(liObj).addClass("is-active");

            // indicates which tab level to manipulate
            // if the content is for the first tab (tactics), build out the page for tactic and regular techniques (TXXXX)
            // if the content is for the second level of tabs (techniques), build out inner tab container for technique question and its children
            if (level == 1) {
                $("#content1").append(buildTabs(tab, res));
                createTabContent(tab, res);
            } else {
                buildInnerContainer(tab, res);
            }
        },
    });
}

// function to open tab when clicking on a technique in the side bar
// very similar to function above with auto scrolling
function opentab_missing_content(liObj, tab, level) {
    let technique = tab.split(".")[1];
    let tactic = tab.split(".")[0];

    $.ajax({
        type: "GET",
        url: `/edit/tree/api`,
        contentType: "application/json",
        dataType: "json",
        data: {
            index: tactic,
            version: $("#versionSelect").val(),
            selected_content: "tree", // get the content for tactics and technqiues
        },
        success: function (res) {
            $(`#tabs1`).find(" > ul > .is-active").removeClass("is-active"); // remove the highlighting on all tabs
            $(`.menu-list > li > a`).removeClass("is-active"); // remove active from all items in sidebar
            $(`li[name='${tactic}']`).addClass("is-active"); // add active to the clicked on item in both the sidebar and the

            $(liObj).children().addClass("is-active");

            // content for the first tab
            // this means the technique (TXXXX) answer was clicked on
            // if the technique (TXXXX) question or subtech (TXXXX.XXX) was clicked on, then open the also open the second tab
            if (level == 1) {
                $(`#content1`).empty();
                $("#content1").append(buildTabs(tactic, res));

                createTabContent(`${tactic}`, res);

                // automatically scroll to the selected technique
                $([document.documentElement, document.body]).animate(
                    {
                        scrollTop: $(`#${technique}`).offset().top,
                    },
                    1000
                );
            } else {
                $.ajax({
                    type: "GET",
                    url: `/edit/tree/api`,
                    contentType: "application/json",
                    dataType: "json",
                    data: {
                        index: `${tactic}.${technique}`,
                        version: $("#versionSelect").val(),
                        selected_content: "tree",
                    },
                    success: function (res2) {
                        $(`#content1`).empty();
                        $("#content1").append(buildTabs(tactic, res));

                        // rebuild only the tactic question at the top of the page
                        createTabContent(`${tactic}`, { data: [], question: res.question });

                        $(`#tabs2`).find(" > ul > .is-active").removeClass("is-active");
                        $(`#content2`).empty();

                        $(`li[name='${technique}']`).addClass("is-active");

                        // build the inner tab container filled with the technique's question and subtechnique answers
                        buildInnerContainer(`${tactic}.${technique}`, res2);

                        // automatically scroll to the content
                        $([document.documentElement, document.body]).animate(
                            {
                                scrollTop: $(`#${tab.split(".").slice(1).join("\\.")}`).offset().top,
                            },
                            1000
                        );
                    },
                });
            }
        },
    });
}

// function to build an entire tab
function createTabContent(index, data) {
    // this is just the question at the top of the page
    let section_question = $(`<section class="section"><h1 class="title">Question Text</h1></section>`);
    let section_answers = buildSectionAnswer(data); // this builds the section with answers
    let content_div = $("#content1");
    //create the question editing box
    section_question.append(
        createEditBox(
            `${data.question.id} (${data.question.name})`,
            data.question.question_edit,
            data.question.question_view,
            "question"
        )
    );
    content_div.prepend(section_question);
    //if tabs should exist, add tabs
    if (index !== "start") {
        //build the lower container
        let inner_div = $(`<div id="content2"></div>`);
        inner_div.append(section_answers);
        content_div.append(inner_div);
    } else {
        content_div.append(section_answers);
    }
}

// function to build just the inner tab's content
function buildInnerContainer(index, data) {
    let div = $(`<div id="content3"></div>`);
    let section_answers = buildSectionAnswer(data);

    //if index is a subtechnique (used for when items in the sidebar are clicked)
    if (index.match(/TA[0-9]{4}\.T[0-9]{4}/)) {
        let section_question = $(`<section class="section"><h1 class="title">Question Text</h1></section>`);

        section_question.append(
            createEditBox(
                `${data.question.id} (${data.question.name})`,
                data.question.question_edit,
                data.question.question_view,
                "question",
                false
            )
        );
        $("#content2").append(section_question);

        section_answers.append(div);
        $("#content2").append(section_answers);
    } else {
        div.append(section_answers);
        $("#content2").append(div);
    }
}

// function to build the tabs - used for the second tab since the first one will not be changing
function buildTabs(index, data) {
    let sub_tab = $(`<div class="tabs is-centered" id="tabs2"></div>`);
    let ul = $("<ul></ul>");
    ul.append($(`<li name="base" class="is-active" onclick="openTab(this,'${index}',2)"><a>base</a></li>`));
    for (const item of data.data) {
        if (item.has_children) {
            let li = $(`<li name="${item.id}" onclick="openTab(this,'${index}.${item.id}',2)"><a>${item.id}</a></li>`);
            ul.append(li);
        }
        sub_tab.append(ul);
    }
    return sub_tab;
}

// function to build the answer section
// this can be subtechnique answers or technique answers - depending on which tab the user is at
function buildSectionAnswer(data) {
    let section_answers = $('<section class="section"><h1 class="title">Answer Text</h1></section>');
    for (const item of data.data) {
        let mismapping = false;
        if (/^T[0-9]{4}/.test(item.id)) {
            mismapping = true;
        }
        section_answers.append(
            createEditBox(`${item.id} (${item.name})`, item.answer_edit, item.answer_view, "answer", mismapping)
        );
    }
    return section_answers;
}

// function to build the editing and rendering box
function createEditBox(label, edit_text, view_text, type, mismap) {
    let mismap_element = "";
    if (mismap) {
        let index = label.split(" ")[0];
        let version = $("#versionSelect").val();
        let tactic = $("#tabs1 ul > li.is-active").attr("name");

        let mismapLinkParams = new URLSearchParams([
            ["version", version],
            ["tactic", tactic],
            ["index", index]
        ]).toString();
        mismap_element = $(`<a href="/edit/mismapping?${mismapLinkParams}">Edit Mismappings</a>`);
    }

    // ATT&CK identifier, can also be "start"
    let attack_id = label.split(" ")[0];
    let box;

    // start box cannot be edited - fixed text
    if (attack_id === "start") {
        box = $(`
        <div class="box">
            <h6 class="title is-6">${attack_id}</h6>
            <div class="columns">
                <div class="column">
                    <div id="${attack_id}-render" class="md-content">${view_text}</div>
                </div>
            </div>
        </div>
        `);
    }

    // others are editable
    else {
        box = $(`
        <div id='${attack_id}' class="box">
            <h6 class="title is-6">${label}</h6>
            <div class="columns">
                <div class="column">
                    <textarea
                        class="textarea" data-id="${attack_id}" data-type="${type}"
                        oninput="updateContent(this)">${edit_text}</textarea>
                </div>
                <div class="column">
                    <div id="${attack_id}-render" class="md-content">${view_text}</div>
                </div>
            </div>
        </div>
        `);
    }

    box.append(mismap_element);
    return box;
}

// function to update content on each key press
var updateContent = _.debounce(function (elem) {
    let textarea = $(elem);
    let data = {
        type: textarea.data("type"),
        id: textarea.data("id"),
        text: textarea.val(),
        version: $("#versionSelect").val(),
    };
    $.ajax({
        type: "POST",
        url: `/edit/tree/api`,
        dataType: "json",
        contentType: "application/json",
        data: JSON.stringify(data),
        success: function (res) {
            $(`[id="${textarea.data("id")}-render"]`).html(res.name);
            populateSidebar();
        },
    });
}, 200);

// function to build the missing techniques/subtechniques sidebar
function populateSidebar() {
    $.ajax({
        type: "GET",
        url: `/edit/tree/api`,
        dataType: "json",
        contentType: "application/json",
        data: {
            version: $("#versionSelect").val(),
            selected_content: "missing_content",
        },
        success: function (missing) {
            // Represents a list of chunks.
            // Each chunk represents a Tactic and a list of Techniques under it missing content.
            let missingChunks = missing.map((chunk) => ({
                tactic_id: chunk[0],
                tactic_name: chunk[1],
                techniques: chunk[2].map((tech_arr) => ({
                    tech_id: tech_arr[0],
                    tech_name: tech_arr[1],
                    level_type: tech_arr[2], // tactic_level -or- technique_level
                    level: tech_arr[3], // figure this out, it becomes opentab_missing_content(_, _, level)
                })),
            }));

            // Clear and re-populate sidebar menu.
            $("#missingContent").empty();
            for (const chunk of missingChunks) {
                // build techniques in group
                let missingTechRows = _.map(chunk.techniques, function (tech) {
                    return `
                    <li onclick="opentab_missing_content(this,'${chunk.tactic_id}.${tech.tech_id}',${tech.level})">
                        <a><span class="icon" style="color: blue;">
                            <i class="mdi mdi-18px mdi-chat-processing"></i>
                        </span> ${tech.tech_id} (${tech.tech_name})</a>
                    </li>`;
                });

                // form chunk and add
                let tacticChunk = $(`
                    <p name="${chunk.tactic_id}" class="menu-label">${chunk.tactic_id} (${chunk.tactic_name})<p>
                    <ul class="menu-list">
                        ${_.join(missingTechRows, "")}
                    </ul>
                `);
                $("#missingContent").append(tacticChunk);
            }
        },
    });
}

// page load -> populate TechID: (1st)TactID resolver
$(document).ready(function () {
    jumpToIDChangeVersion($("#versionSelect").val());

    // JumpToID input keyup callback: [Enter] -> do jump
    $("#editing-jump-to-id-input").keyup(function (event) {
        if (event.keyCode === 13) {
            jumpToIDBtnCallback();
        }
    });
});

// loads the tech->(1st)tact map for the version specified
function jumpToIDChangeVersion(version) {
    // clear current map and lock controls
    window.jump_to_id.tech_to_tact = {};
    $("#editing-jump-to-id-input").prop("disabled", true);
    $("#editing-jump-to-id-button").prop("disabled", true);

    // grab new tech->tact map
    $.ajax({
        url: `/api/techid_to_valid_tactid_map/${version}`,
        type: "GET",
        dataType: "json",
        success: function (techid_tactid_map) {
            // store and enable controls that use the map
            window.jump_to_id.tech_to_tact = techid_tactid_map;
            $("#editing-jump-to-id-input").prop("disabled", false);
            $("#editing-jump-to-id-button").prop("disabled", false);
        },
    });
}

// display warning in JumpToID
function setErrorJumpToIDStatus(content) {
    let statusSpan = $("#editing-jump-to-id-status");
    statusSpan.html(`<b>${content}</b>`);
    statusSpan.css("color", "red");
}

// display default help-text in JumpToID
function resetJumpToIDStatus() {
    let statusSpan = $("#editing-jump-to-id-status");
    statusSpan.css("color", "black");
    statusSpan.html("Tnnnn<u><b>.</b>nnn</u> or Tnnnn<u><b>/</b>nnn</u> allowed");
}

// JumpToID button callback
function jumpToIDBtnCallback() {
    let jumpInput = $("#editing-jump-to-id-input");
    let jumpButton = $("#editing-jump-to-id-button");
    let techID = jumpInput.val().trim().toUpperCase().replace("/", ".");

    // malformed tech ID
    if (techID.match(/^T[0-9]{4}(\.[0-9]{3})?$/) === null) {
        setErrorJumpToIDStatus("Invalid format entered");
        setTimeout(resetJumpToIDStatus, 2000);
        return;
    }
    // tech ID doesn't exist
    if (!(techID in window.jump_to_id.tech_to_tact)) {
        setErrorJumpToIDStatus("Tech ID doesn't exist");
        setTimeout(resetJumpToIDStatus, 2000);
        return;
    }

    // lock jump input and unlock in 2s
    jumpInput.prop("disabled", true);
    jumpButton.prop("disabled", true);
    setTimeout(function () {
        jumpInput.val("");
        jumpInput.prop("disabled", false);
        jumpButton.prop("disabled", false);
    }, 2000);

    // resolve Tact for request and Tech vs SubTech level
    let tactID = window.jump_to_id.tech_to_tact[techID];
    let contentLevel = techID.includes(".") ? 2 : 1;
    opentab_missing_content(null, `${tactID}.${techID}`, contentLevel);
}
