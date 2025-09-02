document.addEventListener("DOMContentLoaded", function () {
  const micButton = document.getElementById("mic-button");
  const statusText = document.getElementById("status");
  const responseText = document.getElementById("response-text");
  const commandInput = document.getElementById("command-input");
  const textCommandButton = document.getElementById("text-command");
  const shoppingListContainer = document.getElementById(
    "shopping-list-container"
  );
  const clearListButton = document.getElementById("clear-list");

  let isListening = false;

  // Initialize shopping list
  loadShoppingList();

  // Voice command handler
  micButton.addEventListener("click", function () {
    if (isListening) {
      stopListening();
    } else {
      startListening();
    }
  });

  // Text command handler
  textCommandButton.addEventListener("click", function () {
    const command = commandInput.value.trim();
    if (command) {
      sendTextCommand(command);
      commandInput.value = "";
    }
  });

  // Clear list handler
  clearListButton.addEventListener("click", function () {
    if (confirm("Are you sure you want to clear your shopping list?")) {
      fetch("/clear-list", {
        method: "POST",
      })
        .then((response) => response.json())
        .then((data) => {
          showResponse(data.response);
          loadShoppingList();
        });
    }
  });

  // Enter key for text input
  commandInput.addEventListener("keypress", function (e) {
    if (e.key === "Enter") {
      textCommandButton.click();
    }
  });

  function startListening() {
    isListening = true;
    micButton.classList.add("listening");
    statusText.textContent = "Listening...";

    fetch("/voice-command", {
      method: "POST",
    })
      .then((response) => response.json())
      .then((data) => {
        showResponse(data.response);
        loadShoppingList();
        stopListening();
      })
      .catch((error) => {
        showResponse("Error: " + error.message);
        stopListening();
      });
  }

  function stopListening() {
    isListening = false;
    micButton.classList.remove("listening");
    statusText.textContent = "Click the microphone to speak";
  }

  function sendTextCommand(command) {
    showResponse("Processing...");

    fetch("/text-command", {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
      },
      body: JSON.stringify({ command: command }),
    })
      .then((response) => response.json())
      .then((data) => {
        showResponse(data.response);
        loadShoppingList();
      })
      .catch((error) => {
        showResponse("Error: " + error.message);
      });
  }

  function showResponse(text) {
    responseText.textContent = text;
  }

  function loadShoppingList() {
    fetch("/shopping-list")
      .then((response) => response.json())
      .then((data) => {
        renderShoppingList(data.shopping_list);
      })
      .catch((error) => {
        console.error("Error loading shopping list:", error);
      });
  }

  function renderShoppingList(items) {
    if (items.length === 0) {
      shoppingListContainer.innerHTML =
        '<div class="empty-list">Your shopping list is empty</div>';
      return;
    }

    // Group items by category
    const categories = {};
    items.forEach((item) => {
      if (!categories[item.category]) {
        categories[item.category] = [];
      }
      categories[item.category].push(item);
    });

    let html = "";

    for (const category in categories) {
      html += `<div class="category">
                <h3>${category.charAt(0).toUpperCase() + category.slice(1)}</h3>
                <div class="items">`;

      categories[category].forEach((item) => {
        html += `<div class="item">
                    <div class="item-name">${item.name}</div>
                    <div>
                        <span class="item-quantity">${item.quantity}</span>
                        <button class="remove-button" data-item="${item.name}">Remove</button>
                    </div>
                </div>`;
      });

      html += `</div></div>`;
    }

    shoppingListContainer.innerHTML = html;

    // Add event listeners to remove buttons
    document.querySelectorAll(".remove-button").forEach((button) => {
      button.addEventListener("click", function () {
        const itemName = this.getAttribute("data-item");
        sendTextCommand(`remove ${itemName}`);
      });
    });
  }
});
