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
// server.js (Node + Express)
const express = require('express');
const bodyParser = require('body-parser');
const pins = require('./gujarat_pincodes.json'); // same JSON file
const pinSet = new Set(pins.map(p=>String(p)));
const app = express();
app.use(bodyParser.json());

app.post('/place-order', (req, res) => {
  const { pincode } = req.body;
  if (!/^\d{6}$/.test(pincode)) return res.status(400).json({ok:false, error:'invalid_pincode'});
  if (!pinSet.has(String(pincode))) return res.status(400).json({ok:false, error:'out_of_area'});
  // proceed to create order...
  return res.json({ok:true, message:'order placed'});
});

app.listen(3000);

