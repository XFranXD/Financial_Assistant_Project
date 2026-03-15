/* docs/assets/app.js */
/* Confidence bar animation on page load */
document.addEventListener('DOMContentLoaded', function() {
  document.querySelectorAll('.conf-bar-fill').forEach(function(bar) {
    var target = bar.getAttribute('data-width') || '0';
    setTimeout(function() { bar.style.width = target + '%'; }, 100);
  });
});
