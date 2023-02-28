// BAREBONES
// ---------
// shared_barebones.js
//   - holds all functionality that can be used in both base.html pages and base-barebones.html pages
// shared.js
//   - holds functionality used in base.html pages but not base-barebones.html page
// as it stands
//   - login in the only page using base-barebones
//   - shared.js is for anything the rest of the app uses but that cannot go in login

$(document).ready(function () {
    // clear front-end sessionstorage if format of front-end data (carts) has changed
    let neededFrontendVersion = "c13a8a11-bd01-4464-9190-a4280e114c1a";
    let currentFrontendVersion = sessionStorage.getItem("currentFrontendVersion");
    if (currentFrontendVersion !== neededFrontendVersion) {
        sessionStorage.clear();
        sessionStorage.setItem("currentFrontendVersion", neededFrontendVersion);
    }
});

// --------------------------------------------------------------------------------------------------------------------
// Bulma Toast Config

function showToast(message, type = "is-success") {
    bulmaToast.toast({
        message: message,
        type: type,
        dismissible: true,
        animate: { in: "fadeIn", out: "fadeOut" },
        duration: 3500,
        pauseOnHover: true,
        closeOnClick: true,
        position: "bottom-right",
    });
}

// --------------------------------------------------------------------------------------------------------------------
// AJAX - Global Error Handler -> Makes Bulma Toasts

$(document).ajaxError(function (_event, xhr, _status, _err) {
    let message = null;

    try {
        message = JSON.parse(xhr.responseText).message;
    } catch (error) {
        message = null;
    }

    message = message || "Server is unavailable. Otherwise, error is unknown.";
    showToast(message, "is-danger");
});

// SHARED
// ------
// shared_barebones.js
//   - holds all functionality that can be used in both base.html pages and base-barebones.html pages
// shared.js
//   - holds functionality used in base.html pages but not base-barebones.html page
// as it stands
//   - login in the only page using base-barebones
//   - shared.js is for anything the rest of the app uses but that cannot go in login

// --------------------------------------------------------------------------------------------------------------------
// Base Functionality for generic_filters.html Template Component

function getChkSelections(kind) {
    // Pull storage, defined if unset, return
    var chk_selections = sessionStorage.getItem(`${kind}_checkbox_selections`);
    if (chk_selections === null) {
        chk_selections = [];
        sessionStorage.setItem(`${kind}_checkbox_selections`, JSON.stringify(chk_selections));
    } else {
        chk_selections = JSON.parse(chk_selections);
    }
    return chk_selections;
}

function syncFilters(kind) {
    // Pull selections
    var chk_selections = getChkSelections(kind);

    // For each checkbox - set page state to match storage state
    var checkboxes = $(`#${kind}-selection`).find('input[type="checkbox"]');
    _.forEach(checkboxes, function (chkbox) {
        var is_checked = chk_selections.includes($(chkbox).attr("id").slice(`${kind}-`.length));
        $(chkbox).prop("checked", is_checked);
    });
}

function clearFilters(kind) {
    // Clear selections & sync cleared state to checkboxes themselves
    sessionStorage.setItem(`${kind}_checkbox_selections`, JSON.stringify([]));
    syncFilters(kind);
}

function updateFilters(kind, checkbox) {
    // Update to make
    var filter = $(checkbox).attr("id").slice(`${kind}-`.length);
    var enabled = $(checkbox).is(":checked");

    // Existing state
    var chk_selections = getChkSelections(kind);
    var filter_is_set = _.indexOf(chk_selections, filter) !== -1;

    // If selection was turned on; add to selection if not already there
    if (enabled) {
        if (!filter_is_set) {
            chk_selections.push(filter);
        }
    }

    // If selection was turned off; remove from selection if present
    else {
        if (filter_is_set) {
            _.remove(chk_selections, function (f) {
                return f === filter;
            });
        }
    }

    // Write-back
    sessionStorage.setItem(`${kind}_checkbox_selections`, JSON.stringify(chk_selections));
}

// Fade in/out filters column when filters button (in top right) is clicked
function toggleFilter() {
    var shown = sessionStorage.getItem("filters-shown");
    if (shown === null || shown === "" || shown === "yes") {
        sessionStorage.setItem("filters-shown", "no");
        $("#filterColumn").fadeOut(200);
    } else {
        sessionStorage.setItem("filters-shown", "yes");
        $("#filterColumn").fadeIn(200);
    }
}

// Slide down/up filter contents/checkboxes when filter header/name is clicked
function showHideFilters(kind) {
    let filterElem = $(`#${kind}-selection`);

    if (filterElem.is(":hidden")) filterElem.slideDown("slow");
    else filterElem.slideUp("slow");
}

// --------------------------------------------------------------------------------------------------------------------
// Generic Modal Open and Close Functions

function closeModal(m) {
    $(m).removeClass("is-active");
}

function openModal(m) {
    $(m).addClass("is-active");
}

// ---------------------------------------------------------------------------------------------------------------------
// Full Search URL is generated based on dropdown on icon click

function gotoFullSearch() {
    var attackVersion = $("#versionSelect").val();
    var searchStr = $("#searchBar").val();

    var paramStr = new URLSearchParams([
        ["version", attackVersion],
        ["search", searchStr],
    ]).toString();

    window.location.href = `/search/page?${paramStr}`;
}

// --------------------------------------------------------------------------------------------------------------------
// Functions to jump back to the top of the page

window.onscroll = function () {
    displayJump();
};

function displayJump() {
    let button = $(".jump-to-top");
    if (document.body.scrollTop > 20 || document.documentElement.scrollTop > 20) {
        button.css("display", "block");
    } else {
        button.css("display", "none");
    }
}

function jumpToTop() {
    $([document.documentElement, document.body]).animate({ scrollTop: 0 }, 1000);
}

// ---------------------------------------------------------------------------------------------------------------------
// Allow versioned navigation to suggestions page

function gotoSuggestions() {
    let cartData = getCart();
    if (cartData.entries.length === 0) {
        //cart is empty
        showToast("You must add items to the cart first.", "is-warning");
        return;
    }

    let version = $("#versionSelect").val();
    window.location.href = `/suggestions/${version}`;
    return false; // ignore href
}

// --------------------------------------------------------------------------------------------------------------------
// Alert Modal Maker - dynamic modal replacement for alert(...)

function spawnAlertModal(title, content) {
    // gives a unique identifier (not that multiple modals should be used at once)
    let modal_id = `alert_${_.random(10000, 99999)}`;

    // hides and then removes from DOM
    let close_n_kill = `closeModal('#${modal_id}'); $('#${modal_id}').remove();`;

    // throw into DOM
    $(document.body).append(`
    <div class="modal is-active" id="${modal_id}">
        <div class="modal-background" onclick="${close_n_kill}"></div>
        <div class="modal-card">
            <header class="modal-card-head">
                <p class="modal-card-title">${_.escape(title)}</p>
                <button class="delete" aria-label="close" onclick="${close_n_kill}"></button>
            </header>
            <section class="modal-card-body default-list">
                ${_.escape(content)}
            </section>
            <footer class="modal-card-foot">
                <button class="button is-info" onclick="${close_n_kill}">Ok</button>
            </footer>
        </div>
    </div>
    `);
}

// ---------------------------------------------------------------------------------------------------------------------
// Change ATT&CK Versions / URL+Cart Version Mismatch Handlers

// navigates the page as necessary to change the version using a string argument
// does NOT modify user preferences
function changeVersionStageTwo(new_version) {
    // allows search to pull from version selector like normal
    $("#versionSelect").val(new_version);

    // get url
    let curr_url = window.location.pathname;
    let next_url = "";

    // (question, success) -> keep location, change version (can 404 if not present is other version)
    if (_.startsWith(curr_url, "/question") || _.startsWith(curr_url, "/no_tactic")) {
        let url_portions = curr_url.match(/^\/(no_tactic|question)\/[^\/]+(.*$)/);
        let route_type = url_portions[1];
        let rest_of_path = url_portions[2];
        next_url = `/${route_type}/${new_version}${rest_of_path}`;
    }

    // (search) -> re-render with version-change true (search handles changing URL history / reload)
    else if (_.startsWith(curr_url, "/search/page")) {
        searchFetchAndRender(true);
    }

    // (suggestions) -> change version at end
    else if (_.startsWith(curr_url, "/suggestions")) {
        next_url = `/suggestions/${new_version}`;
    }

    // (edit mismappings) ->
    else if (_.startsWith(curr_url, "/edit/mismapping")) {
        let openTabs = $("aside > div:has(ul.menu-list:visible)").map(function () {
            return $(this).attr("name");
        });
        mismappingInit();

        // re-render the sidebar when changing version
        buildSidebar(openTabs);

        $("#reset-edit-form")
            .closest(".card")
            .find("input, textarea")
            .each(function () {
                $(this).val("");
            });
        $("#mismappingsContainer").empty();
    }

    // (audit tree edits / content) -> reload page under new version
    else if (_.startsWith(curr_url, "/edit/tree/audit")) {
        next_url = `/edit/tree/audit/${new_version}`;
    }

    // (edit tree) ->
    else if (_.startsWith(curr_url, "/edit/tree")) {
        // update link to audit
        $("#edit-tree-link-to-audit").prop("href", `/edit/tree/audit/${new_version}`);

        // update content
        let tab = $("#tabs1").find(".is-active");
        openTab(tab.get(0), tab.find("a").text(), "1");
        populateSidebar();
        jumpToIDChangeVersion($("#versionSelect").val());
    }

    // OTHERS -> go to "home-page" for version
    else {
        next_url = `/question/${new_version}`;
    }

    // destination is question page -> clear answer card filters
    if (_.startsWith(next_url, "/question")) {
        if (typeof questionClearDataSources === "function") {
            questionClearDataSources(); // ATT&CK v10+
        }
        if (typeof questionClearPlatforms === "function") {
            questionClearPlatforms(); // all versions
        }
    }

    // either navigate or update home button
    if (next_url !== "") {
        // destination defined -> navigate;
        window.location.href = next_url;
    } else {
        // stay on same page -> update home button link
        $("#homeButton").prop("href", `/question/${new_version}`);
    }
}

// can be provided a string or the version selector HTML element
// updates the user version preference and then calls stage 2 to change the URL
function changeVersion(elem_or_str) {
    // get version
    let new_version;
    if (typeof elem_or_str === "object") {
        new_version = $(elem_or_str).val(); // element (user caller, html onclick=func(this))
    } else {
        new_version = elem_or_str; // string (code caller)
    }

    // update version preference then change version
    $.ajax({
        type: "PATCH",
        url: "/api/user_version_change",
        contentType: "application/json",
        dataType: "json",
        data: JSON.stringify({
            new_version: new_version,
        }),
        success: changeVersionStageTwo(new_version),
    });
}

// changes the version via URL, may lead the user to a 404
function urlCartMismatchChangeVer() {
    changeVersion(getCart().version);
}

// brings the user to the home question page for their cart version, always succeeds
// does not use changeVersion() as that cannot force a question home destination
function urlCartMismatchGoHome() {
    let new_version = getCart().version;

    // update version preference
    $.ajax({
        type: "PATCH",
        url: "/api/user_version_change",
        contentType: "application/json",
        dataType: "json",
        data: JSON.stringify({
            new_version: new_version,
        }),
        success: function () {
            // clear answer card filters
            if (typeof questionClearDataSources === "function") {
                questionClearDataSources(); // ATT&CK v10+
            }
            if (typeof questionClearPlatforms === "function") {
                questionClearPlatforms(); // all versions
            }

            // navigate
            let correctVersion = new_version;
            window.location.href = `/question/${correctVersion}`;
        },
    });
}

// ---------------------------------------------------------------------------------------------------------------------
// Password Validation

function passwordValidatorJSON(passwordA, passwordB) {
    // test statuses [[message, passed], ..]
    let tests = [];

    function doTest(passed, message) {
        tests.push({
            message: message,
            passed: passed,
        });
        allPassed = allPassed && passed;
    }

    // default requirements
    reqs = {
        // inclusive length range
        minLength: 8,
        maxLength: 48,

        // at least
        numLowers: 2,
        numUppers: 2,
        numNumbers: 2,
        numSpecials: 2,
    };

    let allPassed = true;

    // password composition determination
    let numLowers = passwordA.split("").filter((c) => "a" <= c && c <= "z").length;
    let numUppers = passwordA.split("").filter((c) => "A" <= c && c <= "Z").length;
    let numNumbers = passwordA.split("").filter((c) => "0" <= c && c <= "9").length;
    let numIllegals = passwordA.split("").filter((c) => c < "\x20" || c > "\x7E").length;
    let numSpecials = passwordA.length - (numLowers + numUppers + numNumbers + numIllegals);

    doTest(passwordA === passwordB, `Passwords match: ${passwordA === passwordB}`);
    doTest(
        passwordA.length >= reqs.minLength && passwordA.length <= reqs.maxLength,
        `Length: ${passwordA.length}, Required: ${reqs.minLength} - ${reqs.maxLength}`
    );
    doTest(numLowers >= reqs.numLowers, `Lower-case chars: ${numLowers} / ${reqs.numLowers}`);
    doTest(numUppers >= reqs.numUppers, `Upper-case chars: ${numUppers} / ${reqs.numUppers}`);
    doTest(numNumbers >= reqs.numNumbers, `Numeric chars: ${numNumbers} / ${reqs.numNumbers}`);
    doTest(numSpecials >= reqs.numSpecials, `Special chars: ${numSpecials} / ${reqs.numSpecials}`);
    doTest(numIllegals === 0, `Illegal chars used: ${numIllegals}`);

    return {
        passed: allPassed,
        tests: tests,
    };
}

async function ajaxJSON(method, url, data) {
    return new Promise((resolve, reject) => {
        $.ajax({
            url: url,
            type: method,
            data: JSON.stringify(data),
            dataType: "json",
            contentType: "application/json; charset=utf-8",

            success: function (data) {
                resolve(data);
            },

            error: function (err) {
                reject(err.responseJSON);
            },
        });
    });
}
