(function () {
  var region = document.querySelector(".toast-region");
  if (!region) return;
  setTimeout(function () {
    region.remove();
  }, 3000);
})();
