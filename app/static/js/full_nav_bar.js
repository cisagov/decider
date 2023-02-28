// ---------------------------------------------------------------------------------------------------------------------
// Mini Search Functionality

$(document).ready(function () {
    // Search bar got focus -> show dropdown if it has content
    $(document).on("focusin", ".dropdown", function (e) {
        if ($(".dropdown-menu > .dropdown-content", this).contents().length > 0) {
            $(".dropdown-menu", this).show();
        }
    });

    // Search bar lost focus -> hide dropdown
    $(document).on("focusout", ".dropdown", function (e) {
        if (e.relatedTarget === null || !e.relatedTarget.classList.contains("dropdown-item"))
            $(".dropdown-menu", this).hide();
    });

    // Ensure filter is viaible / hidden as needed
    var shown = sessionStorage.getItem("filters-shown");
    if (shown === null || shown === "" || shown === "no") {
        sessionStorage.setItem("filters-shown", "no");
        $("#filterColumn").hide();
    } else {
        $("#filterColumn").show();
    }
});

document.addEventListener("DOMContentLoaded", () => {
    // Get all "navbar-burger" elements
    const $navbarBurgers = Array.prototype.slice.call(document.querySelectorAll(".navbar-burger"), 0);

    // Check if there are any navbar burgers
    if ($navbarBurgers.length > 0) {
        // Add a click event on each of them
        $navbarBurgers.forEach((el) => {
            el.addEventListener("click", () => {
                // Get the target from the "data-target" attribute
                const target = el.dataset.target;
                const $target = document.getElementById(target);

                // Toggle the "is-active" class on both the "navbar-burger" and the "navbar-menu"
                el.classList.toggle("is-active");
                $target.classList.toggle("is-active");
            });
        });
    }
});

function miniSearchTechniqueTemplate(t) {
    return $(`
    <a href="${t.url}" class="dropdown-item">
        <div>
            <p class="search-result-p">
                <span class="tag is-link search-result-tag">${t.tech_id}</span>
                ${t.tech_name}
            </p>
        </div>
    </a>
    `);
}

var miniSearch = _.debounce(function (search) {
    // Search of 0/1 characters ignored
    if (search.length < 2) {
        $("#searchBarCompletion > .dropdown-content").empty();
        $("#searchBarCompletion").hide();
        return;
    }

    var attack_version = $("#versionSelect").val();

    // Get Techniques from server and display
    $.ajax({
        type: "POST",
        url: `/search/mini/${attack_version}`,
        data: JSON.stringify({ search: search }),
        contentType: "application/json; charset=utf-8",
        dataType: "json",
        success: function (techniques) {
            // Clear results for re-population
            $("#searchBarCompletion > .dropdown-content").empty();

            // Add default (1st) option: run search as full search
            $("#searchBarCompletion > .dropdown-content").append(
                $(`<a href="#" onclick="gotoFullSearch(); event.preventDefault();" class="dropdown-item dropdown-item-selected">
                    <div>
                        <p class="search-result-p">
                            <span class="tag is-link search-result-tag"><i class="mdi mdi-24px mdi-magnify" style="color: white;"></i></span>
                            <b><i>Run as a Full Technique Search</i></b>
                        </p>
                    </div>
                </a>`)
            );

            // Add warning to full search option if there were no results
            if (techniques.length === 0) {
                $(
                    "#searchBarCompletion > .dropdown-content > .dropdown-item-selected > div > .search-result-p"
                ).append("<br><i>(no mini search results)</i>");
            }

            // On results: add entries
            else {
                for (const tech of techniques) {
                    let miniSearchRow = miniSearchTechniqueTemplate(tech);
                    $("#searchBarCompletion > .dropdown-content").append(miniSearchRow);
                }
            }

            $("#searchBarCompletion").show();
            $("#searchBarCompletion").scrollTop(0); // starts at top
        },
    });
}, 100);

function searchBarNavigate(event) {
    // utility case - hide dropdown
    if (event.key === "Escape") {
        $("#searchBar").blur();
    }

    // navigation
    else if (_.includes(["ArrowUp", "ArrowDown", "Enter"], event.key)) {
        let selectedItem = $("#searchBarCompletion > .dropdown-content > .dropdown-item-selected");

        // go to selected link
        if (event.key === "Enter") {
            if (selectedItem[0] === undefined)
                // no selection + enter -> open full search
                gotoFullSearch();
            else selectedItem[0].click(); // selection + enter -> open selection
        }

        // change selection
        else {
            // prevent navigating an empty dropdown
            if (selectedItem[0] === undefined) {
                return;
            }

            // prevent up/down from moving the input cursor
            event.preventDefault();

            let container = $("#searchBarCompletion");
            let items = $("#searchBarCompletion > .dropdown-content").children(".dropdown-item");
            let selectedIndex = $(".dropdown-item").index(selectedItem);

            if (event.key === "ArrowUp") {
                // up
                if (selectedIndex > 0) {
                    // change selection
                    selectedItem.removeClass("dropdown-item-selected");
                    let selectedItemNew = $(items[selectedIndex - 1]);
                    selectedItemNew.addClass("dropdown-item-selected");

                    // scroll to new
                    container.scrollTop(selectedItemNew.offset().top - container.offset().top + container.scrollTop());
                }
            } else if (event.key === "ArrowDown") {
                // down
                if (selectedIndex < items.length - 1) {
                    // change selection
                    selectedItem.removeClass("dropdown-item-selected");
                    let selectedItemNew = $(items[selectedIndex + 1]);
                    selectedItemNew.addClass("dropdown-item-selected");

                    // scroll to new
                    container.scrollTop(selectedItemNew.offset().top - container.offset().top + container.scrollTop());
                }
            }
        }
    }
}
