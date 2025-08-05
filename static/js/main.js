document.addEventListener("DOMContentLoaded", () => {
  const productCard = document.querySelector(".product-card");
  const plusBtn = productCard.querySelector(".plus");
  const minusBtn = productCard.querySelector(".minus");
  const qtyDisplay = productCard.querySelector(".qty");
  const addToCartBtn = productCard.querySelector(".add-to-cart");

  let quantity = 1;

  plusBtn.addEventListener("click", () => {
    quantity++;
    qtyDisplay.textContent = quantity;
  });

  minusBtn.addEventListener("click", () => {
    if (quantity > 1) {
      quantity--;
      qtyDisplay.textContent = quantity;
    }
  });

  addToCartBtn.addEventListener("click", () => {
    const product = {
      id: productCard.dataset.id,
      name: productCard.querySelector("h2").textContent,
      price: 149,
      qty: quantity,
      image: productCard.querySelector("img").src
    };

    let cart = JSON.parse(localStorage.getItem("cart")) || [];

    const existing = cart.find(item => item.id === product.id);
    if (existing) {
      existing.qty += quantity;
    } else {
      cart.push(product);
    }

    localStorage.setItem("cart", JSON.stringify(cart));
    alert("Added to cart!");
    quantity = 1;
    qtyDisplay.textContent = quantity;
  });
});
