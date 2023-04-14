$(document).ready(function () {
    populateCart();

    // Disable version selector if a lock has been set (cart is open)
    if (isVersionSelectLocked()) {
        lockVersionSelect();

        // Check integrity of cart version against selector - they need to match,
        //   manual URL editing (/linking) can mess this up
        var cartVersion = getCart().version;
        var urlVersion = $("#versionSelect").val();
        if (cartVersion !== urlVersion) {
            $("#url_cart_mismatch_cartver").html(_.escape(cartVersion));
            $("#url_cart_mismatch_urlver").html(_.escape(urlVersion));
            openModal("#url_cart_mismatch_modal");
        }
    }

    var shown = sessionStorage.getItem("cart-shown");
    if (shown === null || shown === "" || shown === "no") {
        sessionStorage.setItem("cart-shown", "no");
        $("#cartColumn").hide();
    } else {
        $("#cartColumn").show();
    }

    // auto-save feature present and enabled -> visually show that
    if ($("#auto-save").length !== 0 && sessionStorage.getItem("auto-save") === "true")
        $("#auto-save").prop("checked", true);

    var cartData = getCart();
    if (cartData.entries.length === 0) {
        lockRename();
    }
    $("#cartFile").on("input", uploadCart);
});

// --------------------------------------------------------------------------------------------------------------------

function emptyCartString() {
    return '{ "title": null, "version": null, "entries": [] }';
}

function getCart() {
    var cartStr;
    var cartObj;

    cartStr = sessionStorage.getItem("cart");

    try {
        cartObj = JSON.parse(cartStr);
        if (
            !cartObj.hasOwnProperty("title") ||
            !cartObj.hasOwnProperty("version") ||
            !cartObj.hasOwnProperty("entries")
        )
            throw new Error("malformed cart");
    } catch (e) {
        cartStr = emptyCartString();
        sessionStorage.setItem("cart", cartStr);
        cartObj = JSON.parse(cartStr);
    }
    return cartObj;
}

function updateCartTitle(title, version) {
    if (version === null && title === null) {
        $("#cart-title").html("Cart");
    } else {
        let title_esc = _.escape(title);
        let version_esc = _.escape(version);
        $("#cart-title").html(
            `${title_esc}<sub><span style="font-weight: normal; font-size: 0.75em;">(${version_esc})</span></sub>`
        );
    }
}

function populateCart() {
    let cartData = getCart();
    updateCartTitle(cartData.title, cartData.version);
    for (const cartEntry of cartData.entries) {
        $("#cart").append(cartItemTemplate(cartData.version, cartEntry));
    }
}

var saveNote = _.debounce(function () {
    let cartData = getCart();
    let autoSave = $("#auto-save").length !== 0 && sessionStorage.getItem("auto-save") === "true";

    let cart = $(".note")
        .map((_, e) => e.value)
        .get();
    for (let i = 0; i < cartData.entries.length; i++) {
        cartData.entries[i].notes = cart[i];
    }
    sessionStorage.setItem("cart", JSON.stringify(cartData));
    if (autoSave) {
        saveCartDatabase(false); // verbose=false
    }
}, 400);

function updateAutoSave() {
    // update session storage to match checkbox
    let newState = $("#auto-save").prop("checked").toString();
    sessionStorage.setItem("auto-save", newState);

    // run quick save incase content was added before enabling auto-save to DB (as auto-save uses oninput events)
    if (newState === "true" && getCart().entries.length !== 0) saveCartDatabase(false); // verbose=false
}

function deleteItem(element) {
    // visual removal
    var cartItem = $(element).closest("li");
    var index = cartItem.index();
    cartItem.remove();

    // data removal
    var cartData = getCart();
    cartData.entries.splice(index, 1);
    if (cartData.entries.length === 0) {
        cartData.title = null;
        cartData.version = null;
        updateCartTitle(null, null);
        lockRename();
        unlockVersionSelect();
    }

    sessionStorage.setItem("cart", JSON.stringify(cartData));
}

function toggleCart() {
    var shown = sessionStorage.getItem("cart-shown");
    if (shown === null || shown === "" || shown === "yes") {
        sessionStorage.setItem("cart-shown", "no");
        $("#cartColumn").fadeOut(200);
    } else {
        sessionStorage.setItem("cart-shown", "yes");
        $("#cartColumn").fadeIn(200);
    }
}

function importCart() {
    if (!window.File || !window.FileReader || !window.FileList || !window.Blob) {
        spawnAlertModal("Browser Compatibility Issue", "The File APIs are not fully supported in this browser.");
        return;
    }
    $("#cartFile").click();
}

function cartItemTemplate(version, i) {
    // i -> cart entry data
    let itemURL = `/question/${version}/${i.tactic}/${i.index.replace(".", "/")}`;
    return $(`
        <li class="cartItem">
            <a href="${itemURL}">
                ${_.escape(i.name)} (${_.escape(i.index)})<br>
                <i>${_.escape(i.tacticName)} (${_.escape(i.tactic)})</i>
            </a>
            <textarea oninput="saveNote()" class="textarea is-small note">${_.escape(i.notes)}</textarea>
            <a class="cartItemDelete">
                <span class="icon is-medium">
                    <i class="mdi mdi-24px mdi-delete" onclick="deleteItem(this)"></i>
                </span>
            </a>
        </li>
    `);
}

// --------------------------------------------------------------------------------------------------------------------
// Save Cart to Database Functionality

function preSaveCartModal() {
    let cartData = getCart();
    if (cartData.entries.length === 0) {
        //cart is empty
        showToast("You must add items to the cart first.", "is-warning");
        return;
    }
    openModal("#save_modal");
}

function saveCartDatabase(verbose) {
    let cartData = getCart();
    let cart_name = cartData.title;

    // check if cart name is empty
    if (_.trim(cart_name) === "") {
        showToast("Please enter a cart name.", "is-warning");
        return;
    }

    // check if the cart is empty
    if (cartData.entries.length === 0) {
        showToast("The cart is empty.", "is-warning");
        return;
    }

    $.ajax({
        url: "/profile/save_cart",
        type: "POST",
        contentType: "application/json",
        data: JSON.stringify(cartData),
        success: function () {
            $("#rename_modal_new_name").val("");
            closeModal("#save_modal");

            if (verbose) {
                openModal("#success_modal");
            } else {
                showToast("Cart successfully saved to the database");
            }
        },
    });
}

// called when manually entered cart name changes
function cartNameChange() {
    var typedCartName = _.trim($("#rename_modal_new_name").val());
    var currentCart = getCart();
    var attackVersion = currentCart.version;

    // save local
    currentCart.title = typedCartName;
    sessionStorage.setItem("cart", JSON.stringify(currentCart));
    updateCartTitle(typedCartName, attackVersion);
    closeModal("#rename_modal");

    // auto-save on -> DB save as well
    let autoSave = $("#auto-save").length !== 0 && sessionStorage.getItem("auto-save") === "true";
    if (autoSave) saveCartDatabase(false);
}

// opens the #rename_modal for cart rename
// lists current cart names to ensure an over-write is only done intentionally
// used instead of openModal('#rename_modal') as cart name list is dynamic
function showRenameModal() {
    let curNameBox = $("#rename_modal_current_name");
    let newNameBox = $("#rename_modal_new_name");
    let dbCartList = $("#rename_modal_db_cart_list");

    curNameBox.html(_.escape(getCart().title));
    newNameBox.val("");
    dbCartList.empty();

    $.ajax({
        url: "/profile/carts",
        type: "GET",
        contentType: "application/json",
        dataType: "json",
        success: showRenameModalPopulateCallback,
    });

    openModal("#rename_modal");
}

// callback for showRenameModal() to get and populate the DB cart list
// fills a list with escaped named
function showRenameModalPopulateCallback(carts) {
    let dbCartList = $("#rename_modal_db_cart_list");
    for (const cart of carts) {
        dbCartList.append(`<li>${_.escape(cart.name)}</li>`);
    }
}

// is called when the new name box is typed in for the rename modal
function renameModalOnTypeNewName() {
    let newName = _.trim($("#rename_modal_new_name").val());
    let dbCartList = $("#rename_modal_db_cart_list");

    // if first list item exists - clear incase it was the last result match
    if (dbCartList.children().length > 0) {
        let firstCart = $(dbCartList.children()[0]);
        firstCart.removeClass("rename-modal-to-overwrite");
    }

    // find new match, move to top of list, highlight & bold
    for (const cart of dbCartList.children()) {
        let jqCart = $(cart);
        if (newName === jqCart.text()) {
            dbCartList.remove(jqCart);
            dbCartList.prepend(jqCart);
            jqCart.addClass("rename-modal-to-overwrite");
            break;
        }
    }

    // update Confirm button if new name is deemed valid
    $("#rename-modal-confirm-button").prop("disabled", newName === "");
}

// --------------------------------------------------------------------------------------------------------------------
// Upload Download Operations

function getDateString() {
    // YYYY-MM-DD_hh-mm-ss
    let d = new Date();

    let year = d.getFullYear();
    let month = _.padStart(String(d.getMonth() + 1), 2, "0");
    let day = _.padStart(String(d.getDate()), 2, "0");
    let hour = _.padStart(String(d.getHours()), 2, "0");
    let minute = _.padStart(String(d.getMinutes()), 2, "0");
    let second = _.padStart(String(d.getSeconds()), 2, "0");

    return `${year}-${month}-${day}_${hour}-${minute}-${second}`;
}

// --------------------------------------------------------------------------------------------------------------------
// Upload Download Operations

function downloadCart() {
    let cartData = getCart();
    if (cartData.entries.length === 0) {
        //cart is empty
        showToast("You must add items to the cart first.", "is-warning");
        return;
    }
    let fileName = cartData.title + ".json";
    cartData = JSON.stringify(cartData);

    let fileToSave = new Blob([cartData], {
        type: "application/JSON",
        name: fileName,
    });
    saveAs(fileToSave, fileName);
}

function uploadCart(cartFileInput) {
    var file = cartFileInput.target.files[0];
    if (!file) {
        spawnAlertModal("Cart Upload Issue", "The file specified is invalid");
        return;
    }
    var reader = new FileReader();
    reader.onload = function (e) {
        var contents = e.target.result;
        updateImport(contents);
    };
    reader.readAsText(file);
}

// --------------------------------------------------------------------------------------------------------------------
// Word Export

function hyperlinkParagraph(args) {
    const par = new docx.Paragraph({
        alignment: args.alignment,
        children: [
            new docx.ExternalHyperlink({
                children: [
                    new docx.TextRun({
                        text: args.text,
                        style: "Hyperlink",
                        bold: args.bold,
                        color: args.color,
                    }),
                ],
                link: args.link,
            }),
        ],
    });

    return par;
}

function wordExport() {
    let cartData = getCart();
    if (cartData.entries.length === 0) {
        //cart is empty
        showToast("You must add items to the cart first.", "is-warning");
        return;
    }

    $.ajax({
        url: "/word_export",
        type: "POST",
        data: JSON.stringify(cartData),
        contentType: "application/json; charset=utf-8",
        dataType: "json",
        success: function (data) {
            // column width spacing params - active page space is 9028 units wide
            const TECH_NAME_COL_W = 3000;
            const TECH_ID_COL_W = 1500;
            const TECH_USES_COL_W = 9028 - TECH_NAME_COL_W - TECH_ID_COL_W;

            // response fields
            let tactsAndTechs = data.tactsAndTechs;
            let lookupUsage = data.usages;

            // columns = [..., [tactId, tactName, tactUrl, [[techId, techName, techUrl], ., .]], ...]
            let tactId, tactName, tactUrl;
            let techId, techName, techUrl;
            let techRows;

            let tableRows = [];

            // loop through tactics in cart
            tactsAndTechs.forEach((tactRow) => {
                [tactId, tactName, tactUrl, techRows] = tactRow;

                // tactic header
                tableRows.push(
                    new docx.TableRow({
                        height: {
                            value: 400,
                            rule: docx.HeightRule.EXACT,
                        },
                        children: [
                            new docx.TableCell({
                                width: {
                                    size: 9028,
                                    type: docx.WidthType.DXA,
                                },
                                columnSpan: 3,
                                verticalAlign: docx.VerticalAlign.CENTER,
                                shading: {
                                    fill: "444444",
                                    type: docx.ShadingType.SOLID,
                                    color: "444444",
                                },
                                children: [
                                    hyperlinkParagraph({
                                        text: `${tactName} [${tactId}]`,
                                        link: tactUrl,
                                        bold: true,
                                        color: "00bbee",
                                        alignment: docx.AlignmentType.CENTER,
                                    }),
                                ],
                            }),
                        ],
                    })
                );

                // technique header
                const techHeaderTextsWidths = [
                    { text: "Technique Name", width: TECH_NAME_COL_W },
                    { text: "ID", width: TECH_ID_COL_W },
                    { text: "Use(s)", width: TECH_USES_COL_W },
                ];
                tableRows.push(
                    new docx.TableRow({
                        height: {
                            value: 400,
                            rule: docx.HeightRule.EXACT,
                        },
                        children: techHeaderTextsWidths.map(
                            (cellData) =>
                                new docx.TableCell({
                                    width: {
                                        size: cellData.width,
                                        type: docx.WidthType.DXA,
                                    },
                                    shading: {
                                        fill: "888888",
                                        type: docx.ShadingType.SOLID,
                                        color: "888888",
                                    },
                                    verticalAlign: docx.VerticalAlign.CENTER,
                                    children: [
                                        new docx.Paragraph({
                                            alignment: docx.AlignmentType.CENTER,
                                            children: [
                                                new docx.TextRun({
                                                    text: cellData.text,
                                                    bold: true,
                                                    color: "ffffff",
                                                }),
                                            ],
                                        }),
                                    ],
                                })
                        ),
                    })
                );

                // loop through techs of tactic
                techRows.forEach((techRow) => {
                    [techId, techName, techUrl] = techRow;

                    let rowCells = [];
                    let usages = lookupUsage[`${tactId}--${techId}`] ?? [];

                    // look through usages in tact-tech pair
                    usages.forEach((usage, index) => {
                        // first row gets spanned Tech Name & Tech ID cells
                        if (index === 0) {
                            rowCells.push(
                                ...[
                                    new docx.TableCell({
                                        verticalAlign: docx.VerticalAlign.CENTER,
                                        rowSpan: usages.length,
                                        children: [new docx.Paragraph(techName)],
                                    }),
                                    new docx.TableCell({
                                        verticalAlign: docx.VerticalAlign.CENTER,
                                        rowSpan: usages.length,
                                        children: [
                                            hyperlinkParagraph({
                                                text: techId,
                                                link: techUrl,
                                                bold: true,
                                                alignment: docx.AlignmentType.CENTER,
                                            }),
                                        ],
                                    }),
                                ]
                            );
                        }

                        // all rows get usage
                        rowCells.push(
                            new docx.TableCell({
                                children: [new docx.Paragraph(usage || "-")],
                            })
                        );

                        // add row
                        tableRows.push(
                            new docx.TableRow({
                                children: rowCells,
                            })
                        );
                        rowCells = [];
                    });
                });
            });

            // header text
            const docHeaderParagraphs = [
                new docx.Paragraph({
                    children: [
                        new docx.TextRun({ text: "Decider Version:", bold: true }),
                        new docx.TextRun({ text: ` ${data.appVersion}\n` }),
                    ],
                }),
                new docx.Paragraph({
                    spacing: {
                        after: 400,
                    },
                    children: [
                        new docx.TextRun({ text: "Cart Export Time:", bold: true }),
                        new docx.TextRun({ text: ` ${new Date().toString()}\n` }),
                    ],
                }),
            ];

            // document
            const doc = new docx.Document({
                sections: [
                    {
                        children: [
                            ...docHeaderParagraphs,
                            new docx.Table({
                                width: {
                                    size: 9028,
                                    type: docx.WidthType.DXA,
                                },
                                rows: tableRows,
                            }),
                        ],
                    },
                ],
            });

            // dump
            docx.Packer.toBlob(doc).then((blob) => {
                saveAs(blob, `${cartData.title}-word.docx`);
            });
        },
    });
}

// --------------------------------------------------------------------------------------------------------------------
// Navigator Export

function navigatorExport() {
    let cartData = getCart();
    if (cartData.entries.length === 0) {
        //cart is empty
        showToast("You must add items to the cart first.", "is-warning");
        return;
    }

    let tech_list = [];

    for (const cartEntry of cartData.entries) {
        let technique_id = cartEntry.index;
        let modified_tactic_name = cartEntry.tacticName.toLowerCase().replaceAll(" ", "-");
        let notes = cartEntry.notes;
        const techniques = tech_list.map(({ techniqueID }) => techniqueID);
        if (techniques.indexOf(technique_id) >= 0) {
            let tech_to_change = tech_list[techniques.indexOf(technique_id)];
            if (modified_tactic_name == tech_to_change["tactic"]) {
                tech_to_change["comment"] = tech_to_change["comment"] + " | " + notes;
                continue;
            }
        }

        let base_layer_json = {
            techniqueID: technique_id,
            tactic: modified_tactic_name,
            color: "#e60d0d",
            comment: notes,
            enabled: "true",
            metadata: [],
            links: [],
            showSubtechniques: true,
        };
        tech_list.push(base_layer_json);
    }
    // This will need to be updated as the ATT&CK versions change. Not sure of a way around this at this moment.
    let navigator_json = {
        name: "layer",
        versions: {
            attack: cartData.version.substring(1), // vx.y... -> x.y...
            navigator: "4.8.0",
            layer: "4.4",
        },
        domain: "enterprise-attack",
        description: "",
        filters: {
            platforms: [
                "Linux",
                "macOS",
                "Windows",
                "Azure AD",
                "Office 365",
                "SaaS",
                "IaaS",
                "Google Workspace",
                "PRE",
                "Network",
                "Containers",
            ],
        },
        sorting: 0,
        layout: {
            layout: "side",
            aggregateFunction: "average",
            showID: false,
            showName: true,
            showAggregateScores: false,
            countUnscored: false,
        },
        hideDisabled: false,
        techniques: tech_list,
        gradient: {
            colors: [
                "#ff6666ff",
                "#ffe766ff",
                "#8ec843ff"
            ],
            minValue: 0,
            maxValue: 100,
        },
        legendItems: [],
        metadata: [],
        links: [],
        showTacticRowBackground: false,
        tacticRowBackground: "#dddddd",
        selectTechniquesAcrossTactics: true,
        selectSubtechniquesWithParent: false,
    };
    downloadObjectAsJson(navigator_json, cartData.title);
}

function downloadObjectAsJson(exportObj, exportName) {
    var dataStr = "data:text/json;charset=utf-8," + encodeURIComponent(JSON.stringify(exportObj));
    var downloadAnchorNode = document.createElement("a");
    downloadAnchorNode.setAttribute("href", dataStr);
    downloadAnchorNode.setAttribute("download", exportName + "-navigator.json");
    document.body.appendChild(downloadAnchorNode); // required for firefox
    downloadAnchorNode.click();
    downloadAnchorNode.remove();
}

// --------------------------------------------------------------------------------------------------------------------
// Load Cart from File + Misc

function updateImport(inputCartData) {
    // fetch ATT&CK versions on server to ensure this cart will have content to view
    $.ajax({
        type: "GET",
        url: "/api/versions",
        dataType: "json",
        success: function (versions) {
            let cartData = JSON.parse(emptyCartString());
            try {
                inputCartData = JSON.parse(inputCartData);

                // top level key validation
                if (!inputCartData.hasOwnProperty("entries"))
                    throw new Error('File Malformed: missing "entries" field');
                if (!Array.isArray(inputCartData.entries))
                    throw new Error('File Malformed: "entries" field is not an array');

                if (!inputCartData.hasOwnProperty("version"))
                    throw new Error('File Malformed: missing "version" field');
                if (typeof inputCartData.version !== "string")
                    throw new Error('File Malformed: "version" field is not a string');

                if (!inputCartData.hasOwnProperty("title")) throw new Error('File Malformed: missing "title" field');
                if (typeof inputCartData.title !== "string")
                    throw new Error('File Malformed: "title" field is not a string');

                cartData.title = inputCartData.title;
                cartData.version = inputCartData.version;
                if (!versions.includes(cartData.version))
                    throw new Error(
                        `File Unsupported: the file uses ATT&CK (${cartData.version}), and Decider has (${versions}) loaded.`
                    );

                // add only desired fields for each entry
                _.forEach(inputCartData.entries, function (inputEntry) {
                    let cartEntry = {};

                    // basic regex check on ATT&CK ids
                    if (!/^T[0-9]{4}(\.[0-9]{3})?$/.test(inputEntry["index"]))
                        throw new Error(
                            `File Malformed: entry present with invalid ATT&CK Technique ID: ${inputEntry["index"]}`
                        );
                    if (!/^TA[0-9]{4}$/.test(inputEntry["tactic"]))
                        throw new Error(
                            `File Malformed: entry present with invalid ATT&CK Tactic ID: ${inputEntry["tactic"]}`
                        );

                    _.forEach(["name", "index", "notes", "tactic", "tacticName"], function (prop) {
                        cartEntry[prop] = inputEntry[prop];
                    });
                    cartData.entries.push(cartEntry);
                });
            } catch (err) {
                // fail -> print help statement
                spawnAlertModal(
                    "JSON Load Issue",
                    `There is an issue with this JSON file. Please ensure it is a Cart. ${err}`
                );
                $("#cartFile").val(null);
                return;
            }

            // success -> store new data and display
            sessionStorage.setItem("cart", JSON.stringify(cartData));
            updateCartTitle(cartData.title, cartData.version);
            $("#cartFile").val(null);
            $("#cart").empty();

            // reload cart if they're already on matching version - else go to homepage of correct version and unlock rename
            lockVersionSelect();
            unlockRename();
            if ($("#versionSelect").val() === cartData.version) populateCart();
            else urlCartMismatchGoHome();
        },
    });
}

function preCloseCartModal() {
    // Checks if closing the cart is even a valid action first

    let cartData = getCart();
    if (cartData.entries.length === 0) {
        //cart is empty
        showToast("You must add items to the cart first.", "is-warning");
        return;
    }
    openModal("#close_cart_modal");
}

function clearCart() {
    $("#cart").empty();
    updateCartTitle(null, null);
    sessionStorage.setItem("cart", emptyCartString());
    unlockVersionSelect();
    lockRename();
    closeModal("#close_cart_modal");
}

// --------------------------------------------------------------------------------------------------------------------
// Version Select Locking - Only allow access to 1 ATT&CK version when a cart is opened

// locks
function lockVersionSelect() {
    sessionStorage.setItem("version-select-locked", "true");
    $("#versionSelect").prop("disabled", true);

    // add tooltip explaining the cart has content of a specific version
    var versionSelectNavbarItem = $("#versionSelectNavbarItem");
    versionSelectNavbarItem.addClass("has-tooltip-bottom has-tooltip-multiline");
    versionSelectNavbarItem.attr(
        "data-tooltip",
        `The version selector is disabled as the cart already contains content
        for a specific version of ATT&CK. Please clear the cart before accessing the content of other versions.`
    );
}

// unlocks
function unlockVersionSelect() {
    sessionStorage.setItem("version-select-locked", "false");
    $("#versionSelect").prop("disabled", false);

    // clear selector tooltip message
    var versionSelectNavbarItem = $("#versionSelectNavbarItem");
    versionSelectNavbarItem.removeClass("has-tooltip-bottom has-tooltip-multiline");
    versionSelectNavbarItem.removeAttr("data-tooltip");
}

// checks state
function isVersionSelectLocked() {
    var versionSelectLocked = sessionStorage.getItem("version-select-locked");
    return versionSelectLocked === "true";
}

function lockRename() {
    $("#rename-button").prop("disabled", true);
    var renameButton = $("#rename-button");
    renameButton.attr(
        "data-tooltip",
        `You cannot edit the name of an empty cart. Please start a new one or load an old one.`
    );
}

// unlocks
function unlockRename() {
    $("#rename-button").prop("disabled", false);
    var renameButton = $("#rename-button");
    renameButton.removeClass("has-tooltip-multiline");
    renameButton.attr("data-tooltip", `Rename the cart.`);
}
