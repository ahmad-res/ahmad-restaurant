
// MOBILE NAVIGATION
const menuToggle = document.getElementById("menuToggle");
const navLinks = document.getElementById("navLinks");

menuToggle.addEventListener("click", function () {
    navLinks.classList.toggle("show");
});

navLinks.querySelectorAll("a").forEach(function (link) {
    link.addEventListener("click", function () {
        navLinks.classList.remove("show");
    });
});

// FOOD FILTER
const filterButtons = document.querySelectorAll(".filter-btn");
const foodCards = document.querySelectorAll(".food-card");

filterButtons.forEach(function (button) {
    button.addEventListener("click", function () {
        filterButtons.forEach(function (item) {
            item.classList.remove("active");
        });

        button.classList.add("active");

        const selectedCategory = button.dataset.filter;

        foodCards.forEach(function (card) {
            if (
                selectedCategory === "all" ||
                card.dataset.category === selectedCategory
            ) {
                card.classList.remove("hidden");
            } else {
                card.classList.add("hidden");
            }
        });
    });
});

// SHOPPING CART
let cart = [];

const cartCount = document.getElementById("cartCount");
const cartTotal = document.getElementById("cartTotal");
const cartItems = document.getElementById("cartItems");

document.querySelectorAll(".add-btn").forEach(function (button) {
    button.addEventListener("click", function () {
        const name = button.dataset.name;
        const price = Number(button.dataset.price);

        const existingItem = cart.find(function (item) {
            return item.name === name;
        });

        if (existingItem) {
            existingItem.quantity++;
        } else {
            cart.push({
                name: name,
                price: price,
                quantity: 1
            });
        }

        updateCart();
    });
});

function updateCart() {
    let total = 0;
    let count = 0;

    cartItems.innerHTML = "";

    if (cart.length === 0) {
        cartItems.textContent = "Your cart is empty.";
    }

    cart.forEach(function (item) {
        total += item.price * item.quantity;
        count += item.quantity;

        const row = document.createElement("div");
        row.className = "cart-item";

        const name = document.createElement("span");
        name.textContent = item.name + " x " + item.quantity;

        const price = document.createElement("strong");
        price.textContent = "Rs. " + item.price * item.quantity;

        row.append(name, price);
        cartItems.appendChild(row);
    });

    cartCount.textContent = count;
    cartTotal.textContent = "Rs. " + total;
}

// WHATSAPP ORDER

// APNA NUMBER SIRF YAHAN ENTER KARNA HAI
// Example: 03001234567 becomes 923001234567
const phoneNumber = "923278014863";
document.getElementById("checkoutBtn").addEventListener("click", function () {

    if (cart.length === 0) {
        alert("Please add food items to your cart first.");
        return;
    }

    let message = "Hello Ahmad Restaurant! I want to place an order:\n\n";

    cart.forEach(function (item) {
        message += item.name + " x " + item.quantity;
        message += " = Rs. " + item.price * item.quantity + "\n";
    });

    const total = cart.reduce(function (sum, item) {
        return sum + item.price * item.quantity;
    }, 0);

    message += "\nTotal: Rs. " + total;

    const whatsappURL =
        "https://wa.me/" + phoneNumber +
        "?text=" + encodeURIComponent(message);

    window.open(whatsappURL, "_blank");
});
