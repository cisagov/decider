//Mismapping

$(document).ready(function () {
    const urlParams = new URLSearchParams(window.location.search);

    // initialize all the dropdowns
    mismappingInit();

    // if the url contains version, index, and tactic
    // this is primarily used in the success page that redirects the user to the mismapping page
    // this also works if someone were to share the mismappings link
    if (urlParams.get("version") && urlParams.get("index") && urlParams.get("tactic")) {
        let tactic = urlParams.get("tactic");
        let index = urlParams.get("index");

        let observerConfig = {
            attributes: true,
            childList: true,
            characterData: true,
        };

        buildSidebar([urlParams.get("tactic")]);

        const sidebar_target = $("#sideBar").get(0);

        // observer to wait for the sidebar to finish loading
        let sidebar_observer = new MutationObserver((_, observer) => {
            let item = $(`div[name="${tactic}"] a[name="${index}"]`);
            preFillForm(item);
            observer.disconnect();
        });
        sidebar_observer.observe(sidebar_target, observerConfig);
    } else {
        buildSidebar();
    }
});

// function to build the dropdowns and store in sessionstorage
function mismappingInit() {
    let techniques = [];
    $.ajax({
        type: "GET",
        url: "/api/techniques",
        dataType: "json",
        data: {
            fields: ["technique_id", "technique_name"],
            version: $("#versionSelect").val(),
        },
        success: function (res) {
            res.unshift({
                technique_name: "N/A", // None (N/A)
                technique_id: "None",
                uid: undefined,
            });
            techniques = _.map(res, function (val, ind) {
                let v = val;
                v.id = ind;
                return val;
            });

            // allows us to quickly retrieve the list of techniques without having to do another query
            sessionStorage.setItem("mismappingTechniques", JSON.stringify(techniques));

            renderMismapDropdown(techniques, ".mismappingDropdownOriginal");
            renderMismapDropdown(techniques, ".mismappingDropdownCorrected");
        },
    });
}

// function to build the dropdowns
function renderMismapDropdown(arr, id) {
    $(id).empty(); // id the the class of the dropdown or can be the dropdown object itself
    let i = 0;
    if (
        (typeof id === "object" && id.attr("class").match(/mismappingDropdownOriginal/)) ||
        (typeof id == "string" && id.match(/^\.mismappingDropdownOriginal$/))
    ) {
        if (arr.length > 0 && arr[0].technique_name.includes("N/A")) {
            i = 1; // skip the first technique item because the first item is N/A
            // N/A should not show in the original
        }
    }

    $(id).append(buildDropdownItem(arr[i], "dropdown-item-selected"));
    i++;

    for (; i < arr.length; i++) {
        $(id).append(buildDropdownItem(arr[i]));
    }
}

// builds the individual item in the dropdown
function buildDropdownItem(technique, selected = "") {
    let technique_id = technique.technique_id;
    let technique_name = technique.technique_name;

    let a = $(`<a class="dropdown-item ${selected}" ></a>`);

    a.html(`${technique_id} (${technique_name})`);
    a.data("technique_id", technique_id);
    a.attr("href", "javascript:void(0);");

    // onclick, select this element and set the original/corrected fields properly
    a.click(function (_e) {
        let input = $(this).parentsUntil(".dropdown-container").find(" > .dropdown-trigger > .field > p > input");
        input.val(`${technique_id} (${technique_name})`);
        $(this).closest(".dropdown-menu").hide();
    });

    return a;
}

// function to search the dropdown for a technique
function mismappingSearch(element, phrase) {
    let techniques = JSON.parse(sessionStorage.getItem("mismappingTechniques"));

    // if nothing has been entered in the field
    if (phrase.length == 0) {
        renderMismapDropdown(
            techniques,
            $(element).parentsUntil(".dropdown-container").find(" > .dropdown-menu > .dropdown-content")
        );
    } else {
        let mismapSearch = new MiniSearch({
            fields: ["technique_name", "technique_id"],
            storeFields: ["technique_name", "technique_id"],
        });
        mismapSearch.addAll(techniques);

        // use minisearch
        let results = mismapSearch.search(phrase, {
            fuzzy: 0.25,
            prefix: true,
        });

        // if there are results, rerender th dropdown, otherwise do not render
        if (results.length > 0) {
            renderMismapDropdown(
                results,
                $(element).parentsUntil(".dropdown-container").find(" > .dropdown-menu > .dropdown-content")
            );
        }
    }
}

// function for the user to navigate the dropdowns
function mismappingNavigate(element, event) {
    let dropdown = $(element).parentsUntil(".dropdown-container").find(".dropdown-content");
    if (event.key === "Escape") {
        $(element).blur();
    } else if (_.includes(["ArrowUp", "ArrowDown", "Enter"], event.key)) {
        let selection = $($(dropdown.children(".dropdown-item-selected")[0]));

        // select element if enter key pressed
        if (event.key === "Enter") {
            selection[0].click();
        } else {
            event.preventDefault();

            let items = dropdown.children(".dropdown-item");
            let index = $(items).index(selection);

            // scroll the list up
            if (event.key == "ArrowUp") {
                if (index > 0) {
                    selection.removeClass("dropdown-item-selected");
                    let next = $(items[index - 1]);
                    next.addClass("dropdown-item-selected");

                    dropdown.parent().scrollTop(next.offset().top - dropdown.offset().top + dropdown.scrollTop());
                }
            }
            // scroll the list down
            else if (event.key == "ArrowDown") {
                if (index < items.length - 1) {
                    selection.removeClass("dropdown-item-selected");
                    let next = $(items[index + 1]);
                    next.addClass("dropdown-item-selected");

                    dropdown.parent().scrollTop(next.offset().top - dropdown.offset().top + dropdown.scrollTop());
                }
            }
        }
    }
}

// function to save the mismapping to the server
function mismappingSave(element) {
    let forms = $(element).closest(".card").find("input, textarea");
    let id = $(element).data("id");
    let data = {};
    let ret = false;
    if (id !== undefined && id !== null) {
        data["id"] = id;
    }

    let storageTechniques = JSON.parse(sessionStorage.getItem("mismappingTechniques"));
    let listTechIDNames = _.map(storageTechniques, function (t) {
        return `${t.technique_id} (${t.technique_name})`;
    });

    // iterate through the fields in a single form and pull out the info we need
    forms.each(function () {
        let field = $(this).data("field");

        // validate seletions of original->corrected fields of mismap
        if (field === "original" || field === "corrected") {
            let val = $(this).val();

            // original must be defined as a valid "Tech ID (Tech Name)" from the dropdown
            if (field === "original") {
                if (val.length === 0 || !listTechIDNames.includes(val)) {
                    showToast("Original Technique must be a valid selection from the dropdown.", "is-danger");
                    ret = true;
                    return false;
                }
            }

            // corrected must be defined as "None (N/A)" or as a valid "Tech ID (Tech Name)" from the dropdown
            else {
                // field === "corrected"
                if (val.length === 0 || (val !== "None (N/A)" && !listTechIDNames.includes(val))) {
                    showToast("Corrected Technique must be a valid selection from the dropdown.", "is-danger");
                    ret = true;
                    return false;
                }
            }

            data[field] = _.escape($(this).val().split(" ")[0]);
        } else {
            data[$(this).data("field")] = _.escape($(this).val());
        }
    });

    // if the fields are valid, send the request to the server
    if (!ret) {
        $.ajax({
            type: "POST",
            url: "/edit/mismapping",
            contentType: "application/json",
            dataType: "json",
            data: JSON.stringify(data),
            success: function (res) {
                showToast("Successfully saved mismapping");

                // if we are able to successfully save the mismapping and the button pressed was submit
                if (element.name === "submit") {
                    let corrected = _.escape($("#edit-corrected").val());
                    if (corrected === null || corrected === undefined || corrected === "") corrected = "None (N/A)";
                    $("#mismappingsContainer").append(
                        buildMismappingForm(
                            _.escape($("#edit-original").val()),
                            corrected,
                            _.escape(data["context"]),
                            _.escape(data["rationale"]),
                            res.uid
                        )
                    );
                    renderMismapDropdown(storageTechniques, ".mismappingDropdownOriginal");
                    renderMismapDropdown(storageTechniques, ".mismappingDropdownCorrected");
                }
            },
        });
    }
}

// function to clear out the fields of the mismapping
function mismappingReset(element) {
    $(element)
        .closest(".card")
        .find("input, textarea")
        .each(function () {
            if ($(this).data("field") != "original") $(this).val("");
        });
}

// function to delete hte mismapping
function mismappingDelete(element) {
    $.ajax({
        type: "DELETE",
        url: "/edit/mismapping",
        contentType: "application/json",
        dataType: "json",
        data: JSON.stringify({ id: $(element).data("id") }),
        success: function (_res) {
            showToast(`Successfully deleted mismapping`);
            $(element).parentsUntil(".mismappingEdit").parent().remove();
        },
    });
}

// opens up the tactic if clicked on
function toggleSubMenu(element) {
    $(element).parent().next().toggle();
}

// function to fill the form with techniques if one is clicked in the sidebar
function preFillForm(element) {
    $.ajax({
        type: "GET",
        url: "/api/mismappings",
        dataType: "json",
        data: {
            technique: $(element).attr("name"),
            version: $("#versionSelect").val(),
        },
        success: function (res) {
            $("#mismappingsContainer").empty();
            for (const mismap of res) {
                let original = mismap.original;
                let corrected = mismap.corrected;

                // if corrected is left empty, just fill in with N/A
                corrected =
                    corrected === null || corrected === undefined
                        ? "None (N/A)"
                        : `${corrected.technique_id} (${corrected.technique_name})`;
                $("#mismappingsContainer").append(
                    buildMismappingForm(
                        `${original.technique_id} (${original.technique_name})`,
                        corrected,
                        mismap.context,
                        mismap.rationale,
                        mismap.uid
                    )
                );
            }
            $("#edit-original").val($(element).data("name"));
            $(".sidebar li > a").removeClass("is-active");
            $(element).addClass("is-active");
            let techniques = JSON.parse(sessionStorage.getItem("mismappingTechniques"));
            renderMismapDropdown(techniques, ".mismappingDropdownOriginal");
            renderMismapDropdown(techniques, ".mismappingDropdownCorrected");
        },
    });
}

// mismapping form
function buildMismappingForm(original, corrected, context, rationale, uid) {
    return $(`
        <div class="card mismappingEdit">
            <div class="card-header">
                <p class="card-header-title">Edit Mismapping</p>
            </div>
            <div class="card-content">
                <div class="field-group">
                    <div class="field is-inline-block-desktop">
                        <label class="label">Original</label>
                        <div class="control dropdown-container">
                            <div class="dropdown" >
                                <div class="dropdown-trigger">
                                    <div class="field">
                                        <p class="control is-expanded has-icons-right">
                                            <input class="input" data-field="original" oninput="mismappingSearch(this,this.value)" type="text" onkeydown="mismappingNavigate(this,event)" placeholder="Search for technique... " value="${original}" />
                                            <span class="icon is-right"><i class="mdi mdi-18px mdi-menu-down"></i></span>
                                        </p>
                                    </div>
                                </div>
                                <div class="dropdown-menu" role="menu" style="display: none;">
                                    <div class="dropdown-content mismappingDropdownOriginal">
                                    </div>
                                </div>
                            </div>
                        </div>
                    </div>
                    <div class="field is-inline-block-desktop">
                        <label class="label">Corrected</label>
                        <div class="control dropdown-container">
                            <div class="dropdown" >
                                <div class="dropdown-trigger">
                                    <div class="field">
                                        <p class="control is-expanded has-icons-right">
                                            <input class="input" data-field="corrected" oninput="mismappingSearch(this,this.value)" onkeydown="mismappingNavigate(this,event)" type="text" placeholder="Search for technique..." value="${corrected}"/>
                                            <span class="icon is-right"><i class="mdi mdi-18px mdi-menu-down"></i></span>
                                        </p>
                                    </div>
                                </div>
                                <div class="dropdown-menu" style="display: none;">
                                    <div class="dropdown-content mismappingDropdownCorrected">
                                    </div>
                                </div>
                            </div>
                        </div>
                    </div>
                </div>

                <div class="field">
                    <label class="label">Context</label>
                    <div class="control">
                        <textarea class="textarea" data-field="context" placeholder="Context">${context}</textarea>
                    </div>
                </div>
                <div class="field">
                    <label class="label">Rationale</label>
                    <div class="control">
                        <textarea class="textarea" data-field="rationale" placeholder="Rationale">${rationale}</textarea>
                    </div>
                </div>
                <div class="control">
                    <button class="button is-link" data-id="${uid}" onclick="mismappingSave(this)">Save</button>
                    <button class="button is-danger" data-id="${uid}" onclick="mismappingDelete(this)">Delete</button>
                </div>
            </div>
        </div>

    `);
}
// function to build out a clickable menu that populates the technique for mismap editing
function buildSidebar(openTabs = []) {
    $.ajax({
        type: "GET",
        url: "/api/tactics",
        dataType: "json",
        data: {
            fields: ["tactic_id", "tactic_name", "techniques"],
            version: encodeURI($("#versionSelect").val()),
        },
        success: function (res) {
            let aside = $('<aside class="menu sidebar"></aside>');
            for (const tactic of res) {
                let tactic_id = tactic.tactic_id;
                let tactic_name = tactic.tactic_name;
                let technique_ul = $('<ul class="menu-list" style="display: none;"></ul>');

                // sort and modify the technique list to fit the sidebar
                // groups the subtechniques by parent technique, then by tactic
                let techniques = _.sortBy(
                    _.map(
                        _.groupBy(tactic.techniques, function (t) {
                            return t.technique_id.split(".")[0];
                        }),
                        function (value, key) {
                            return [
                                key,
                                _.sortBy(value, function (o) {
                                    return o.technique_id;
                                }),
                            ];
                        }
                    ),
                    function (o) {
                        return o[0];
                    }
                );

                let technique_name;
                for (const [key, value] of techniques) {
                    let li = "";

                    // if there is only 1 technique, then we can just append the technique to the menu
                    if (value.length == 1) {
                        technique_name = value[0].technique_name;
                        li = $(
                            `<li name="${key}"><a name="${key}" data-name="${key} (${technique_name})" onclick="preFillForm(this)">${key} (${technique_name})</a></li>`
                        );
                    } else {
                        // if the technique has subtechniques, we have to create a sub menu item that'll also show the subtechniques under the parent technique
                        technique_name = value[0].technique_name;
                        let ul = $(`<ul></ul>`);

                        li = $(`
                            <li name="${key}">
                                <a name="${key}" data-name="${key} (${technique_name})" onclick="preFillForm(this)">${key} (${technique_name})</a>
                            </li>
                        `);
                        for (const technique of value) {
                            let technique_id = technique.technique_id;
                            technique_name = technique.technique_name;
                            if (technique.technique_id !== key) {
                                ul.append(
                                    $(`
                                    <li name="${technique_id}"><a name="${technique_id}" data-name="${technique_id} (${technique_name})" onclick="preFillForm(this)">${technique_id} (${technique_name})</a></li>
                                `)
                                );
                            }
                        }
                        li.append(ul);
                    }
                    technique_ul.append(li);
                }

                aside.append(
                    $(`
                    <div name="${tactic_id}">
                        <p class="menu-label">
                            <a onclick="toggleSubMenu(this)">${tactic_id} (${tactic_name})<span class="icon is-right"><i class="mdi mdi-18px mdi-menu-down"></i></span></a>
                        </p>
                    </div>
                `).append(technique_ul)
                );
            }
            $("#sideBar").empty();
            $("#sideBar").append(aside);
            for (const tab of openTabs) {
                $(`div[name="${tab}"] > ul`).toggle();
            }
        },
    });
}
