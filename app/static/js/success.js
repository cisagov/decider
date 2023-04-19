// ---------------------------------------------------------------------------------------------------------------------
// Success-page Data Fetching / Rendering

$(document).ready(function () {
    let url_regex = /^\/question\/([^\/]*)\/(TA[0-9]{4})\/(T[0-9]{4}(\/[0-9]{3})?)$/;
    let match = window.location.pathname.match(url_regex);
    if (match !== null && match.length > 3) {
        let mismapLinkParams = new URLSearchParams([
            ["version", match[1]],
            ["tactic", match[2]],
            ["index", match[3].split("/").join(".")]
        ]).toString();
        $("#mismappingLink").attr("href", `/edit/mismapping?${mismapLinkParams}`);
    }

    $("#noTacticDropdownSelect").on("change", function () {
        let selected_tactic = $("#noTacticDropdownSelect :selected").val();
        let technique = $("#technique").data("value");
        $("#add_button_icon").attr("class", "mdi mdi-36px mdi-plus");
        $("#add_button").removeAttr("data-tooltip");
        $("#mismappingsButton").attr("data-tooltip", "Add/Edit/Delete Mismappings");
        $("#mismappingIcon").attr("class", "mdi mdi-24px mdi-table-edit");

        let mismapLinkParams = new URLSearchParams([
            ["version", $("#versionSelect").val()],
            ["tactic", selected_tactic],
            ["index", technique]
        ]).toString();
        $("#mismappingLink").attr("href", `/edit/mismapping?${mismapLinkParams}`);

        $("#noTacticDropdownSelect option[value='no_tactic']").remove();
    });
});

function addToCart(name, index) {
    var versionSelect = $("#versionSelect");

    let picked_tactic = $("#tacticDropdownSelect :selected");
    let item = {
        name: name,
        index: index,
        notes: "",
        tactic: picked_tactic.val(),
        tacticName: picked_tactic.data("tname"),
    };
    let cartData = getCart();

    // first item sets cart version
    if (cartData.entries.length === 0) {
        cartData.title = "untitled-" + getDateString();
        cartData.version = versionSelect.val();
        updateCartTitle(cartData.title, cartData.version);
        lockVersionSelect();
        unlockRename();
    }

    // cart has content, ensure version matches
    else {
        if (cartData.version !== versionSelect.val()) {
            $("#add_to_cart_mismatch_cartver").html(_.escape(cartData.version));
            $("#add_to_cart_mismatch_urlver").html(_.escape(versionSelect.val()));

            openModal("#add_to_cart_mismatch_modal");
            return;
        }
    }

    cartData.entries.unshift(item);
    sessionStorage.setItem("cart", JSON.stringify(cartData));

    $("#cart").prepend(cartItemTemplate(cartData.version, item));
    $("#cartColumn").show();
}

function tacticlessAddToCart(name, index) {
    var versionSelect = $("#versionSelect");

    let picked_tactic = $("#noTacticDropdownSelect :selected");
    if (picked_tactic.val() === "no_tactic") {
        return;
    }
    let item = {
        name: name,
        index: index,
        notes: "",
        tactic: picked_tactic.val(),
        tacticName: picked_tactic.data("tname"),
    };
    let cartData = getCart();

    // first item sets cart version
    if (cartData.entries.length === 0) {
        cartData.title = "untitled-" + getDateString();
        cartData.version = versionSelect.val();
        updateCartTitle(cartData.title, cartData.version);
        lockVersionSelect();
        unlockRename();
    }

    // cart has content, ensure version matches
    else {
        if (cartData.version !== versionSelect.val()) {
            $("#add_to_cart_mismatch_cartver").html(_.escape(cartData.version));
            $("#add_to_cart_mismatch_urlver").html(_.escape(versionSelect.val()));

            openModal("#add_to_cart_mismatch_modal");
            return;
        }
    }

    cartData.entries.unshift(item);
    sessionStorage.setItem("cart", JSON.stringify(cartData));

    $("#cart").prepend(cartItemTemplate(cartData.version, item));
    $("#cartColumn").show();
}
