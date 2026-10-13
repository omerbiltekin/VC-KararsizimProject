(function () {
  var MIN_OPTIONS = 2;
  var MAX_OPTIONS = 5;

  var list = document.querySelector("[data-option-list]");
  var template = document.querySelector("[data-option-template]");
  var addButton = document.querySelector("[data-add-option]");
  if (!list || !template || !addButton) return;

  function rows() {
    return list.querySelectorAll(".options__row");
  }

  function refresh() {
    var current = rows();
    current.forEach(function (row, index) {
      var input = row.querySelector("input");
      input.placeholder = "Seçenek " + (index + 1);
      input.setAttribute("aria-label", "Seçenek " + (index + 1));
      var remove = row.querySelector("[data-remove-option]");
      remove.hidden = false;
      remove.disabled = current.length <= MIN_OPTIONS;
    });
    addButton.hidden = false;
    addButton.disabled = current.length >= MAX_OPTIONS;
  }

  addButton.addEventListener("click", function () {
    if (rows().length >= MAX_OPTIONS) return;
    list.appendChild(template.content.cloneNode(true));
    refresh();
    list.lastElementChild.querySelector("input").focus();
  });

  list.addEventListener("click", function (event) {
    var button = event.target.closest("[data-remove-option]");
    if (!button || rows().length <= MIN_OPTIONS) return;
    button.closest(".options__row").remove();
    refresh();
  });

  refresh();
})();
