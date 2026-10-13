(function () {
  var form = document.querySelector("[data-vote-form]");
  if (!form || !window.fetch) return;

  var SEGMENT_CLASS = "decision-bar__segment decision-bar__segment--";

  function toast(message, ok) {
    var region = document.createElement("div");
    region.className = "toast-region";
    region.setAttribute("role", "status");
    var item = document.createElement("div");
    item.className = "toast";
    item.textContent = message;
    region.appendChild(item);
    var old = document.querySelector(".toast-region");
    if (old) old.remove();
    document.body.appendChild(region);
    setTimeout(function () {
      region.remove();
    }, 3000);
  }

  function renderBar(results) {
    var bar = document.querySelector("[data-decision-bar]");
    bar.textContent = "";
    if (!results.total) return;
    var positions = {};
    document.querySelectorAll("[data-option-id]").forEach(function (row) {
      var match = row.className.match(/option-row--(\d)/);
      positions[row.getAttribute("data-option-id")] = match ? match[1] : "0";
    });
    results.options.forEach(function (option) {
      if (!option.percent) return;
      var segment = document.createElement("span");
      segment.className = SEGMENT_CLASS + positions[option.id];
      segment.style.width = option.percent + "%";
      var label = document.createElement("span");
      label.className = "sr-only";
      label.textContent = option.text + " %" + option.percent;
      segment.appendChild(label);
      bar.appendChild(segment);
    });
  }

  function render(results) {
    results.options.forEach(function (option) {
      var row = document.querySelector('[data-option-id="' + option.id + '"]');
      if (!row) return;
      row.classList.remove("option-row--votable");
      row.classList.add("option-row--revealed");
      row.querySelector(".option-row__fill").style.width = option.percent + "%";
      var percent = row.querySelector(".option-row__percent");
      percent.textContent = "%" + option.percent;
      percent.hidden = false;
      var button = row.querySelector("button");
      if (button) button.disabled = true;
      if (option.id === results.voted_option_id) {
        row.classList.add("option-row--mine");
        var note = document.createElement("span");
        note.className = "sr-only";
        note.textContent = "Senin oyun";
        row.querySelector(".option-row__body").appendChild(note);
      }
    });
    renderBar(results);
    var badge = document.querySelector("[data-badge]");
    badge.textContent = results.badge_text;
    badge.className = "badge badge--" + results.badge_level;
    var total = document.querySelector("[data-total-votes]");
    if (total) total.textContent = results.total;
  }

  form.addEventListener("submit", function (event) {
    var submitter = event.submitter;
    if (!submitter || !submitter.value) return;
    event.preventDefault();

    var data = new FormData();
    data.append("option_id", submitter.value);
    var buttons = form.querySelectorAll("button");
    buttons.forEach(function (button) {
      button.disabled = true;
    });

    fetch(form.action, {
      method: "POST",
      body: data,
      credentials: "same-origin",
      headers: {
        Accept: "application/json",
        "X-CSRFToken": form.querySelector("[name=csrfmiddlewaretoken]").value,
        "X-Requested-With": "XMLHttpRequest",
      },
    })
      .then(function (response) {
        return response.json();
      })
      .then(function (body) {
        if (body.results) {
          render(body.results);
        } else {
          buttons.forEach(function (button) {
            button.disabled = false;
          });
        }
        toast(body.message, body.ok);
      })
      .catch(function () {
        buttons.forEach(function (button) {
          button.disabled = false;
        });
        toast("Bir sorun oluştu. Tekrar dene.", false);
      });
  });
})();
