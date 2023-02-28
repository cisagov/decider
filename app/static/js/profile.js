window.cart_to_delete = {};

function loadCart(cart_id) {
    $.ajax({
        url: "/profile/load_cart",
        type: "POST",
        contentType: "application/json",
        dataType: "json",
        data: JSON.stringify({
            cart_id: cart_id,
        }),
        success: function (cart) {
            // Change version to match cart (from DB, and user auth'd, so this works fine)
            $.ajax({
                type: "PATCH",
                url: "/api/user_version_change",
                contentType: "application/json",
                dataType: "json",
                data: JSON.stringify({
                    new_version: cart.version,
                }),
                success: function () {
                    sessionStorage.setItem("cart", JSON.stringify(cart));
                    sessionStorage.setItem("cart-shown", "yes");
                    lockVersionSelect();
                    unlockRename();
                    location.reload(); // calls updateCartTitle() for us as well
                },
            });
        },
        error: function () {
            spawnAlertModal("Cart Load Issue", "Something went wrong. Please refresh the page.");
        },
    });
}

function askToConfirmDeleteCart(cart_id, element) {
    // store cart to delete and open confirmation dialog
    window.cart_to_delete = {
        cart_id: cart_id,
        element: element,
    };
    openModal("#cart_delete_confirm_modal");
}

function deleteCart() {
    // request deletion
    $.ajax({
        url: "/profile/delete_cart",
        type: "POST",
        contentType: "application/json",
        data: JSON.stringify({
            cart_id: window.cart_to_delete.cart_id,
        }),

        // pass -> success toast
        success: function () {
            $(window.cart_to_delete.element).parent().remove();
            showToast("Successfully deleted cart.");

            // clear confirmation
            window.cart_to_delete = {};
            closeModal("#cart_delete_confirm_modal");
        },

        // fail -> warning modal
        error: function () {
            // clear confirmation
            window.cart_to_delete = {};
            closeModal("#cart_delete_confirm_modal");

            spawnAlertModal("Cart Deletion Issue", "Something went wrong. Please refresh the page.");
        },
    });
}
